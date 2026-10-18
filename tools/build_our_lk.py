#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 omajili-manbu
"""
Build our own unlock LK image from the official lk partition image.

Changes vs official:
  1) Replace the Xiaomi unlock-token RSA-2048 public modulus in the 'lk' and
     'aee' sub-images with our own modulus. The 3-byte exponent 01 00 01 is
     left untouched (RSA e=65537).
  2) Insert a 90-byte ASN.1 0xA0 hash-override block before the cert2 DER of
     the lk and aee sub-images. The block carries:
         OID 2.16.886.2454.2.4  BIT STRING  SHA-256(GFH header)
         OID 2.16.886.2454.2.1  BIT STRING  SHA-256(image body)
     The original cert2 DER is kept byte-identical (its signature stays valid).
  3) cert2 dsize 0x3d6 -> 0x430, then pad the partition image to 0x1000000.

Verified on rodin 303 and 304 official images (same GFH layout, same key
offsets). Intended for the user's own device with the user's own private key.
"""

import argparse
import hashlib
import struct
import sys
from pathlib import Path

GFH_MAGIC = b'\x88\x16\x88\x58'
GFH_INFO = 0x58891689
PART_HDR = 0x200
CERT2_NEW_SIZE = 0x430
PARTITION_SIZE = 0x1000000

# unlock-token key body offsets inside the lk / aee sub-images (rodin 303/304)
LK_KEY_BODY_OFF = 0xEFBE9
AEE_KEY_BODY_OFF = 0xBA721

OID_HDR = bytes.fromhex('060760867693160204')  # 2.16.886.2454.2.4
OID_IMG = bytes.fromhex('060760867693160201')  # 2.16.886.2454.2.1


def parse_parts(data: bytes):
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


