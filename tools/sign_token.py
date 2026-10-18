#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 omajili-manbu
"""
Offline unlock-token signer for the rodin LK images in this repository.

Validated against old working signatures from the third-party unlock service:
the LK verifies a raw RSA PKCS#1 v1.5 type-1 "signature" over the **base64
token string** (token1 + token2, about 80 ASCII chars), then base64-decodes the
recovered string into the binary token (magic 0x5501 ... 'rodin' ...).

    EM  = 00 01 FF...FF 00 || base64(token1 + token2)
    sig = EM^d mod n          (256 bytes)

It does NOT sign the decoded binary. The old working `unlock_a.sig` /
`unlock_b.sig` recover to an 80-char base64 string; decoding that yields a
59-byte token with magic 0x5501 and TLV records for the challenge, `rodin`,
and the fixed suffix.

Usage (Python 3.8+, standard library only):
  # two base64 lines from `fastboot oem get_token`
  python3 tools/sign_token.py --token1 '<token1>' --token2 '<token2>' -o unlock.sig

  # paste the whole fastboot output into a file
  python3 tools/sign_token.py --token-file token.txt -o unlock.sig

  # a single concatenated base64 token
  python3 tools/sign_token.py --token '<token1><token2>' -o unlock.sig

  # you already have the decoded binary; base64-encode it and sign that string
  python3 tools/sign_token.py --token-hex 5501... -o unlock.sig

  # self-test (synthetic token, no device needed)
  python3 tools/sign_token.py --self-test

The private key in this repository is intentionally public (see keys/README.md).
It only signs tokens for the modified LK images in this repository. If you want
a key only you control, build the images with your own key (docs/CUSTOM_KEY.md).
Signing is fully local; nothing is sent anywhere.
"""

import argparse
import base64
import binascii
import hashlib
import re
import sys
from pathlib import Path

DEFAULT_KEY = Path(__file__).resolve().parent.parent / 'keys' / 'rodin_unlock_priv.pem'
RSA_BYTES = 256


# --------------------------------------------------------------------------
# minimal DER / RSA private key parsing (PKCS#1 and PKCS#8, unencrypted)
# --------------------------------------------------------------------------
def read_tlv(buf, off):
    if off + 2 > len(buf):
        raise ValueError('DER: truncated header')
    tag = buf[off]
    ln = buf[off + 1]
    hdr = 2
    if ln & 0x80:
        n = ln & 0x7F
        if n == 0 or n > 4:
            raise ValueError('DER: bad length')
        ln = int.from_bytes(buf[off + 2:off + 2 + n], 'big')
        hdr = 2 + n
    end = off + hdr + ln
    if end > len(buf):
        raise ValueError('DER: length exceeds buffer')
    return tag, buf[off + hdr:end], end


def parse_rsaprivkey(der):
    tag, body, _ = read_tlv(der, 0)
    if tag != 0x30:
        raise ValueError('RSAPrivateKey: not a SEQUENCE')
    vals = []
    off = 0
    while off < len(body):
        t, v, off = read_tlv(body, off)
        if t != 0x02:
            raise ValueError('RSAPrivateKey: expected INTEGER')
        vals.append(int.from_bytes(v, 'big'))
    if len(vals) < 4:
        raise ValueError('RSAPrivateKey: too few fields')
    return vals[1], vals[2], vals[3]  # n, e, d


