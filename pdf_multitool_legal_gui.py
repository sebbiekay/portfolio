#!/usr/bin/env python3
"""
Browser-based GUI for Legal PDF Splitter (no tkinter dependency).

Run:
    python3 pdf_multitool_legal_gui.py
Then open:
    http://127.0.0.1:8765
"""

import html
import json
import os
import shutil
import threading
import time
import uuid
import tempfile
from cgi import FieldStorage
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
import pytesseract


PARTITION_MAX_WORDS = 30
PARTITION_MAX_LINES = 6
HEADER_HINTS = [
    "public defenders",
    "department of public advocacy",
    "dpa.ky.gov",
    "equal opportunity employer",
]


jobs = {}
jobs_lock = threading.Lock()


def save_uploaded_pdf(file_item):
    filename = os.path.basename(file_item.filename or "uploaded.pdf")
    if not filename.lower().endswith(".pdf"):
        raise ValueError("Uploaded file must be a PDF.")

    temp_dir = tempfile.mkdtemp(prefix="legal_pdf_upload_")
    target_path = os.path.join(temp_dir, filename)
    with open(target_path, "wb") as out_file:
        shutil.copyfileobj(file_item.file, out_file)
    return target_path


class LegalPdfSplitterEngine:
    def __init__(self, log_callback=None, progress_callback=None):
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.ocr_cache = {}

    def log(self, text):
        if self.log_callback:
            self.log_callback(text)

    def progress(self, value, total, phase):
        if self.progress_callback:
            self.progress_callback(value, total, phase)

    def ocr_page(self, pdf_path, page_number):
        if page_number in self.ocr_cache:
            return self.ocr_cache[page_number]
        try:
            images = convert_from_path(
                pdf_path,
                first_page=page_number + 1,
                last_page=page_number + 1,
                dpi=200,
            )
            text = pytesseract.image_to_string(images[0])
            self.ocr_cache[page_number] = text
            return text
        except Exception as exc:
            self.log(f"OCR failed on page {page_number + 1}: {exc}")
            return ""

    def extract_text_smart(self, reader, pdf_path, page_number):
        try:
            text = reader.pages[page_number].extract_text()
            if text and text.strip():
                return text
        except Exception:
            pass
        self.log(f"OCR processing page {page_number + 1}...")
        return self.ocr_page(pdf_path, page_number)

    @staticmethod
    def is_partition_page(text):
        if not text or not text.strip():
            return True
        text = text.lower().strip()
        words = text.split()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        word_count = len(words)
        line_count = len(lines)
        if word_count <= PARTITION_MAX_WORDS and line_count <= PARTITION_MAX_LINES:
            return True
        for hint in HEADER_HINTS:
            if hint in text and word_count < 60:
                return True
        return False

    def detect_sections(self, reader, pdf_path, split_keyword=None):
        total_pages = len(reader.pages)
        sections = []
        current_start = 0
        self.log("Analyzing document structure...")
        for i in range(total_pages):
            self.progress(i + 1, total_pages, "Analyzing")
            text = self.extract_text_smart(reader, pdf_path, i)
            if self.is_partition_page(text):
                continue
            if split_keyword and split_keyword in text.lower():
                if i != current_start:
                    sections.append((current_start, i))
                    current_start = i
        if current_start < total_pages:
            sections.append((current_start, total_pages))
        return sections

    def save_sections(self, reader, pdf_path, sections, base_name, output_folder):
        os.makedirs(output_folder, exist_ok=True)
        saved = []
        total_pages_to_scan = sum(end - start for start, end in sections)
        processed = 0
        for idx, (start, end) in enumerate(sections, 1):
            writer = PdfWriter()
            pages_kept = 0
            for page_num in range(start, end):
                processed += 1
                self.progress(processed, max(total_pages_to_scan, 1), "Writing")
                text = self.extract_text_smart(reader, pdf_path, page_num)
                if self.is_partition_page(text):
                    continue
                writer.add_page(reader.pages[page_num])
                pages_kept += 1
            if pages_kept == 0:
                continue
            filename = f"{base_name}_{idx}.pdf"
            path = os.path.join(output_folder, filename)
            with open(path, "wb") as out_file:
                writer.write(out_file)
            self.log(f"Saved {filename} ({pages_kept} pages)")
            saved.append(filename)
        return saved

    def run_split(self, pdf_path, base_name, split_keyword, output_folder=None):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError("File not found.")
        if not pdf_path.lower().endswith(".pdf"):
            raise ValueError("Input must be a PDF file.")
        if shutil.which("tesseract") is None:
            raise RuntimeError("Missing dependency: tesseract")
        if shutil.which("pdftoppm") is None:
            raise RuntimeError("Missing dependency: pdftoppm (poppler)")

        self.ocr_cache.clear()
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        if not output_folder:
            downloads = os.path.expanduser("~/Downloads")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            output_folder = os.path.join(downloads, f"{base_name}_Split_{timestamp}")

        self.log(f"Total pages: {total_pages}")
        sections = self.detect_sections(
            reader=reader,
            pdf_path=pdf_path,
            split_keyword=split_keyword if split_keyword else None,
        )
        if not sections:
            self.log("No keyword sections found. Using full document split.")
            sections = [(0, total_pages)]
        self.log(f"Sections detected: {len(sections)}")
        self.log("Splitting and removing partition pages...")
        saved_files = self.save_sections(
            reader=reader,
            pdf_path=pdf_path,
            sections=sections,
            base_name=base_name,
            output_folder=output_folder,
        )
        return {
            "total_pages": total_pages,
            "saved_count": len(saved_files),
            "output_folder": output_folder,
            "saved_files": saved_files,
        }


