# Security policy

## The private key is public by design

`keys/rodin_unlock_priv.pem` is **intentionally published**. It is a key
generated for this project, not a leaked Xiaomi/MediaTek credential. It only
signs unlock tokens for the modified LK images in this repository.

This means:

- Anyone can sign tokens for devices flashed with these images. That is the
  intended feature: offline unlocking without a server.
- The key cannot unlock stock firmware, decrypt user data, or bypass screen
  locks/accounts/FRP.
- If you want a signing key that only you control, generate your own and rebuild
  the images — see [docs/CUSTOM_KEY.md](docs/CUSTOM_KEY.md).

**Please do not report the committed PEM as a leaked secret.** If GitHub's
secret scanning flags it, it is expected for this project: the key is
project-generated and intentionally public. The repository owner can
acknowledge it in the GitHub UI.

## Reporting other issues

For vulnerabilities in the scripts (for example, unsafe file handling or a
verification bypass), please open a GitHub Security Advisory or an issue. Do not
include personal device identifiers, tokens, or private data in reports.

## Scope

In scope:

- `tools/*.py` correctness and safety issues;
- verification logic in `tools/verify_our_lk.py`;
- documentation errors that could cause a user to brick a device.

Out of scope:

- The fact that the signing key is public (intended);
- Vendor firmware vulnerabilities in general;
- Devices or firmware versions not covered by this repository.

## Supported versions

- Redmi Turbo 4 (rodin), HyperOS 3.0.303 and 3.0.304 lk images.
- Other versions/models are unsupported and may use different offsets or a
  patched preloader.
