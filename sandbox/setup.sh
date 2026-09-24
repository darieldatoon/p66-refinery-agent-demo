#!/usr/bin/env bash
set -euo pipefail
# The disposable sandbox uses a PEP 668 managed system interpreter.
python3 -m pip install --quiet --break-system-packages pandas==2.3.3 matplotlib==3.10.8
mkdir -p /reports
