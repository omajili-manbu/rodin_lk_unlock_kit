#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-only
# Copyright (C) 2026 omajili-manbu
"""
Offline unlock-token signer for our own rodin LK.

The LK verifies the token as a raw RSA PKCS#1 v1.5 type-1 "signature":
    EM = 00 01 FF...FF 00 || token_payload
    sig = EM^d mod n          (256 bytes)
It then parses the recovered token payload (TLV: magic 0x5501 ...).

Usage (WSL/Linux/macOS, Python 3.8+):
  # two base64 lines from `fastboot oem get_token`
  python3 tools/sign_token.py --token1 '<token1>' --token2 '<token2>' -o unlock.sig

  # paste the whole fastboot output into a file
  python3 tools/sign_token.py --token-file token.txt -o unlock.sig

  # a single concatenated base64 token
  python3 tools/sign_token.py --token '<token1><token2>' -o unlock.sig

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
KEY_BYTES = 256


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
    # version, n, e, d, ...
    return vals[1], vals[2], vals[3]


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
        # PrivateKeyInfo ::= SEQUENCE { version, AlgorithmIdentifier, OCTET STRING }
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
def pkcs1_type1_em(payload: bytes, k: int = KEY_BYTES) -> bytes:
    if len(payload) > k - 11:
        raise ValueError(f'payload too long: {len(payload)} > {k - 11}')
    ps = b'\xff' * (k - 3 - len(payload))
    return b'\x00\x01' + ps + b'\x00' + payload


def raw_sign(payload, n, d):
    k = (n.bit_length() + 7) // 8
    em = pkcs1_type1_em(payload, k)
    sig = pow(int.from_bytes(em, 'big'), d, n)
    return sig.to_bytes(k, 'big')


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
# token decoding
# --------------------------------------------------------------------------
def b64decode_loose(s: str) -> bytes:
    s = ''.join(s.split())
    s = s.replace('-', '+').replace('_', '/')
    s += '=' * (-len(s) % 4)
    return base64.b64decode(s, validate=False)


def parse_token_lines(text: str):
    """Extract base64 tokens from `fastboot oem get_token` output or plain lines."""
    tokens = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.search(r'token\s*:\s*(.+)$', line, re.I)
        if m:
            cand = m.group(1).strip()
            cand = ''.join(cand.split())
            if re.fullmatch(r'[A-Za-z0-9+/=_-]+', cand):
                tokens.append(cand)
            continue
        # plain line: accept only if it is entirely base64-ish and long enough
        cand = ''.join(line.split())
        if len(cand) >= 16 and re.fullmatch(r'[A-Za-z0-9+/=_-]+', cand):
            tokens.append(cand)
    return tokens


def token_candidates(tokens):
    cands = []
    if len(tokens) >= 2:
        a, b = tokens[0], tokens[1]
        try:
            cands.append(('concat-b64', b64decode_loose(a + b)))
        except (binascii.Error, ValueError):
            pass
        try:
            cands.append(('concat-bytes', b64decode_loose(a) + b64decode_loose(b)))
        except (binascii.Error, ValueError):
            pass
        try:
            cands.append(('concat-strip-pad', b64decode_loose(a.rstrip('=') + b.rstrip('='))))
        except (binascii.Error, ValueError):
            pass
    elif len(tokens) == 1:
        try:
            cands.append(('single', b64decode_loose(tokens[0])))
        except (binascii.Error, ValueError):
            pass
    # de-duplicate
    out = []
    seen = set()
    for name, data in cands:
        if data not in seen:
            seen.add(data)
            out.append((name, data))
    return out


def token_score(data: bytes):
    s = 0
    if data[:2] in (b'\x55\x01', b'\x01\x55'):
        s += 100
    if b'rodin' in data:
        s += 50
    if 40 <= len(data) <= 200:
        s += 10
    if len(data) <= KEY_BYTES - 11:
        s += 5
    return s


def describe(data: bytes):
    printable = ''.join(chr(c) if 32 <= c < 127 else '.' for c in data[:48])
    return f'len={len(data)} magic={data[:2].hex()} ascii="{printable}"'


def choose_token(tokens, mode='auto'):
    cands = token_candidates(tokens)
    if not cands:
        raise ValueError('failed to base64-decode the token input')
    scored = sorted(((token_score(d), n, d) for n, d in cands), reverse=True,
                    key=lambda x: (x[0], len(x[2])))
    print('token decode candidates:')
    for sc, name, data in scored:
        print(f'  [{sc:3d}] {name:18s} {describe(data)}')
    if mode != 'auto':
        for sc, name, data in scored:
            if name == mode:
                print(f'using --decode {mode}')
                return data
        raise ValueError(f'decode mode {mode!r} not available; '
                         f'choices: {[n for _, n, _ in scored]}')
    best = scored[0]
    if best[0] < 100:
        print('[warn] no candidate starts with magic 0x5501; check the token input.')
    return best[2]


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def self_test():
    n, e, d = load_private_key(DEFAULT_KEY)
    print(f'key: {n.bit_length()} bits, e={e}, n={n.to_bytes(KEY_BYTES, "big")[:8].hex()}...')
    # synthetic token: magic 0x5501 + type + length + 'rodin' + 32-byte challenge
    payload = b'\x55\x01' + b'\x02\x30' + b'rodin' + bytes(range(32)) + b'\x00' * 10
    sig = raw_sign(payload, n, d)
    rec = raw_verify(sig, n, e)
    print(f'self-test: payload={len(payload)}B sig={len(sig)}B verify={rec == payload}')
    if rec != payload:
        raise SystemExit('SELF TEST FAILED')
    print('SELF TEST OK')


def main():
    ap = argparse.ArgumentParser(
        description='Offline unlock-token signer (raw RSA PKCS#1 v1.5 type-1). '
                    "This repo's signing key is public by design.")
    ap.add_argument('--token1', help='first base64 token from fastboot oem get_token')
    ap.add_argument('--token2', help='second base64 token')
    ap.add_argument('--token', help='single concatenated base64 token')
    ap.add_argument('--token-hex', help='raw token bytes as hex (no base64 decoding)')
    ap.add_argument('--token-file', help='file containing fastboot output or token lines')
    ap.add_argument('--decode', default='auto',
                    choices=['auto', 'concat-bytes', 'concat-b64', 'concat-strip-pad', 'single'],
                    help='token decode strategy (default: auto)')
    ap.add_argument('-k', '--key', default=str(DEFAULT_KEY), help='private key PEM')
    ap.add_argument('-o', '--out', default='unlock.sig', help='output signature file (256 B)')
    ap.add_argument('--raw', action='store_true',
                    help='also write the decoded token to <out>.token.bin')
    ap.add_argument('--verify', action='store_true',
                    help='verify <out> against the token and exit (no signing)')
    ap.add_argument('--self-test', action='store_true', help='run a synthetic sign/verify test')
    args = ap.parse_args()

    if args.self_test:
        self_test()
        return

    if args.token_hex:
        token = bytes.fromhex(''.join(args.token_hex.split()))
        print(f'token: {describe(token)}')
        print(f'token sha256: {hashlib.sha256(token).hexdigest()}')
    else:
        tokens = []
        if args.token_file:
            tokens += parse_token_lines(Path(args.token_file).read_text(errors='replace'))
        if args.token1:
            tokens.append(args.token1)
        if args.token2:
            tokens.append(args.token2)
        if args.token:
            tokens.append(args.token)
        if not tokens:
            ap.error('provide --token1/--token2, --token, --token-hex, or --token-file')

        token = choose_token(tokens, args.decode)
        print(f'token: {describe(token)}')
        print(f'token sha256: {hashlib.sha256(token).hexdigest()}')

    n, e, d = load_private_key(args.key)
    if n.bit_length() != 2048:
        raise SystemExit(f'key is {n.bit_length()} bits, expected 2048')
    if e != 65537:
        raise SystemExit(f'key e={e}, expected 65537')

    out = Path(args.out)
    if args.verify:
        sig = out.read_bytes()
        rec = raw_verify(sig, n, e)
        print(f'verify {out}: sig={len(sig)}B recovered={len(rec)}B match={rec == token}')
        if rec != token:
            raise SystemExit('VERIFY FAILED')
        return

    sig = raw_sign(token, n, d)
    out.write_bytes(sig)
    if args.raw:
        Path(str(out) + '.token.bin').write_bytes(token)
    rec = raw_verify(sig, n, e)
    print(f'signature: {out} ({len(sig)} bytes)')
    print(f'local verify: {"OK" if rec == token else "FAILED"}')
    if rec != token:
        raise SystemExit('SIGN/VERIFY MISMATCH')
    print('done. Now: fastboot stage %s && fastboot oem unlock' % out)


if __name__ == '__main__':
    main()
