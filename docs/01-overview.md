# 01 — 概览与范围

## 目标

为 **Redmi Turbo 4 (rodin)** 提供一个**完全离线**的 bootloader 解锁套件：

- 预先构建好的 16MB `lk` 分区镜像（303 / 304）；
- 镜像内嵌的 unlock-token 公钥属于本项目，对应私钥**公开**；
- 本地 Python 工具直接签 `fastboot oem get_token` 返回的 token；
- 不需要云端、access code、账号或网络。

## 支持范围

| 项目 | 支持 |
|---|---|
| 机型 | Redmi Turbo 4（codename `rodin`） |
| 系统 | HyperOS 3.0.303 / 3.0.304（MTK 平台） |
| 分区 | `lk`（16MB，包含 lk / aee / bl2_ext / lk_main_ / lk_dtbo 等 15 个 GFH 子镜像） |
| 解锁方式 | `fastboot oem get_token` + `fastboot stage` + `fastboot oem unlock` |
| 槽位 | 双槽，每个槽分别取 token、签名、解锁 |

**不支持**：其他机型、其他 MTK 设备、305 或更新版本（未验证；偏移/preloader
可能不同）、官方固件（官方 `lk` 不认本项目的公钥）。

## 包含内容

- `images/`：303 / 304 两版 16MB `lk` 镜像，已内置本项目公钥和 cert2 哈希覆盖块。
- `keys/`：本项目 RSA-2048 密钥对；**私钥故意公开**。
- `tools/sign_token.py`：离线签名器（纯标准库）。
- `tools/build_our_lk.py`：从官方 `lk.img` 复现构建。
- `tools/verify_our_lk.py`：镜像结构、密钥、cert2 哈希校验。
- `docs/`：原理、构建、签名、刷机、验证、故障排查、FAQ。

## 不是什么

- 不是屏幕锁/账号锁/FRP 绕过工具；
- 不是通用 MTK 解锁工具；
- 不包含小米/MTK 的私钥；
- 不保证在已修补 preloader 的设备上可用；
- 不提供变砖救援服务（只能给建议）。

## 风险

- 解锁/刷机可能清空数据、失去保修、触发 anti-rollback、变砖。
- 镜像必须与设备版本匹配（303/304），双槽都要写。
- token 必须现场取、立即签、立即用。
- 私钥公开意味着任何拿到镜像的人都能为这些设备签 token；如果你要独占，
  请用自己的密钥重建。

完整免责声明：[../DISCLAIMER.md](../DISCLAIMER.md)。

## 从这里开始

1. 确认设备和版本：[05-flash-unlock.md](05-flash-unlock.md)
2. 校验镜像：[06-verify.md](06-verify.md)
3. 了解原理：[02-principle.md](02-principle.md)
4. 签名 token：[04-sign-token.md](04-sign-token.md)
5. 自己构建/换密钥：[03-build.md](03-build.md)、[CUSTOM_KEY.md](CUSTOM_KEY.md)