def update_job(job_id, **kwargs):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)


def append_log(job_id, message):
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id]["logs"].append(message)


def run_job(job_id, payload):
    try:
        engine = LegalPdfSplitterEngine(
            log_callback=lambda msg: append_log(job_id, msg),
            progress_callback=lambda value, total, phase: update_job(
                job_id,
                progress={
                    "phase": phase,
                    "current": value,
                    "total": total,
                    "percent": (value / total * 100) if total else 0,
                },
            ),
        )
        update_job(job_id, status="running")
        result = engine.run_split(
            pdf_path=payload["pdf_path"],
            base_name=payload["base_name"],
            split_keyword=payload["split_keyword"],
            output_folder=payload["output_folder"] or None,
        )
        update_job(job_id, status="done", result=result, ended_at=time.time())
    except Exception as exc:
        update_job(job_id, status="error", error=str(exc), ended_at=time.time())


def html_page(body):
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PDF Multitool</title>
  <style>
    :root {{
      --bg: #f3f7f4;
      --ink: #102018;
      --panel: #ffffff;
      --accent: #1b7a4a;
      --muted: #5f6f64;
      --line: #d5dfd8;
    }}
    body {{
      margin: 0;
      font-family: "SF Pro Text", "Helvetica Neue", sans-serif;
      color: var(--ink);
      background: radial-gradient(circle at 20% 10%, #dceee3 0%, var(--bg) 45%);
    }}
    .wrap {{
      max-width: 900px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
      box-shadow: 0 8px 30px rgba(16, 32, 24, 0.08);
    }}
    h1 {{
      margin: 0 0 8px 0;
      font-size: 1.35rem;
    }}
    .muted {{
      color: var(--muted);
      margin-bottom: 12px;
    }}
    label {{
      display: block;
      margin-top: 10px;
      font-weight: 600;
      font-size: 0.95rem;
    }}
    input {{
      width: 100%;
      box-sizing: border-box;
      margin-top: 4px;
      padding: 10px 11px;
      border-radius: 10px;
      border: 1px solid var(--line);
      font-size: 0.95rem;
    }}
    button {{
      margin-top: 14px;
      background: var(--accent);
      color: white;
      border: 0;
      border-radius: 10px;
      padding: 10px 14px;
      font-weight: 700;
      cursor: pointer;
    }}
    progress {{
      width: 100%;
      margin-top: 10px;
      height: 16px;
    }}
    pre {{
      background: #0f1713;
      color: #d6e3db;
      padding: 12px;
      border-radius: 10px;
      height: 280px;
      overflow: auto;
      white-space: pre-wrap;
      margin-top: 10px;
    }}
    .status {{
      font-weight: 700;
      margin-top: 10px;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    {body}
  </div>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def _send_html(self, text, code=200):
        encoded = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, obj, code=200):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(html_page(self.render_home()))
            return
        if parsed.path.startswith("/job/"):
            job_id = parsed.path.split("/")[-1]
            self._send_html(html_page(self.render_job(job_id)))
            return
        if parsed.path.startswith("/api/job/"):
            job_id = parsed.path.split("/")[-1]
            with jobs_lock:
                job = jobs.get(job_id)
            if not job:
                self._send_json({"error": "Job not found"}, code=404)
                return
            self._send_json(job)
            return
        self._send_html(html_page("<div class='card'>Not found</div>"), code=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/start":
            self._send_html(html_page("<div class='card'>Not found</div>"), code=404)
            return

        content_type = self.headers.get("Content-Type", "")
        pdf_path = ""
        base_name = "Case"
        split_keyword = ""
        output_folder = ""

        try:
            if "multipart/form-data" in content_type:
                form = FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        "REQUEST_METHOD": "POST",
                        "CONTENT_TYPE": content_type,
                    },
                )
                if "pdf_file" in form and getattr(form["pdf_file"], "filename", None):
                    pdf_path = save_uploaded_pdf(form["pdf_file"])
                else:
                    raise ValueError("Please select a PDF file.")

                base_name = (form.getfirst("base_name", "Case") or "Case").strip() or "Case"
                split_keyword = (form.getfirst("split_keyword", "") or "").strip().lower()
                output_folder = (form.getfirst("output_folder", "") or "").strip()
            else:
                raise ValueError("Invalid form submission type.")
        except Exception as exc:
            self._send_html(
                html_page(
                    "<div class='card'><h1>Invalid Upload</h1>"
                    f"<p class='muted'>{html.escape(str(exc))}</p>"
                    "<p><a href='/'>Back</a></p></div>"
                ),
                code=400,
            )
            return

        job_id = uuid.uuid4().hex
        with jobs_lock:
            jobs[job_id] = {
                "id": job_id,
                "status": "queued",
                "error": "",
                "result": None,
                "logs": [],
                "progress": {"phase": "Queued", "current": 0, "total": 1, "percent": 0},
                "created_at": time.time(),
                "ended_at": None,
            }

        payload = {
            "pdf_path": pdf_path,
            "base_name": base_name,
            "split_keyword": split_keyword,
            "output_folder": output_folder,
        }

        thread = threading.Thread(target=run_job, args=(job_id, payload), daemon=True)
        thread.start()

        self.send_response(303)
        self.send_header("Location", f"/job/{job_id}")
        self.end_headers()

    def render_home(self):
        missing = []
        if shutil.which("tesseract") is None:
            missing.append("tesseract")
        if shutil.which("pdftoppm") is None:
            missing.append("pdftoppm (poppler)")
        warning = ""
        if missing:
            warning = (
                f"<p class='muted'><strong>Missing system tools:</strong> "
                f"{html.escape(', '.join(missing))}<br/>"
                f"Install: <code>brew install tesseract poppler</code></p>"
            )

        return f"""
<div class="card">
  <h1>PDF Splitter</h1>
  {warning}
  <form method="post" action="/start" enctype="multipart/form-data" id="splitForm">
    <div id="dropzone" style="margin-top:6px; border:2px dashed #9ab9a7; border-radius:10px; padding:18px; text-align:center; background:#f7fbf8;">
      <strong>Drag and drop PDF here</strong><br/>
      or <button type="button" id="pickBtn" style="margin-top:8px;">Choose PDF</button>
      <div id="pickedName" class="muted" style="margin-top:8px; margin-bottom:0;">No file selected</div>
    </div>
    <input id="pdf_file" type="file" name="pdf_file" accept="application/pdf,.pdf" style="display:none;" />
    <label>Base name</label>
    <input name="base_name" value="Case" />
    <label>Split keyword (optional)</label>
    <input name="split_keyword" placeholder="case number" />
    <label>Output folder (optional)</label>
    <input name="output_folder" placeholder="/Users/you/Downloads" />
    <button type="submit">Start</button>
  </form>
</div>
<script>
const form = document.getElementById('splitForm');
const input = document.getElementById('pdf_file');
const pickBtn = document.getElementById('pickBtn');
const dropzone = document.getElementById('dropzone');
const pickedName = document.getElementById('pickedName');

function updatePickedName() {{
  if (input.files && input.files.length > 0) {{
    pickedName.textContent = 'Selected: ' + input.files[0].name;
  }} else {{
    pickedName.textContent = 'No file selected';
  }}
}}

pickBtn.addEventListener('click', () => input.click());
input.addEventListener('change', updatePickedName);

dropzone.addEventListener('dragover', (e) => {{
  e.preventDefault();
  dropzone.style.borderColor = '#1b7a4a';
  dropzone.style.background = '#edf8f1';
}});

dropzone.addEventListener('dragleave', () => {{
  dropzone.style.borderColor = '#9ab9a7';
  dropzone.style.background = '#f7fbf8';
}});

dropzone.addEventListener('drop', (e) => {{
  e.preventDefault();
  dropzone.style.borderColor = '#9ab9a7';
  dropzone.style.background = '#f7fbf8';
  const files = e.dataTransfer.files;
  if (!files || files.length === 0) return;
  const dt = new DataTransfer();
  dt.items.add(files[0]);
  input.files = dt.files;
  updatePickedName();
}});

form.addEventListener('submit', (e) => {{
  const hasUpload = input.files && input.files.length > 0;
  if (!hasUpload) {{
    e.preventDefault();
    alert('Select a PDF file.');
  }}
}});
</script>
"""

    def render_job(self, job_id):
        return f"""
<div class="card">
  <h1>Job {html.escape(job_id[:8])}</h1>
  <div id="status" class="status">Loading...</div>
  <progress id="bar" max="100" value="0"></progress>
  <div id="phase" class="muted"></div>
  <pre id="log"></pre>
  <p><a href="/">Start another job</a></p>
</div>
<script>
const jobId = {json.dumps(job_id)};
async function tick() {{
  const res = await fetch('/api/job/' + jobId, {{cache: 'no-store'}});
  if (!res.ok) {{
    document.getElementById('status').textContent = 'Job not found';
    return;
  }}
  const data = await res.json();
  document.getElementById('status').textContent = 'Status: ' + data.status.toUpperCase();
  const pct = data.progress ? data.progress.percent : 0;
  document.getElementById('bar').value = pct;
  const phase = data.progress
    ? `${{data.progress.phase}} (${{data.progress.current}}/${{data.progress.total}})`
    : '';
  document.getElementById('phase').textContent = phase;
  document.getElementById('log').textContent = (data.logs || []).join('\\n');
  if (data.status === 'done' && data.result) {{
    document.getElementById('log').textContent +=
      `\\n\\nComplete. Files created: ${{data.result.saved_count}}` +
      `\\nOutput folder: ${{data.result.output_folder}}`;
    return;
  }}
  if (data.status === 'error') {{
    document.getElementById('log').textContent += '\\n\\nError: ' + data.error;
    return;
  }}
  setTimeout(tick, 700);
}}
tick();
</script>
"""

    def log_message(self, format, *args):
        return


def main():
    host = "127.0.0.1"
    port = 8765
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"PDF Splitter running at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.server_close()


if __name__ == "__main__":
    main()
