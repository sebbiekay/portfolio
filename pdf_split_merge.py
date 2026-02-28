#!/usr/bin/env python3

import os
import PyPDF2
from PyPDF2 import PdfReader, PdfWriter

#Ask user for PDF path and search phrase
pdf_path = input("Enter file path: ").strip()
phrase = input("Enter split term: ").strip()
base_name = input("Enter a base name for the split file (e.g., 'CR'): ").strip()

reader = PdfReader("sample.pdf")
hits = []
downloads_folder = os.path.expanduser("~/Downloads")


print(len(reader.pages))

for i, page in enumerate(reader.pages):
    text = page.extract_text()
    if text and phrase in text.lower():
        print(f"Phrase found on page {i + 1}")
#Checks for keyword on page



for i, page in enumerate(reader.pages):
    text = page.extract_text()
    if text and phrase in text.lower():
        hits.append(i)
print(hits)
#Marks start and end of split

if not hits:
    print("No matches found.")
else: 
    for i in range(1, len(hits)):
        if hits[i] == hits[i - 1] + 1:
            print(f"Consecutive matches found on pages {hits[i-1] + 1} and {hits[i]+1}")

ranges = []
for idx, start in enumerate(hits):
    if idx + 1 < len(hits):
        end = hits[idx + 1]
    else:
        end = len(reader.pages)
    ranges.append((start, end))
print(ranges)
#Marks the range of the split




for idx, (start, end) in enumerate(ranges):
    writer = PdfWriter()
    for p in range(start, end):
        writer.add_page(reader.pages[p])
    custom_name = input(f"Enter name for section {idx + 1} (Press enter to use {base_name}_{idx + 1}): ")
    if not custom_name:
        custom_name = f"{base_name}_{idx + 1}"
    out_path = os.path.join(downloads_folder, f"{custom_name}.pdf")
    with open(out_path, "wb") as f:writer.write(f)
    print(f"Saved: {out_path}")
#Splits the PDF into sections and saves to folder

merge_choice = input("Would you like to merge files? (y/n): ").strip().lower()

if merge_choice == "y":
    downloads_folder = os.path.expanduser("~/Downloads")
    files = [f for f in os.listdir(downloads_folder) if f.endswith('.pdf')]
    print("PDFs in File: ")
    for idx, filename in enumerate(files, 1):
        print(f"{idx}.{filename}")

    selection = input("Enter the numbers of the files you want to merge, separated by commas (e.g. 1,3,5): ")
    try:
        indices = [int(x.strip()) - 1 for x in selection.split(',') if x.strip().isdigit()]
        selected_files = [os.path.join(downloads_folder, files[i]) for i in indices if 0<= i < len(files)]

        merger = PdfWriter()
        for filepath in selected_files:
            reader = PdfReader(filepath)
            for page in reader.pages:
                merger.add_page(page)

        merged_name = input("Enter a name for merged pdf (no extension): ")
        merged_path = os.path.join(downloads_folder, f"{merged_name}.pdf")
        with open(merged_path, "wb") as f:
            merger.write(f)
        print(f"Merged PDF saved as: {merged_path}")
    except Exception as e:
        print("Selection error:", e)
else:
    print("Done")
