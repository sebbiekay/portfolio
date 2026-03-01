#!/usr/bin/env python3
"""Build standalone executable for current OS using PyInstaller."""

import os
import shutil
import subprocess
import sys


APP_NAME = "PDFMultitool"
ENTRY_FILE = "pdf_multitool_legal_gui.py"


def run(cmd, env=None):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, env=env)


def main():
    if not os.path.exists(ENTRY_FILE):
        raise FileNotFoundError(f"Missing entry file: {ENTRY_FILE}")

    pyinstaller = shutil.which("pyinstaller")
    if pyinstaller:
        cmd = [pyinstaller]
    else:
        cmd = [sys.executable, "-m", "PyInstaller"]

    cmd += [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        APP_NAME,
        ENTRY_FILE,
    ]

    # Keep console for logs and easy troubleshooting across OSes.
    env = os.environ.copy()
    env.setdefault("PYINSTALLER_CONFIG_DIR", os.path.join(os.getcwd(), ".pyinstaller"))
    run(cmd, env=env)
    print(f"\nBuild complete. Output binary is in: dist/{APP_NAME}")
    if os.name == "nt":
        print("Windows output: dist/PDFMultitool.exe")
    elif sys.platform == "darwin":
        print("macOS output: dist/PDFMultitool")
    else:
        print("Linux output: dist/PDFMultitool")


if __name__ == "__main__":
    main()
