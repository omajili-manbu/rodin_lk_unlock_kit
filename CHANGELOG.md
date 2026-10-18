# Changelog

## v1.0.0 — 2026-10-19

Initial public release.

- Prebuilt 16MB `lk` partition images for Redmi Turbo 4 (rodin):
  - `images/rodin_303_our_lk.img`
  - `images/rodin_304_our_lk.img`
- Public RSA-2048 unlock-token signing key:
  - `keys/rodin_unlock_priv.pem` (intentionally public)
  - `keys/rodin_unlock_pub.pem`, `keys/modulus.txt`
- Offline token signer: `tools/sign_token.py`
  - raw RSA PKCS#1 v1.5 type-1 signing of the decoded token;
  - supports two base64 tokens, a combined token, a token file, or raw hex;
  - self-test and signature verification.
- Reproducible builder: `tools/build_our_lk.py`
  - from official `303lk.img` / `304lk.img`;
  - replaces the unlock-token modulus in `lk` and `aee`;
  - inserts the 90-byte cert2 `0xA0` hash-override block;
  - pads to 16MB.
- Image verifier: `tools/verify_our_lk.py`
  - checks size, GFH parts, key, exponent, cert2 dsize/override hashes;
  - optional comparison with official/reference images.
- Documentation: principle, image format, build, token signing, flashing,
  verification, troubleshooting, FAQ, custom key.
- License: AGPL-3.0-only for original code and documentation; firmware images
  remain vendor-derived (see NOTICE); the signing key is a functional artifact.
- GitHub Actions workflow to verify checksums, image structure, and signer
  self-test.
