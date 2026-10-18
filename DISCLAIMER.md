# DISCLAIMER

**Use this project only on devices you own or are explicitly authorized to
modify.**

Bootloader unlocking and flashing a modified `lk` partition are invasive
operations. By using anything in this repository you acknowledge and accept
the following:

1. **Data loss.** Unlocking may wipe userdata/metadata. Back up anything
   important before starting.
2. **Brick risk.** A wrong image, wrong partition, wrong version, interrupted
   flash, or incompatible preloader can make the device unbootable. Recovery may
   require EDL/authorized service tools.
3. **Warranty and support.** Unlocking may void the manufacturer's warranty and
   may violate the vendor's terms or service policy.
4. **Anti-rollback.** The device may have anti-rollback (`anti: 1`). Do not
   downgrade firmware versions or mix 303/304 images. Use the image that matches
   the installed firmware.
5. **Patched devices.** This kit relies on a preloader certificate-parsing
   behavior that may be fixed in newer firmware. No guarantee is made that it
   works on any version other than the tested 303/304 `rodin` builds.
6. **No account/FRP bypass.** This is a bootloader unlock kit, not a way to
   bypass screen locks, Google/Xiaomi accounts, FRP, or stolen-device
   protections. It requires physical access and usually wipes data.
7. **Public signing key.** The private key in `keys/` is intentionally public.
   Anyone can sign unlock tokens for devices flashed with these images. If you
   want a key only you control, rebuild the images with your own key.
8. **No affiliation.** This project is not affiliated with Xiaomi, Redmi,
   MediaTek, or HyperOS. Trademarks belong to their owners.
9. **Local laws.** Bootloader unlocking, firmware modification, and
   redistribution may be regulated where you live. You are responsible for
   complying with applicable laws.
10. **No warranty / no liability.** The software, images, keys, and
    documentation are provided "as is", without warranty of any kind. The
    authors are not liable for damage, data loss, bricked devices, warranty
    denial, or any other consequence.

**Do not use this project on a device you do not own or have not been
authorized to modify. Do not use it to facilitate theft, resale of stolen
devices, or bypassing account/FRP protections.**
