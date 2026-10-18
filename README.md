# rodin_lk_unlock_kit

> 红米 Turbo 4（rodin）离线 BL 解锁套件：自制 `lk` 镜像、公开签名私钥、离线 token 签名工具。  
> 不需要云端、不需要 access code，拿到镜像和 token 就能本地签名。

![license](https://img.shields.io/badge/license-AGPL--3.0-blue)
![device](https://img.shields.io/badge/device-Redmi%20Turbo%204%20(rodin)-orange)
![unlock](https://img.shields.io/badge/unlock-offline-success)
![versions](https://img.shields.io/badge/versions-303%20%7C%20304-informational)

---

## ⚠️ 先读

- **仅限你自己拥有或获得明确授权的设备。** 不要用于他人的设备、来源不明的设备或被盗设备。
- 解锁/刷机可能导致**数据清空、变砖、失去保修**；设备可能有 **anti-rollback**。风险自负。
- 本仓库的**私钥是故意公开的**：任何拿到这些镜像的人都能为刷了镜像的设备签 token。  
  如果你想要只由自己掌握的私钥，请用 [docs/CUSTOM_KEY.md](docs/CUSTOM_KEY.md) 生成自己的密钥并重建镜像。
- 这不是绕屏幕锁、账号锁、FRP 的工具；bootloader 解锁需要物理访问，通常会清数据。
- 仅支持 **Redmi Turbo 4 (rodin) 的 303 / 304 版本**。其他版本/机型不支持，可能变砖。
- 详细免责声明：[DISCLAIMER.md](DISCLAIMER.md)。

---

## 这是什么

`lk` 是 MTK 的 bootloader。小米的 `lk` 里内置了一把 RSA-2048 公钥，用来验证
`fastboot oem get_token` + 云端签名得到的 **unlock token**。

本套件：

1. 把 `lk` / `aee` 里内置的 unlock-token 公钥模数换成**我们自己的**公钥（指数仍是 65537）；
2. 在 `lk` / `aee` 的 cert2 前面插入一个 90 字节的 `0xA0` 哈希覆盖块，让 preloader
   用修改后镜像的 SHA-256 通过校验；原 cert2 DER 及其签名不动；
3. 提供一个**纯本地**的 token 签名器，用 `keys/` 里公开的私钥直接签
   `fastboot oem get_token` 返回的 token。

镜像里没有改任何代码，只有两把 256 字节公钥和两个 cert2 哈希覆盖块。

---

## 支持版本

| 版本 | 镜像 | 大小 | SHA-256 |
|---|---|---|---|
| 303 | `images/rodin_303_our_lk.img` | 16,777,216 | `187a890b462d843dc1e0e391015130d24d8ed1c2f795e7bf4aed181ef3475d16` |
| 304 | `images/rodin_304_our_lk.img` | 16,777,216 | `e0ff77c7bbd814b3fee671655bb189ddf3fe3cf3846e264db00d6ec3d2d48242` |

- 303 基于官方 `303lk.img`（3,829,328 字节）。
- 304 基于官方 `304lk.img`（3,829,600 字节）。
- 官方镜像 SHA-256 见 [images/manifest.json](images/manifest.json)。
- **不要混用 303/304**；先确认设备版本。设备可能有 `anti: 1`。

---

## 快速开始

### 0. 取仓库并校验

```bash
git clone https://github.com/omajili-manbu/rodin_lk_unlock_kit.git
cd rodin_lk_unlock_kit

cd images
sha256sum -c SHA256SUMS.txt
cd ..
```

也可以直接跑完整校验：

```bash
python3 tools/verify_our_lk.py --all
python3 tools/sign_token.py --self-test
```

### 1. 写入 lk_a 和 lk_b

> 按你设备上可用的 root/adb 方式操作。下面的块设备路径是示例，**先确认**
> `lk_a` / `lk_b` 的真实路径；写错分区可能变砖。

```bash
# 303 设备用 303 镜像；304 设备用 304 镜像
IMG=images/rodin_304_our_lk.img

adb push "$IMG" /data/local/tmp/our_lk.img
adb shell su -c 'ls -l /dev/block/by-name/ | grep -E "lk_a|lk_b"'

adb shell su -c 'dd if=/data/local/tmp/our_lk.img of=/dev/block/by-name/lk_a bs=1M'
adb shell su -c 'dd if=/data/local/tmp/our_lk.img of=/dev/block/by-name/lk_b bs=1M'
adb shell su -c 'sync'
```

两个槽都要写。也可以沿用你之前工具箱“写 LK”的流程，只替换镜像文件。

### 2. 每个槽解锁

```bash
fastboot getvar current-slot
fastboot oem get_token
# 把输出的两行 token 保存到 token.txt

python3 tools/sign_token.py --token-file token.txt -o unlock.sig --raw

fastboot stage unlock.sig
fastboot oem unlock
fastboot oem lks        # 期望返回 0
```

- **token 必须现场取、立即签、立即用。** 重启、切槽、或先执行 `oem unlock`
  都会刷新 challenge，旧 token 立即失效。
- **每个槽单独** `get_token` → 签名 → `stage` → `oem unlock`；a 槽 token 不能用于 b 槽。
- 经验上先解锁非活跃槽，再切回原卡槽解锁；严格按你设备上验证过的顺序来。
- `fastboot stage` 显示 `(0 KB)` 是正常的，签名文件实际是 **256 字节**。
- **不要在没 stage 签名的情况下执行 `oem unlock`**，否则可能报
  `Failed to set lock state`，challenge 重置。

更完整的流程见 [docs/05-flash-unlock.md](docs/05-flash-unlock.md)。

---

## 文件

| 路径 | 说明 |
|---|---|
| `images/rodin_303_our_lk.img` | 303 版 16MB lk 分区镜像 |
| `images/rodin_304_our_lk.img` | 304 版 16MB lk 分区镜像 |
| `images/SHA256SUMS.txt` | 镜像校验和 |
| `images/manifest.json` | 版本、镜像哈希、公钥指纹、官方基座哈希 |
| `keys/rodin_unlock_priv.pem` | **故意公开**的 RSA-2048 私钥 |
| `keys/rodin_unlock_pub.pem` | 对应公钥 |
| `keys/modulus.txt` | 公钥模数（`Modulus=...`） |
| `keys/KEY_INFO.txt` | 密钥指纹、改动偏移、镜像哈希 |
| `tools/sign_token.py` | 离线 token 签名器（纯 Python 标准库） |
| `tools/build_our_lk.py` | 从官方镜像构建我们自己的 lk |
| `tools/verify_our_lk.py` | 镜像结构/密钥/哈希校验 |
| `scripts/flash_lk.sh` | 带确认的 dd 刷写示例 |
| `scripts/get_token_and_sign.ps1` | Windows 下取 token + 离线签名 |
| `scripts/verify_all.sh` | checksums + 镜像校验 + 自签自测 |
| `docs/` | 原理、构建、签名、刷机、验证、FAQ |

---

## 原理速览

- **解锁 token**：`lk` 用内置 RSA-2048 公钥验证 token。我们把公钥模数换成自己的，
  私钥公开，所以任何人都能离线签 token。
- **preloader 校验**：`lk` / `aee` 由 preloader 用 cert2 验证。我们在 cert2 DER 前插入
  `0xA0` 哈希覆盖块，写入新镜像的 SHA-256；原 cert2 与签名保持不变。这利用了
  MTK cert2 ASN.1 解析的已知逻辑缺陷（同类公开研究：pwnage24mtk / CVE-2023-20696 等）。
- **token 签名**：裸 RSA PKCS#1 v1.5 type-1（不是 `dgst` 那种 DigestInfo），
  解出的明文就是 token 本身（magic `0x5501`、设备 ID、challenge 等）。
- **代码未改**：除两个 256 字节公钥和两个 cert2 哈希块外，`bl2_ext`、`lk_main_`、
  `lk_dtbo` 等全部与官方逐字节一致。

详细原理与偏移：[docs/02-principle.md](docs/02-principle.md)。

---

## 私钥公开说明

`keys/rodin_unlock_priv.pem` **是故意提交到仓库的**：

- 它不是小米/MTK 泄漏的密钥，而是为本项目生成的；
- 它只能签发**刷了本仓库镜像**的设备的 unlock token；
- 它不能解锁官方固件、不能解密数据、不能绕过屏幕锁/账号锁/FRP；
- 任何人拿到它都能为这些镜像签 token —— 这正是“随时离线解锁”的设计目标。

如果你想要**只由自己掌握**的私钥：

1. 自己生成 RSA-2048（e=65537）；
2. 用 [tools/build_our_lk.py](tools/build_our_lk.py) 从官方镜像重建；
3. 只发布公钥/模数，私钥自己保管。

步骤见 [docs/CUSTOM_KEY.md](docs/CUSTOM_KEY.md)。

---

## 验证

```bash
# 镜像 checksum
(cd images && sha256sum -c SHA256SUMS.txt)

# 镜像结构、公钥、指数、cert2 覆盖块哈希
python3 tools/verify_our_lk.py --all

# 签名器自测
python3 tools/sign_token.py --self-test

# 对已有签名做本地复核
python3 tools/sign_token.py --token-file token.txt -o unlock.sig --verify
```

公钥指纹（SPKI DER SHA-256）：

```
ca6b606035ebe83cddd515a3d47f2e5f5b396c37d38edc0a6027afed22ebc704
```

---

## 常见问题

- **私钥公开会不会被别人用来解锁我的手机？**  
  只有刷了本仓库镜像的设备才会认这把钥匙；bootloader 解锁本来就需要物理/root 访问。
  想要独占，请用自己的密钥重建。
- **能绕过账号锁/FRP 吗？**  
  不能。这不是账号锁工具；解锁通常会清数据。
- **会清数据吗？**  
  解锁通常会清 userdata；提前备份。
- **305 或其他机型能用吗？**  
  不支持。偏移、preloader、cert2 布局可能不同，可能变砖。
- **为什么有两个镜像？**  
  303 和 304 的官方 `lk` 基座不同；必须匹配设备版本。
- **为什么双槽都要做？**  
  两个槽各有自己的 `lk` 分区和 token challenge。
- **stage 显示 0 KB？**  
  正常，签名文件是 256 字节，按 KB 显示为 0。
- **失败/变砖怎么办？**  
  见 [docs/07-troubleshooting.md](docs/07-troubleshooting.md)；恢复通常需要刷回官方 `lk` 或 EDL。

更多见 [docs/08-faq.md](docs/08-faq.md)。

---

## 文档

- [01 概览与范围](docs/01-overview.md)
- [02 原理与镜像结构](docs/02-principle.md)
- [03 从官方镜像构建](docs/03-build.md)
- [04 token 与离线签名](docs/04-sign-token.md)
- [05 刷入与双槽解锁](docs/05-flash-unlock.md)
- [06 校验与复现](docs/06-verify.md)
- [07 故障排查](docs/07-troubleshooting.md)
- [08 FAQ](docs/08-faq.md)
- [自定义密钥](docs/CUSTOM_KEY.md)

---

## 安全与法律

- 仅限自己拥有或获授权的设备；不要用于被盗设备。
- 解锁/刷机可能清数据、变砖、失去保修；设备可能有 anti-rollback。
- 本项目与小米、Redmi、MTK、HyperOS 无关联；相关商标归各自所有者。
- 固件镜像由官方固件修改而来，仅用于互操作/维修/安全研究；见 [NOTICE](NOTICE)。
- 完整免责声明：[DISCLAIMER.md](DISCLAIMER.md)。

---

## Credits

- MTK cert2 ASN.1 哈希覆盖的公开研究：  
  [kasnria001/pwnage24mtk](https://github.com/kasnria001/pwnage24mtk)
- 相关 CVE 背景：  
  [CVE-2023-20696](https://cve.komodosec.com/cve?id=CVE-2023-20696)
- MTK modding 社区与所有公开逆向资料。

本项目与上述项目/公司无隶属关系。

---

## License

- 脚本与文档：**AGPL-3.0-only**，见 [LICENSE](LICENSE)。
- `images/` 中的固件镜像由官方固件修改而来，**不属于 AGPL-3.0 许可**；见 [NOTICE](NOTICE)。
- `keys/` 中的私钥为本项目生成，**故意公开**；它作为功能材料提供，见 [keys/README.md](keys/README.md)。
- 如果你修改本仓库代码并通过网络提供服务，AGPL-3.0 要求你向用户提供对应源代码。
