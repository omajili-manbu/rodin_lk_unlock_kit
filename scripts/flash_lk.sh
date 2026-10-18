#!/usr/bin/env bash
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 omajili-manbu
#
# Example helper to write an LK image to lk_a and lk_b via root + dd.
#
# THIS IS DESTRUCTIVE. It overwrites two partitions. Read docs/05-flash-unlock.md
# first, confirm the block-device paths on YOUR device, and keep a backup of the
# original lk_a/lk_b.
#
# Usage:
#   scripts/flash_lk.sh <image> <lk_a_block_device> <lk_b_block_device>
#
# Example (paths vary by device/firmware):
#   scripts/flash_lk.sh images/rodin_304_our_lk.img \
#       /dev/block/by-name/lk_a /dev/block/by-name/lk_b
#
set -euo pipefail
cd "$(dirname "$0")/.."

IMG="${1:-}"
LK_A="${2:-}"
LK_B="${3:-}"

if [ -z "$IMG" ] || [ -z "$LK_A" ] || [ -z "$LK_B" ]; then
  echo "usage: $0 <image> <lk_a_block_device> <lk_b_block_device>" >&2
  exit 2
fi
if [ ! -f "$IMG" ]; then
  echo "image not found: $IMG" >&2
  exit 2
fi

SIZE=$(stat -c %s "$IMG")
if [ "$SIZE" != "16777216" ]; then
  echo "refusing: image size is $SIZE, expected 16777216 (16MB)" >&2
  exit 2
fi

echo "image : $IMG"
echo "size  : $SIZE"
echo "sha256: $(sha256sum "$IMG" | awk '{print $1}')"
echo
echo "target A: $LK_A"
echo "target B: $LK_B"
echo
echo "This will overwrite BOTH lk partitions. Type YES to continue."
read -r CONFIRM
if [ "$CONFIRM" != "YES" ]; then
  echo "aborted"
  exit 1
fi

if ! command -v adb >/dev/null 2>&1; then
  echo "adb not found" >&2
  exit 2
fi

echo "== pushing image =="
adb push "$IMG" /data/local/tmp/our_lk.img

echo "== checking target devices =="
adb shell su -c "test -b $LK_A" || { echo "not a block device: $LK_A" >&2; exit 3; }
adb shell su -c "test -b $LK_B" || { echo "not a block device: $LK_B" >&2; exit 3; }

echo "== writing $LK_A =="
adb shell su -c "dd if=/data/local/tmp/our_lk.img of=$LK_A bs=1M"
echo "== writing $LK_B =="
adb shell su -c "dd if=/data/local/tmp/our_lk.img of=$LK_B bs=1M"
adb shell su -c 'sync'

echo
echo "done. Reboot to bootloader and follow the dual-slot unlock flow."