def load_private_key(path):
    text = Path(path).read_text()
    m = re.search(r'-----BEGIN ([A-Z ]+)-----(.*?)-----END \1-----', text, re.S)
    if not m:
        raise ValueError('no PEM block found')
    label, b64 = m.group(1), ''.join(m.group(2).split())
    der = base64.b64decode(b64, validate=True)
    if label == 'RSA PRIVATE KEY':
        return parse_rsaprivkey(der)
    if label == 'PRIVATE KEY':
        tag, body, _ = read_tlv(der, 0)
        if tag != 0x30:
            raise ValueError('PrivateKeyInfo: not a SEQUENCE')
        off = 0
        t, v, off = read_tlv(body, off)  # version
        t, v, off = read_tlv(body, off)  # AlgorithmIdentifier
        t, v, off = read_tlv(body, off)  # OCTET STRING
        if t != 0x04:
            raise ValueError('PrivateKeyInfo: expected OCTET STRING')
        return parse_rsaprivkey(v)
    raise ValueError(f'unsupported PEM label {label!r} '
                     '(decrypt the key or use an unencrypted key)')


# --------------------------------------------------------------------------
# raw RSA PKCS#1 v1.5 type-1 sign / verify
# --------------------------------------------------------------------------
def pkcs1_type1_em(payload: bytes, k: int = RSA_BYTES) -> bytes:
    if len(payload) > k - 11:
        raise ValueError(f'payload too long: {len(payload)} > {k - 11}')
    return b'\x00\x01' + b'\xff' * (k - 3 - len(payload)) + b'\x00' + payload


def raw_sign(payload, n, d):
    k = (n.bit_length() + 7) // 8
    em = pkcs1_type1_em(payload, k)
    return pow(int.from_bytes(em, 'big'), d, n).to_bytes(k, 'big')


def raw_verify(sig, n, e):
    k = (n.bit_length() + 7) // 8
    if len(sig) != k:
        raise ValueError(f'signature length {len(sig)} != {k}')
    em = pow(int.from_bytes(sig, 'big'), e, n).to_bytes(k, 'big')
    if len(em) < 11 or em[0] != 0 or em[1] != 1:
        raise ValueError('bad PKCS#1 type-1 prefix')
    i = 2
    while i < len(em) and em[i] == 0xFF:
        i += 1
    if i < 10 or i >= len(em) or em[i] != 0:
        raise ValueError('bad PKCS#1 type-1 padding')
    return em[i + 1:]


# --------------------------------------------------------------------------
# token parsing: sign the base64 ASCII string, validate the decoded binary
# --------------------------------------------------------------------------
def norm_b64(s: str) -> str:
    return ''.join(s.split())


def parse_token_lines(text: str):
    tokens = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.search(r'token\s*:\s*(.+)$', line, re.I)
        cand = m.group(1) if m else line
        cand = norm_b64(cand)
        if len(cand) >= 16 and re.fullmatch(r'[A-Za-z0-9+/=_-]+', cand):
            tokens.append(cand.replace('-', '+').replace('_', '/'))
    return tokens


def token_string_from_args(args) -> str:
    if args.token_hex:
        raw = bytes.fromhex(''.join(args.token_hex.split()))
        return base64.b64encode(raw).decode('ascii')
    if args.token:
        return norm_b64(args.token)
    if args.token1 or args.token2:
        return norm_b64(args.token1 or '') + norm_b64(args.token2 or '')
    if args.token_file:
        toks = parse_token_lines(Path(args.token_file).read_text(errors='replace'))
        if len(toks) >= 2:
            return toks[0] + toks[1]
        if len(toks) == 1:
            return toks[0]
        raise ValueError('no token line found in token-file')
    raise ValueError('provide --token1/--token2, --token, --token-hex, or --token-file')


def inspect_token(s: str):
    print(f'token string: {len(s)} chars')
    print(f'  {s}')
    print(f'  sha256(string): {hashlib.sha256(s.encode()).hexdigest()}')
    try:
        raw = base64.b64decode(s, validate=True)
    except (binascii.Error, ValueError) as e:
        print(f'  [warn] base64 decode failed: {e}')
        return None
    print(f'  decoded binary: {len(raw)} bytes')
    print(f'  hex: {raw.hex()}')
    print(f'  ascii: {"".join(chr(c) if 32 <= c < 127 else "." for c in raw)}')
    print(f'  magic: {raw[:2].hex()}  rodin: {b"rodin" in raw}  '
          f'length<=245: {len(s) <= 245}')
    if raw[:2] not in (b'\x55\x01', b'\x01\x55'):
        print('  [warn] decoded token does not start with magic 0x5501')
    if b'rodin' not in raw:
        print('  [warn] decoded token does not contain "rodin"')
    return raw


