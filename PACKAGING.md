# Standalone Offline Packaging

This app can be packaged as a standalone executable for each OS using PyInstaller.

Important:
- You must build on each target OS (Windows build on Windows, macOS build on macOS, Linux build on Linux).
- One binary cannot run on all OSes.

## 1) Install build dependencies

```bash
python3 -m pip install -r requirements-build.txt
```

## 2) Build executable

```bash
python3 build_standalone.py
```

`build_standalone.py` automatically uses a project-local PyInstaller cache (`.pyinstaller/`) to avoid permission issues with system cache paths.

Output:
- macOS/Linux: `dist/PDFMultitool`
- Windows: `dist/PDFMultitool.exe`

## GitHub Actions CI Build

This repo includes:
- `.github/workflows/build-standalone.yml`

It builds on:
- `ubuntu-latest`
- `macos-latest`
- `windows-latest`

Trigger:
- push to `main`
- manual run (`workflow_dispatch`)

Artifacts:
- `PDFMultitool-linux`
- `PDFMultitool-macos`
- `PDFMultitool-windows`

## 3) Run packaged app

The app starts a local offline web UI and opens your browser automatically.

```bash
./dist/PDFMultitool
```

Windows:

```bat
dist\PDFMultitool.exe
```

## OCR Runtime Dependencies

The app needs:
- `tesseract`
- `pdftoppm` (from Poppler)

You have two options:

1. Install system-wide tools:
- macOS: `brew install tesseract poppler`
- Linux: install via distro package manager
- Windows: install Tesseract + Poppler binaries

2. Bundle OCR tools next to the executable for fully offline distribution.

Folder layout next to the executable:

- macOS/Linux:
  - `tools/macos/tesseract/bin/tesseract` (macOS)
  - `tools/macos/poppler/bin/pdftoppm` (macOS)
  - `tools/linux/tesseract/bin/tesseract` (Linux)
  - `tools/linux/poppler/bin/pdftoppm` (Linux)
- Windows:
  - `tools/windows/tesseract/tesseract.exe`
  - `tools/windows/poppler/bin/pdftoppm.exe`

The app auto-detects these locations.

## Optional launch flags

```bash
./dist/PDFMultitool --host 127.0.0.1 --port 8765 --no-browser
```
