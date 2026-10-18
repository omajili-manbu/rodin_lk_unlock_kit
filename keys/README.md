# keys

## The private key is public by design

`rodin_unlock_priv.pem` is **intentionally published**. This is not a leak and
not a vendor key. It was generated for this project so that everyone can sign
their own unlock tokens for the modified LK images, without any cloud service.

Because the key is public, **anyone** can sign tokens for devices flashed with
the images in `images/`. That is the point of this kit. If you want a key that
only you control, generate your own and rebuild the images with your public
modulus — see [../docs/CUSTOM_KEY.md](../docs/CUSTOM_KEY.md).

The project's original code and documentation are AGPL-3.0-only. The key
itself is a functional artifact and is provided for use with this project.

## What it can and cannot do

- It can sign an unlock token for a `rodin` device whose `lk` partition contains
  these modified images and this public modulus.
- It cannot unlock stock firmware: stock `lk` verifies tokens against Xiaomi's
  public key, not this one.
- It cannot bypass screen locks, accounts, or FRP. Bootloader unlocking is not
  an account-lock bypass; it requires physical access and usually wipes data.
- It does not affect any server or other device.

## Files

| File | Purpose |
|---|---|
| `rodin_unlock_priv.pem` | RSA-2048 private key used by `tools/sign_token.py` |
| `rodin_unlock_pub.pem` | public key |
| `modulus.txt` | public modulus in `Modulus=...` form |
| `KEY_INFO.txt` | key fingerprint, modulus, image hashes, changed offsets |

## Verify the key matches the image

```bash
python3 tools/verify_our_lk.py --all
```

This checks that the modulus appears twice in each image (lk and aee), that the
exponent is `010001`, and that the cert2 override hashes correspond to the image
body/header.

Public key fingerprint:

```
SPKI-DER SHA-256 = ca6b606035ebe83cddd515a3d47f2e5f5b396c37d38edc0a6027afed22ebc704
```

## If you generate your own key

The prebuilt images use the public key above. If you rebuild with your own key,
keep your private key secret, and publish only your public key/modulus. The
signing flow is identical; see [../docs/CUSTOM_KEY.md](../docs/CUSTOM_KEY.md).
