#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 omajili-manbu
"""
Verify the LK images shipped in this repository.

Default (CI) check needs only the image + public modulus:
  python3 tools/verify_our_lk.py --all

Optional maintainer checks against the official image and a reference
unlock image:
  python3 tools/verify_our_lk.py --image images/rodin_304_our_lk.img \
      --official /path/to/304lk.img --reference /path/to/304lkunlock.img
"""

import argparse
import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GFH_MAGIC = b'\x88\x16\x88\x58'
GFH_INFO = 0x58891689
HDR = 0x200
NEW_CERT2 = 0x430
PARTITION_SIZE = 0x1000000
LK_KEY_BODY_OFF = 0xEFBE9
AEE_KEY_BODY_OFF = 0xBA721

DEFAULT_IMAGES = [
    ROOT / 'images' / 'rodin_303_our_lk.img',
    ROOT / 'images' / 'rodin_304_our_lk.img',
]
DEFAULT_MODULUS = ROOT / 'keys' / 'modulus.txt'


def parse_parts(data):
    parts = []
    pos = 0
    while True:
        idx = data.find(GFH_MAGIC, pos)
        if idx < 0:
            break
        if idx + 0x50 <= len(data):
            info, = struct.unpack_from('<I', data, idx + 0x30)
            if info == GFH_INFO:
                size, = struct.unpack_from('<I', data, idx + 4)
                name = data[idx + 8:idx + 16].rstrip(b'\x00').decode('latin1')
                parts.append({'off': idx, 'name': name, 'size': size})
        pos = idx + 1
    for i, p in enumerate(parts):
        p['next'] = parts[i + 1]['off'] if i + 1 < len(parts) else len(data)
        p['raw'] = data[p['off']:p['next']]
    return parts


def find_part(parts, name, after=None):
    start = 0 if after is None else parts.index(after) + 1
    for p in parts[start:]:
        if p['name'] == name:
            return p
    return None


def load_modulus(path):
    txt = Path(path).read_text()
    if 'Modulus=' in txt:
        txt = txt.split('Modulus=', 1)[1]
    txt = ''.join(txt.split())
    if len(txt) != 512:
        raise SystemExit(f'bad modulus hex length {len(txt)} (expected 512)')
    mod = bytes.fromhex(txt)
    if not (mod[0] & 0x80) or not (mod[-1] & 1):
        raise SystemExit('modulus does not look like a 2048-bit RSA modulus')
    return mod


def check(cond, msg):
    print(('  OK   ' if cond else '  FAIL ') + msg)
    if not cond:
        raise SystemExit('VERIFY FAILED: ' + msg)


