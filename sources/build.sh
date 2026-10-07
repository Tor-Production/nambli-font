#!/usr/bin/env bash
# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
set -euo pipefail

nambli_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
nambli_python="${NAMBLI_PYTHON:-python3}"
cd "$nambli_root"

# Compile the current editable UFO masters; keep committed fonts separate.
"$nambli_python" sources/build_fontmake.py "$@"
