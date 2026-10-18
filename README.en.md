# rodin_lk_unlock_kit

> Offline bootloader unlock kit for the Redmi Turbo 4 (rodin): self-built `lk`
> images, a publicly shared signing key, and a fully offline token signer.
> No cloud service, no access code.

![license](https://img.shields.io/badge/license-AGPL--3.0-blue)
![device](https://img.shields.io/badge/device-Redmi%20Turbo%204%20(rodin)-orange)
![unlock](https://img.shields.io/badge/unlock-offline-success)
![versions](https://img.shields.io/badge/versions-303%20%7C%20304-informational)

## ⚠️ Read first

- Use this only on devices you own or are explicitly authorized to modify.
- Unlocking/flashing may wipe data, brick the device, void the warranty, and
  may conflict with anti-rollback. Use at your own risk.
- **The private key in this repository is intentionally public.** Anyone can
  sign unlock tokens for devices flashed with these images. If you want a key
  only you control, generate your own and rebuild (see
  [docs/CUSTOM_KEY.md](docs/CUSTOM_KEY.md)).
- This is not a screen-lock/account/FRP bypass. It requires physical access and
  usually wipes data.
- Only Redmi Turbo 4 (rodin) 303 and 304 are supported.

Full disclaimer: [DISCLAIMER.md](DISCLAIMER.md).

## What it does

The stock `lk` verifies a bootloader unlock token with an embedded RSA-2048
public key. This kit:

1. replaces the unlock-token public modulus in `lk` and `aee` with our own
   (exponent remains 65537);
2. inserts a 90-byte ASN.1 `0xA0` hash-override block before the `cert2` DER of
   `lk` and `aee`, carrying the new image SHA-256 so the preloader accepts the
   modified images; the original `cert2` DER and signature are untouched;
3. ships an offline token signer that uses the (publicly shared) private key.

No code is changed: only two 256-byte moduli and two cert2 hash-override
blocks differ from the official images.

## Supported versions

| Version | Image | Size | SHA-256 |
|---|---|---|---|
| 303 | `images/rodin_303_our_lk.img` | 16,777,216 | `187a890b462d843dc1e0e391015130d24d8ed1c2f795e7bf4aed181ef3475d16` |
| 304 | `images/rodin_304_our_lk.img` | 16,777,216 | `e0ff77c7bbd814b3fee671655bb189ddf3fe3cf3846e264db00d6ec3d2d48242` |

Do not mix versions. Check your firmware and anti-rollback state first.

## Quick start

```bash
git clone https://github.com/omajili-manbu/rodin_lk_unlock_kit.git
cd rodin_lk_unlock_kit

(cd images && sha256sum -c SHA256SUMS.txt)
python3 tools/verify_our_lk.py --all
python3 tools/sign_token.py --self-test
```

Flash the matching image to **both** `lk_a` and `lk_b` (root + `dd`; adjust the
block-device paths and verify them first):

```bash
IMG=images/rodin_304_our_lk.img
adb push "$IMG" /data/local/tmp/our_lk.img
adb shell su -c 'dd if=/data/local/tmp/our_lk.img of=/dev/block/by-name/lk_a bs=1M'
adb shell su -c 'dd if=/data/local/tmp/our_lk.img of=/dev/block/by-name/lk_b bs=1M'
adb shell su -c 'sync'
```

Unlock each slot with a freshly obtained token:

```bash
fastboot getvar current-slot
fastboot oem get_token
# save the two token lines to token.txt
python3 tools/sign_token.py --token-file token.txt -o unlock.sig --raw
fastboot stage unlock.sig
fastboot oem unlock
fastboot oem lks        # expect 0
```

The token is challenge-bound: get it, sign it, and use it immediately. Do not
reboot or run another `oem` command in between. `fastboot stage` showing
`(0 KB)` is normal; the signature is 256 bytes.

## Verification

```bash
python3 tools/verify_our_lk.py --all
python3 tools/sign_token.py --self-test
```

Public key fingerprint (SPKI DER SHA-256):

```
ca6b606035ebe83cddd515a3d47f2e5f5b396c37d38edc0a6027afed22ebc704
```

## Documentation

- [Overview](docs/01-overview.md)
- [Principle and image format](docs/02-principle.md)
- [Building from official images](docs/03-build.md)
- [Token and offline signing](docs/04-sign-token.md)
- [Flashing and dual-slot unlock](docs/05-flash-unlock.md)
- [Verification](docs/06-verify.md)
- [Troubleshooting](docs/07-troubleshooting.md)
- [FAQ](docs/08-faq.md)
- [Custom key](docs/CUSTOM_KEY.md)

## Credits

- Public MTK cert2 ASN.1 hash-override research:
  [kasnria001/pwnage24mtk](https://github.com/kasnria001/pwnage24mtk)
- Background: [CVE-2023-20696](https://cve.komodosec.com/cve?id=CVE-2023-20696)
- The MTK modding community and all public reverse-engineering material.

Not affiliated with Xiaomi, Redmi, MediaTek, or HyperOS.

## License

Scripts and documentation: **AGPL-3.0-only** (see [LICENSE](LICENSE)). Firmware
images in `images/` are vendor-derived and are **not AGPL-3.0 licensed**; see
[NOTICE](NOTICE). The signing key in `keys/` is project-generated and
intentionally public; it is provided as a functional artifact (see
[keys/README.md](keys/README.md)).

If you modify this code and offer it as a network service, AGPL-3.0 requires
you to offer the corresponding source to its users.
