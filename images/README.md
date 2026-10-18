# images

Each image is a full 16MB dump of the `lk` partition for **Redmi Turbo 4
(rodin)**, built from the matching official `lk.img` of that firmware version.
They are not interchangeable across versions.

| Version | Image | Size | SHA-256 |
|---|---|---|---|
| 303 | `rodin_303_our_lk.img` | 16,777,216 | `187a890b462d843dc1e0e391015130d24d8ed1c2f795e7bf4aed181ef3475d16` |
| 304 | `rodin_304_our_lk.img` | 16,777,216 | `e0ff77c7bbd814b3fee671655bb189ddf3fe3cf3846e264db00d6ec3d2d48242` |

Verify before flashing:

```bash
cd images
sha256sum -c SHA256SUMS.txt
```

Or:

```bash
python3 tools/verify_our_lk.py --all
```

## How they were built

`tools/build_our_lk.py` takes the **official** `lk.img` and:

1. replaces the unlock-token RSA-2048 modulus in `lk` and `aee`
   with the public modulus in `keys/modulus.txt`;
2. inserts the 90-byte ASN.1 `0xA0` hash-override block before the `cert2`
   DER of `lk` and `aee`, containing the new body SHA-256 and the unchanged
   GFH header SHA-256;
3. pads to 16MB.

The original `cert2` DER and its signature are untouched.

The official base image hashes (for identifying your firmware dump) are in
`manifest.json`.

## Version matching

- 303 firmware → `rodin_303_our_lk.img`
- 304 firmware → `rodin_304_our_lk.img`

Check with `fastboot getvar version-bootloader` or the OS build. Do not mix
versions; the device may have anti-rollback enabled (`anti: 1`).
