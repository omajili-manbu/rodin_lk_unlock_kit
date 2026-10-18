---
name: Bug report
about: Report a problem with the scripts, documentation, or image verification
title: "[bug] "
labels: bug
---

**Do not paste real unlock tokens, device serial numbers, or personal data.**

## Environment

- OS / shell:
- Python version (`python3 --version`):
- Image used (`rodin_303_our_lk.img` / `rodin_304_our_lk.img` / custom):
- Image SHA-256 (`sha256sum images/...`):

## Command run

```text
(paste the command)
```

## Expected behavior

## Actual behavior / error

```text
(paste the output; redact serial numbers/tokens)
```

## Device state (optional, redact serial)

```text
fastboot getvar product
fastboot getvar version-bootloader
fastboot getvar current-slot
fastboot getvar anti
fastboot getvar unlocked
fastboot oem lks
```

## Additional context