def der_len(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    b = n.to_bytes((n.bit_length() + 7) // 8, 'big')
    return bytes([0x80 | len(b)]) + b


def bitstring(h: bytes) -> bytes:
    if len(h) != 32:
        raise ValueError('hash must be 32 bytes')
    return b'\x03\x21\x00' + h


def make_override(hdr_hash: bytes, body_hash: bytes) -> bytes:
    body = OID_HDR + bitstring(hdr_hash) + OID_IMG + bitstring(body_hash)
    blk = b'\xa0' + der_len(len(body)) + body
    if len(blk) != 90:
        raise AssertionError('override block must be 90 bytes')
    return blk


def load_modulus(arg: str) -> bytes:
    txt = Path(arg).read_text() if Path(arg).exists() else arg
    txt = txt.strip()
    if 'Modulus=' in txt:
        txt = txt.split('Modulus=', 1)[1]
    txt = ''.join(txt.split())
    if len(txt) == 514 and txt.startswith('00'):
        txt = txt[2:]
    if len(txt) != 512:
        raise ValueError(f'modulus hex must be 512 chars (256 bytes), got {len(txt)}')
    mod = bytes.fromhex(txt)
    if not (mod[0] & 0x80) or not (mod[-1] & 1):
        raise ValueError('modulus does not look like a 2048-bit RSA modulus')
    return mod


def find_part(parts, name, after=None):
    start = 0 if after is None else parts.index(after) + 1
    for p in parts[start:]:
        if p['name'] == name:
            return p
    raise ValueError(f'part {name!r} not found')


def build(official_path: Path, modulus: bytes, reference_path=None):
    data = official_path.read_bytes()
    parts = parse_parts(data)
    lk = find_part(parts, 'lk')
    aee = find_part(parts, 'aee')
    cert2_lk = find_part(parts, 'cert2', after=lk)
    cert2_aee = find_part(parts, 'cert2', after=aee)

    if len(data) < PARTITION_SIZE and data[0:4] != GFH_MAGIC:
        raise ValueError('not an lk partition image')

    # Locate the official unlock-token key inside lk/aee bodies.
    old_key = lk['raw'][PART_HDR + LK_KEY_BODY_OFF:PART_HDR + LK_KEY_BODY_OFF + 256]
    if len(old_key) != 256:
        raise ValueError('failed to read old key from lk')
    n_occ = data.count(old_key)
    if n_occ != 2:
        raise ValueError(f'expected 2 occurrences of official key, found {n_occ} '
                         '(unsupported image version?)')

    report = []
    def log(s=''):
        print(s)
        report.append(s)

    log(f'official : {official_path}  size={len(data):#x}  parts={len(parts)}')
    log(f'new key  : {modulus[:8].hex()}...{modulus[-8:].hex()} ({len(modulus)*8} bits)')
    log(f'old key  : {old_key[:8].hex()}...{old_key[-8:].hex()}  occurrences={n_occ}')

    # Replace key in lk and aee, keep exponent 01 00 01.
    def replace_key(part, name):
        raw = bytearray(part['raw'])
        idx = raw.find(old_key)
        if idx < 0 or raw.find(old_key, idx + 1) >= 0:
            raise ValueError(f'{name}: expected exactly one key occurrence')
        raw[idx:idx + 256] = modulus
        part['raw'] = bytes(raw)
        log(f'{name}: key replaced at file offset {part["off"] + idx:#x} '
            f'(body offset {idx - PART_HDR:#x})')

    replace_key(lk, 'lk')
    replace_key(aee, 'aee')

    hdr_lk = hashlib.sha256(lk['raw'][:PART_HDR]).digest()
    hdr_aee = hashlib.sha256(aee['raw'][:PART_HDR]).digest()
    body_lk = hashlib.sha256(lk['raw'][PART_HDR:PART_HDR + lk['size']]).digest()
    body_aee = hashlib.sha256(aee['raw'][PART_HDR:PART_HDR + aee['size']]).digest()
    pre_lk = make_override(hdr_lk, body_lk)
    pre_aee = make_override(hdr_aee, body_aee)

    log(f'lk  header sha256: {hdr_lk.hex()}')
    log(f'lk  body   sha256: {body_lk.hex()}')
    log(f'aee header sha256: {hdr_aee.hex()}')
    log(f'aee body   sha256: {body_aee.hex()}')
    log(f'lk  override: {pre_lk.hex()}')
    log(f'aee override: {pre_aee.hex()}')

    # Assemble. cert2 parts get the override block and lose their old padding
    # (the new block fills it and shifts following parts by +0x50).
    out = bytearray()
    for p in parts:
        if p is cert2_lk or p is cert2_aee:
            gfh = bytearray(p['raw'][:PART_HDR])
            struct.pack_into('<I', gfh, 4, CERT2_NEW_SIZE)
            content = p['raw'][PART_HDR:PART_HDR + p['size']]
            prefix = pre_lk if p is cert2_lk else pre_aee
            new_part = bytes(gfh) + prefix + content
            if len(new_part) != PART_HDR + CERT2_NEW_SIZE:
                raise AssertionError('cert2 size mismatch')
            out += new_part
            log(f'cert2 after {("lk" if p is cert2_lk else "aee")}: '
                f'dsize 0x{p["size"]:x} -> 0x{CERT2_NEW_SIZE:x}, '
                f'inserted 90-byte override at file offset {len(out) - len(new_part) + PART_HDR:#x}')
        else:
            out += p['raw']

    if len(out) > PARTITION_SIZE:
        raise ValueError(f'image too large: {len(out):#x}')
    out += b'\x00' * (PARTITION_SIZE - len(out))

    # ---- validate ----
    new_parts = parse_parts(out)
    if len(new_parts) != len(parts):
        raise AssertionError('part count changed')
    for a, b in zip(parts, new_parts):
        if a['name'] != b['name'] or a['size'] != b['size'] and a['name'] != 'cert2':
            raise AssertionError(f'part mismatch {a["name"]}')
    log(f'output   : size={len(out):#x}  parts={len(new_parts)}')

    # keys present exactly twice at expected places
    cnt = out.count(modulus)
    if cnt != 2:
        raise AssertionError(f'new key occurrences = {cnt}, expected 2')
    for name, p in (('lk', new_parts[0]), ('aee', find_part(new_parts, 'aee'))):
        key_off = p['off'] + PART_HDR + (LK_KEY_BODY_OFF if name == 'lk' else AEE_KEY_BODY_OFF)
        if out[key_off:key_off + 256] != modulus:
            raise AssertionError(f'{name}: new key not at expected offset')
        log(f'{name}: new key verified at file offset {key_off:#x}')

    # cert2 overrides verified
    for name, p, hdr, body in (
        ('lk', find_part(new_parts, 'cert2', after=find_part(new_parts, 'lk')), hdr_lk, body_lk),
        ('aee', find_part(new_parts, 'cert2', after=find_part(new_parts, 'aee')), hdr_aee, body_aee),
    ):
        if p['size'] != CERT2_NEW_SIZE:
            raise AssertionError(f'{name} cert2 dsize != 0x430')
        blk = out[p['off'] + PART_HDR:p['off'] + PART_HDR + 90]
        if blk != make_override(hdr, body):
            raise AssertionError(f'{name} cert2 override mismatch')
        log(f'cert2 after {name}: override verified at file offset {p["off"] + PART_HDR:#x}')

    # optional diff vs reference unlock image
    if reference_path:
        ref = Path(reference_path).read_bytes()
        if len(ref) != len(out):
            log(f'[warn] reference size {len(ref):#x} != output size {len(out):#x}')
        n = min(len(ref), len(out))
        diffs = [i for i in range(n) if ref[i] != out[i]]
        # coalesce
        ranges = []
        for i in diffs:
            if ranges and i == ranges[-1][1] + 1:
                ranges[-1][1] = i
            else:
                ranges.append([i, i])
        log(f'reference: {reference_path}')
        log(f'byte diffs vs reference: {len(diffs)} in {len(ranges)} ranges')
        for s, e in ranges:
            log(f'  {s:#010x}-{e:#010x} len={e-s+1}')
        # expected: keys (2*256) + two body hashes (2*32) = 576
        if len(diffs) not in range(0, 700):
            log('[warn] unexpected number of diffs; inspect the ranges above')

    return bytes(out), '\n'.join(report) + '\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--official', required=True, help='official lk partition image')
    ap.add_argument('--out', required=True, help='output 16MB image')
    ap.add_argument('--modulus', required=True,
                    help='modulus hex (512 chars) or file containing Modulus=...')
    ap.add_argument('--reference', help='optional existing unlock image for diff check')
    args = ap.parse_args()

    mod = load_modulus(args.modulus)
    img, report = build(Path(args.official), mod, args.reference)
    Path(args.out).write_bytes(img)
    Path(args.out + '.report.txt').write_text(report, encoding='utf-8')
    print(f'\nwrote {args.out} ({len(img):#x} bytes)')
    print(f'wrote {args.out}.report.txt')


if __name__ == '__main__':
    main()
