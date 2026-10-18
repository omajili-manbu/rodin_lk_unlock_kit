# 07 — 故障排查

## 刷机/解锁前

### 设备是不是 rodin？

```bash
adb shell getprop ro.product.device
fastboot getvar product
```

不是 `rodin` 就不要继续。

### 版本是 303 还是 304？

```bash
fastboot getvar version-bootloader
```

或者看系统版本。303 用 `images/rodin_303_our_lk.img`，304 用
`images/rodin_304_our_lk.img`。**不要混用。**

### 有没有 anti-rollback？

```bash
fastboot getvar anti
```

`anti: 1` 表示不要降级。用错版本/降级可能直接无法启动。

### 有没有备份 lk_a/lk_b？

没有就先备份：

```bash
adb shell su -c 'dd if=/dev/block/by-name/lk_a of=/sdcard/lk_a_backup.img bs=1M'
adb shell su -c 'dd if=/dev/block/by-name/lk_b of=/sdcard/lk_b_backup.img bs=1M'
adb pull /sdcard/lk_a_backup.img
adb pull /sdcard/lk_b_backup.img
```

## 刷写阶段

### `dd: /dev/block/by-name/lk_a: No such file or directory`

先确认真实块设备：

```bash
adb shell su -c 'ls -l /dev/block/by-name/ | grep -i lk'
```

不同系统可能是 `/dev/block/by-name/lk_a`，也可能是
`/dev/block/platform/.../by-name/lk_a`。**确认目标再写。**

### 写完不启动 / 黑屏 / 一直重启

可能原因：

- 镜像版本不对（303 ↔ 304）；
- 写错了分区；
- 写入了不完整的镜像；
- preloader 不接受修改后的 lk（已修补的版本）。

处理：

1. 尽量进 bootloader/fastboot；
2. 用备份或官方 `lk.img` 写回两个槽；
3. 不行则 EDL/授权维修；
4. 不要反复盲刷。

### 官方镜像哪里来？

对应版本的 fastboot 固件包里有 `lk.img`（或可从完整分区镜像提取）。仓库的
`images/manifest.json` 里有官方基座的 SHA-256，可用于确认版本。

## token/签名阶段

### `fastboot stage` 显示 `(0 KB)`

正常。签名文件是 256 字节，按 KB 显示为 0。确认文件大小：

```bash
ls -l unlock.sig    # 256
```

### `token sig decrypt failed`

- token 解码错误（拼接方式/换行/截断）；
- token 已过期（challenge 重置）；
- 镜像公钥和签名私钥不匹配；
- 签名不是裸 PKCS#1 type-1（例如误用了 `openssl dgst -sign`）。

先：

```bash
python3 tools/sign_token.py --token-file token.txt -o unlock.sig --raw
```

看解码后的 token 是否 `magic=5501`、长度约 80、包含 `rodin`。不对就换
`--decode concat-bytes` / `concat-b64` 再试。

### `[unlock_token]no token found!`

解码后的数据不是 token（可能只解出了 token1，或拼接方式错）。用 `--decode`
指定拼接方式，或检查 `token.txt` 是否完整包含两行。

### `Failed to set lock state`

常见原因：

- 没先 `stage` 就执行了 `oem unlock`；
- token 过期；
- 之前误执行过 `oem unlock`，challenge 已重置。

处理：重新 `get_token` → 立即签名 → `stage` → `oem unlock`。不要重复盲试。

### `cpuid mismatch` / `device name mismatch`

token 不是这台设备的，或 token 被截断/拼接错。重新取 token，确认设备 ID 是
`rodin`。

### `token verify fail! Can not be write into rpmb!`

可能和 RPMB/锁定状态有关。先确认：

- token 是当前槽、当前 challenge 的；
- 设备没有处于异常锁定状态；
- 没有跨槽复用 token；
- 重新解锁流程。

如果持续失败，先恢复官方 lk，确认设备状态，再重新开始。

### `fastboot oem lks` 不是 0

解锁没有真正生效。看 `oem unlock` 的输出；重新取 token、签名、stage、unlock。
不要在没 stage 的情况下反复 `oem unlock`。

### token 可以跨槽/跨重启用吗？

不能。每个槽、每次 challenge 都要重新取 token。token 与槽位绑定，重启/切槽/
误执行 `oem unlock` 都会重置 challenge。

## 签名工具/环境

### `python3: command not found`

Windows 上可以装 Python 3，或者用 WSL。工具只用标准库，不需要 pip 安装。

### `No such file: keys/rodin_unlock_priv.pem`

从仓库根目录运行，或用 `-k` 指定私钥路径：

```bash
python3 tools/sign_token.py -k /path/to/rodin_unlock_priv.pem --token-file token.txt -o unlock.sig
```

### `payload too long`

token 解码后超过了 245 字节（RSA-2048 type-1 的上限）。rodin 的 token 约 80 字节；
如果解出很长一段，说明拼接/解码错了。

### `bad PKCS#1 type-1 padding`

签名数据损坏，或不是用本仓库的私钥签的。重新签，确认 `unlock.sig` 是二进制
256 字节。

## 其他

### 私钥公开，会不会被别人用来解锁我的设备？

只有刷了本仓库镜像的设备会认这个公钥。要独占私钥，请用
[CUSTOM_KEY.md](CUSTOM_KEY.md) 重建。详见 [08-faq.md](08-faq.md)。

### 可以回锁吗？

本仓库不提供回锁流程。`fastboot oem lock` 的行为和风险因版本/状态而异，可能
导致无法启动。不要在没有完整备份和验证流程的情况下尝试。

### 可以用于 305 或其他机型吗？

不支持。偏移、cert2 布局、preloader 行为都可能不同，可能变砖。
