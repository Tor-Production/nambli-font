# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
"""Use installed dependencies or an explicitly configured local directory."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
candidate = os.environ.get('NAMBLI_PYTHON_DEPS')
if candidate:
    sys.path.insert(0, candidate)
