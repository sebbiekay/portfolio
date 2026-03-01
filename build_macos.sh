#!/usr/bin/env bash
set -euo pipefail
python3 -m pip install -r requirements-build.txt
python3 build_standalone.py
