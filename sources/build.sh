#!/usr/bin/env bash
# Copyright 2026 The Nambli Project Authors (https://github.com/Tor-Production/nambli-font)
# SPDX-License-Identifier: OFL-1.1
set -euo pipefail

nambli_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
nambli_python="${NAMBLI_PYTHON:-python3}"
cd "$nambli_root"

# Build all 12 static faces using the original open Python design pipeline.
# The builder writes build-fonts/, leaving the shipping fonts/ tree untouched.
"$nambli_python" sources/build_family.py

# Export editable UFO3s and verify every outline, metric, Unicode mapping and
# OpenType layout table. Existing build UFOs are verified, never overwritten.
"$nambli_python" sources/export_ufo.py \
  --fonts build-fonts \
  --features sources/features.fea \
  --output build-ufos \
  --report build-ufo-validation.json \
  --resume-existing
