# 05 — 刷入与双槽解锁

> **先读 [DISCLAIMER.md](../DISCLAIMER.md)。** 下面每一步都可能因为版本不匹配、
> 写错分区或 token 过期而让设备无法启动。先备份、先确认版本、再动手。

## 前置条件

- 设备是 **Redmi Turbo 4 (rodin)**，系统为 303 或 304；
- 已有可用的 root（用于 `dd` 写 `lk` 分区）或等效的写入方式；
- `adb` / `fastboot` 可用；
- 已下载匹配版本的镜像：303 用 `rodin_303_our_lk.img`，304 用
  `rodin_304_our_lk.img`；
- 最好先准备官方 `lk.img` 或当前分区的备份，方便恢复。

如果设备还没有 root，单靠这个 kit 不能写入 `lk`；请先用你已经验证过的 root
方案，或使用 EDL/授权工具。不要在未知状态下乱刷。

## 1. 确认设备与版本

```bash
adb shell getprop ro.product.device        # 期望 rodin
fastboot getvar product                    # 期望 rodin
fastboot getvar version-bootloader
fastboot getvar current-slot
fastboot getvar anti
fastboot getvar unlocked
fastboot oem lks                           # 0=已解锁, 1=已锁
```

- `anti` 通常为 1；不要降级版本。
- 303/304 必须和镜像匹配。混用可能触发 anti-rollback 或直接无法启动。

## 2. 备份当前 lk_a / lk_b

```bash
adb shell su -c 'ls -l /dev/block/by-name/ | grep -E "lk_a|lk_b"'

adb shell su -c 'dd if=/dev/block/by-name/lk_a of=/sdcard/lk_a_backup.img bs=1M'
adb shell su -c 'dd if=/dev/block/by-name/lk_b of=/sdcard/lk_b_backup.img bs=1M'

adb pull /sdcard/lk_a_backup.img
adb pull /sdcard/lk_b_backup.img
```

确认备份大小为 **16,777,216 字节**。把备份放在电脑上，不要只留在手机里。

## 3. 写入两个槽

> 块设备路径因设备/系统而异。**先确认** `/dev/block/by-name/lk_a` 和
> `lk_b` 存在且指向正确分区；写错会变砖。

手动方式：

```bash
IMG=images/rodin_304_our_lk.img    # 303 设备改成 303 镜像

adb push "$IMG" /data/local/tmp/our_lk.img

adb shell su -c 'dd if=/data/local/tmp/our_lk.img of=/dev/block/by-name/lk_a bs=1M'
adb shell su -c 'dd if=/data/local/tmp/our_lk.img of=/dev/block/by-name/lk_b bs=1M'
adb shell su -c 'sync'
```

或使用带确认的示例脚本：

```bash
scripts/flash_lk.sh images/rodin_304_our_lk.img \
  /dev/block/by-name/lk_a /dev/block/by-name/lk_b
```

脚本会检查镜像大小、打印 SHA-256、要求输入 `YES` 才写入。

可选：读回校验（如果允许读 `lk`）：

```bash
adb shell su -c 'dd if=/dev/block/by-name/lk_a of=/sdcard/lk_a_new.img bs=1M'
adb pull /sdcard/lk_a_new.img
sha256sum lk_a_new.img images/rodin_304_our_lk.img
```

两者应一致。

## 4. 双槽解锁

经验总结里的顺序是：**先解锁非活跃槽，再切回原卡槽解锁**（工具箱在
`a` 槽时先切到 `b` 解锁，再回 `a` 补一遍）。按你设备上验证过的顺序做；
核心是**每个槽都要独立取 token、独立签名、独立 stage + unlock**。

假设当前是 `a` 槽，要解锁 `b`：

```bash
fastboot --set-active=b
fastboot reboot bootloader
fastboot getvar current-slot        # 期望 b

fastboot oem get_token              # 记录两行 token
# 保存到 token.txt
python3 tools/sign_token.py --token-file token.txt -o unlock_b.sig --raw

fastboot stage unlock_b.sig
fastboot oem unlock
fastboot oem lks                    # 期望 0
```

然后切回 `a`，重新取 token（**必须重新取**）：

```bash
fastboot --set-active=a
fastboot reboot bootloader
fastboot getvar current-slot        # 期望 a

fastboot oem get_token
python3 tools/sign_token.py --token-file token.txt -o unlock_a.sig --raw

fastboot stage unlock_a.sig
fastboot oem unlock
fastboot oem lks                    # 期望 0
```

### 关键规则

- **token 现场取、立即签、立即用**。重启、切槽、或先执行 `oem unlock` 都会刷新
  challenge，旧 token 立即失效。
- **不要跨槽用 token**。a 槽 token 不能用于 b 槽。
- **不要在没 stage 的情况下执行 `oem unlock`**。可能导致
  `Failed to set lock state`，challenge 重置。
- `fastboot stage` 显示 `(0 KB)` 正常；签名是 256 字节。
- 如果失败：重新 `get_token`，重新签名，重新 stage，再 unlock；不要连续盲试。

## 5. 收尾

```bash
fastboot --set-active=a
fastboot reboot
```

解锁后如果进不了系统，通常需要清数据：

```bash
fastboot erase userdata
fastboot erase metadata
fastboot reboot
```

`userdata` 是 f2fs 时出现 erase 警告是正常的。**这会清空数据，先备份。**

## 6. 如果设备已经是解锁状态

刷入我们的镜像不会自动改变 `seccfg` 的锁定状态；它只是让 `lk` 以后用我们的
公钥验 token。你不需要为了“刷镜像”而重新解锁；但以后如果要重新解锁/换槽，
token 必须用本仓库的 `tools/sign_token.py` 和 `keys/` 里的私钥签。

## 7. 恢复/救砖

先不要重复刷写。按情况处理：

- 能进 bootloader：把官方 `lk.img`（或备份的 `lk_a_backup.img`）用同样的
  `dd` 方法写回两个槽，`sync`，重启。
- 不能进 bootloader/fastboot：尝试 EDL/授权维修工具；这通常需要额外的
  firehose/授权文件，本仓库不提供。
- 不确定原因时，保留现场，记录 `fastboot getvar all`、屏幕/串口信息，再求助。

## 8. 不要做的事

- 不要把 303 镜像刷到 304 设备（或反过来）。
- 不要降级系统版本（`anti: 1`）。
- 不要在没备份 `lk_a`/`lk_b` 的情况下开始。
- 不要写错块设备。
- 不要在 token 过期后复用旧签名。
- 不要用来源不明的 `lk.img`。
