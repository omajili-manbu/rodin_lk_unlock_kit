#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 omajili-manbu
# Verify everything that can be checked without a device.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PYTHON:-python3}"

echo "== [1/3] image checksums =="
(cd images && sha256sum -c SHA256SUMS.txt)

echo
echo "== [2/3] image structure / key / cert2 hashes =="
"$PY" tools/verify_our_lk.py --all

echo
echo "== [3/3] signer self-test =="
"$PY" tools/sign_token.py --self-test

echo
echo "ALL LOCAL CHECKS PASSED"