def verify_image(image, mod, official=None, reference=None):
    image = Path(image)
    data = image.read_bytes()
    print(f'\n== {image} ==')
    print(f'  sha256: {hashlib.sha256(data).hexdigest()}')
    check(len(data) == PARTITION_SIZE, f'size == 0x1000000 (got {len(data):#x})')
    parts = parse_parts(data)
    check(len(parts) == 15, f'15 GFH parts (got {len(parts)})')
    lk = find_part(parts, 'lk')
    aee = find_part(parts, 'aee')
    c2lk = find_part(parts, 'cert2', after=lk)
    c2aee = find_part(parts, 'cert2', after=aee)
    check(all([lk, aee, c2lk, c2aee]), 'lk/aee/cert2 parts found')

    lk_key = lk['off'] + HDR + LK_KEY_BODY_OFF
    aee_key = aee['off'] + HDR + AEE_KEY_BODY_OFF
    check(data[lk_key:lk_key + 256] == mod, f'lk key @ {lk_key:#x}')
    check(data[aee_key:aee_key + 256] == mod, f'aee key @ {aee_key:#x}')
    check(data[lk_key - 3:lk_key] == b'\x01\x00\x01', 'lk exponent 010001')
    check(data[aee_key - 3:aee_key] == b'\x01\x00\x01', 'aee exponent 010001')
    check(data.count(mod) == 2, 'modulus occurs exactly twice')

    for name, pc, sub in (('lk', c2lk, lk), ('aee', c2aee, aee)):
        check(pc['size'] == NEW_CERT2, f'cert2 after {name}: dsize 0x430')
        check(struct.unpack_from('<I', pc['raw'], 4)[0] == NEW_CERT2,
              f'cert2 after {name}: GFH dsize field 0x430')
        blk = data[pc['off'] + HDR:pc['off'] + HDR + 90]
        check(blk[:2] == b'\xa0\x58', f'cert2 after {name}: 0xA0 0x58 override')
        hdr = hashlib.sha256(data[sub['off']:sub['off'] + HDR]).digest()
        body = hashlib.sha256(data[sub['off'] + HDR:sub['off'] + HDR + sub['size']]).digest()
        check(blk[14:46] == hdr, f'cert2 after {name}: 2.4 header hash matches')
        check(blk[58:90] == body, f'cert2 after {name}: 2.1 image hash matches')
        der = data[pc['off'] + HDR + 90:pc['off'] + HDR + 90 + 0x3D6]
        check(len(der) == 0x3D6 and der[:4] == b'\x30\x82\x03\xd2',
              f'cert2 after {name}: original DER present (982 bytes)')

    if official:
        off = Path(official).read_bytes()
        op = parse_parts(off)
        olk = find_part(op, 'lk')
        oaee = find_part(op, 'aee')
        oc2lk = find_part(op, 'cert2', after=olk)
        oc2aee = find_part(op, 'cert2', after=oaee)
        for name, so, sn, koff in (('lk', olk, lk, LK_KEY_BODY_OFF),
                                   ('aee', oaee, aee, AEE_KEY_BODY_OFF)):
            o = off[so['off'] + HDR:so['off'] + HDR + so['size']]
            n = data[sn['off'] + HDR:sn['off'] + HDR + sn['size']]
            diffs = [i for i in range(min(len(o), len(n))) if o[i] != n[i]]
            check(len(o) == len(n), f'{name} body size unchanged')
            check(all(koff <= i < koff + 256 for i in diffs),
                  f'{name} body differs only in the 256-byte key')
        for name, oc, nc in (('lk', oc2lk, c2lk), ('aee', oc2aee, c2aee)):
            o = off[oc['off'] + HDR:oc['off'] + HDR + oc['size']]
            n = data[nc['off'] + HDR + 90:nc['off'] + HDR + 90 + oc['size']]
            check(o == n, f'cert2 after {name}: original DER == official')
        skip = {op.index(olk), op.index(oaee), op.index(oc2lk), op.index(oc2aee)}
        for i, (a, b) in enumerate(zip(op, parts)):
            if i in skip:
                continue
            check(a['raw'][:HDR + a['size']] == b['raw'][:HDR + b['size']],
                  f'{a["name"]}@{a["off"]:#x} content == official')

    if reference:
        ref = Path(reference).read_bytes()
        allowed = set()
        for s, l in ((lk_key, 256), (aee_key, 256),
                     (c2lk['off'] + HDR + 58, 32), (c2aee['off'] + HDR + 58, 32)):
            allowed.update(range(s, s + l))
        n = min(len(ref), len(data))
        diffs = [i for i in range(n) if ref[i] != data[i]]
        outside = [i for i in diffs if i not in allowed]
        check(not outside, f'diff vs reference only in key/image-hash ranges '
                           f'({len(diffs)} bytes, outside={len(outside)})')

    print(f'  PASS: {image.name}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--image', help='LK image to verify')
    ap.add_argument('--modulus', default=str(DEFAULT_MODULUS),
                    help='modulus file (default: keys/modulus.txt)')
    ap.add_argument('--official', help='optional official lk image for comparison')
    ap.add_argument('--reference', help='optional reference unlock image for diff check')
    ap.add_argument('--all', action='store_true', help='verify images/rodin_*_our_lk.img')
    args = ap.parse_args()

    mod = load_modulus(args.modulus)
    if args.all or not args.image:
        imgs = DEFAULT_IMAGES
    else:
        imgs = [Path(args.image)]
    for img in imgs:
        if not img.exists():
            raise SystemExit(f'missing {img}')
        verify_image(img, mod, args.official if len(imgs) == 1 else None,
                     args.reference if len(imgs) == 1 else None)
    print('\nALL CHECKS PASSED')


if __name__ == '__main__':
    main()