# --------------------------------------------------------------------------
def self_test():
    n, e, d = load_private_key(DEFAULT_KEY)
    print(f'key: {n.bit_length()} bits, e={e}, '
          f'n={n.to_bytes((n.bit_length() + 7) // 8, "big").hex()[:16]}...')
    raw = (b'\x55\x01\x02\x37\x01\x10' + bytes(range(8)) +
           b'\x03\x05rodin' + b'\x02\x1c' + bytes(range(28)))
    s = base64.b64encode(raw).decode()
    print(f'synthetic token string: {len(s)} chars, decoded {len(raw)} bytes')
    sig = raw_sign(s.encode(), n, d)
    rec = raw_verify(sig, n, e)
    ok = rec == s.encode()
    print(f'self-test: sig={len(sig)}B verify={ok} '
          f'decoded_magic={base64.b64decode(rec)[:2].hex()}')
    if not ok:
        raise SystemExit('SELF TEST FAILED')
    print('SELF TEST OK')


def main():
    ap = argparse.ArgumentParser(
        description='Sign the base64 token string with raw RSA PKCS#1 v1.5 type-1. '
                    "This repo's signing key is public by design.")
    ap.add_argument('--token1', help='first base64 token from fastboot oem get_token')
    ap.add_argument('--token2', help='second base64 token')
    ap.add_argument('--token', help='single concatenated base64 token string')
    ap.add_argument('--token-hex', help='raw decoded token bytes as hex (will be base64-encoded)')
    ap.add_argument('--token-file', help='file containing fastboot output or token lines')
    ap.add_argument('-k', '--key', default=str(DEFAULT_KEY), help='private key PEM')
    ap.add_argument('-o', '--out', default='unlock.sig', help='output signature file (256 B)')
    ap.add_argument('--raw', action='store_true',
                    help='also write the base64 token string to <out>.token.txt')
    ap.add_argument('--verify', action='store_true',
                    help='verify <out> against the token string and exit (no signing)')
    ap.add_argument('--self-test', action='store_true', help='run a synthetic sign/verify test')
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return

    token_str = token_string_from_args(args)
    if not token_str:
        raise SystemExit('empty token string')
    if len(token_str) > 245:
        raise SystemExit(f'token string too long for 2048-bit PKCS#1 v1.5: '
                         f'{len(token_str)} > 245')
    inspect_token(token_str)

    n, e, d = load_private_key(args.key)
    if n.bit_length() != 2048:
        raise SystemExit(f'key is {n.bit_length()} bits, expected 2048')
    if e != 65537:
        raise SystemExit(f'key e={e}, expected 65537')

    out = Path(args.out)
    payload = token_str.encode('ascii')
    if args.verify:
        sig = out.read_bytes()
        rec = raw_verify(sig, n, e)
        print(f'verify {out}: sig={len(sig)}B recovered={len(rec)}B match={rec == payload}')
        if rec != payload:
            raise SystemExit('VERIFY FAILED')
        return

    sig = raw_sign(payload, n, d)
    out.write_bytes(sig)
    if args.raw:
        Path(str(out) + '.token.txt').write_text(token_str)
    rec = raw_verify(sig, n, e)
    print(f'signature: {out} ({len(sig)} bytes)')
    print(f'local verify: {"OK" if rec == payload else "FAILED"}')
    if rec != payload:
        raise SystemExit('SIGN/VERIFY MISMATCH')
    print(f'done. Now: fastboot stage {out} && fastboot oem unlock')


if __name__ == '__main__':
    main()
