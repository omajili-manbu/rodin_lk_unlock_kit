# 02 — 原理与镜像结构

本文说明这套镜像是怎么做到“离线解锁”的。核心只有两件事：

1. 把 `lk` / `aee` 里验证 unlock token 的 RSA 公钥换成我们自己的；
2. 用 cert2 前的 `0xA0` 哈希覆盖块，让 preloader 接受修改后的 `lk` / `aee`。

没有修改任何代码。

---

## 1. lk 分区结构

官方 `lk.img` 是一个 16MB 分区的镜像（官方文件本身只有约 3.8MB，后面补零）。
它由 15 个 MTK GFH 子镜像组成：

```
lk, cert1, cert2, bl2_ext, cert1, cert2, aee,
cert1, cert2, lk_main_, cert1, cert2, lk_dtbo, cert1, cert2
```

每个 GFH 头 0x200 字节，magic `0x58881688`，info magic `0x58891689`。
`lk` / `aee` 是包含 unlock-token 校验代码和公钥的两个子镜像；`bl2_ext`、
`lk_main_`、`lk_dtbo` 等不需要改。

303 和 304 的前 12 个 part 偏移/大小相同；`lk_dtbo` 大小不同
（303: 0x12C61，304: 0x12D77），只影响最后两个 part。本仓库的两个镜像分别
基于对应版本的官方镜像构建。

---

## 2. unlock token 流程

小米官方流程：

1. `fastboot oem get_token` 返回两段 base64；
2. 两段拼接后是一个约 80 个 ASCII 字符的 base64 字符串；解码后约 59 字节的二进制 token；
3. token 通常以 magic `0x5501` 开头，包含 type、设备 ID（`rodin`）、随机
   challenge 等字段；
4. 官方云端用小米的私钥对 **base64 字符串**做裸 PKCS#1 type-1 签名，返回 256 字节 RSA 签名；
5. `fastboot stage <sig>` + `fastboot oem unlock`；
6. `lk` 用内置公钥验签恢复 base64 字符串，再 base64 解码并解析 token，写入 seccfg/RPMB，完成解锁。

token 与 **challenge + 槽位** 绑定：重启、切槽、或先执行 `oem unlock` 都会
让旧 token 失效。

---

## 3. 原厂 token 验签

`lk` 内的验签函数使用固定公钥：

- 模数：256 字节（RSA-2048），位于 `lk` 的 `0xEFDE9`（body `0xEFBE9`）；
- 指数：3 字节 `01 00 01`（65537），位于 `0xEFDE6`；
- `aee` 里有一份同样的公钥和验签代码，位于 `0x2D83E1`（body `0xBA721`）。

验签逻辑是：

1. 对签名做 RSA 公钥运算 `sig^e mod n`；
2. 检查 PKCS#1 v1.5 **type-1** padding：`00 01 FF...FF 00 || payload`；
3. 把 `payload` 当作 token 解析。

也就是说，它不是“对 hash 验签”，而是把签名“解”成 token 明文，再解析 token。
因此只要知道私钥，就可以直接构造：

```
EM  = 00 01 FF...FF 00 || token
sig = EM^d mod n          # 256 字节
```

本项目就是把自己的公钥写进 `lk`/`aee`，然后把私钥公开，让任何人都能自己做
这一步。

> 逆向参考（304 lk，加载基址 0xFFFF000050700000）：
> `sub_FFFF00005073A4E0` 做 `sec_rsa_exptmod` + `RSA_padding_check_PKCS1_type_1`；
> 调用者 `sub_FFFF00005073A908` 处理 unlock token（字符串
> `[unlock_token]type=%d found`、`token sig decrypt failed` 等）。
> aee 里对应 `sub_2C2E8`。

---

## 4. 我们改了什么

### 4.1 公钥替换

在构建好的 16MB 镜像里：

| 项目 | lk | aee |
|---|---|---|
| 模数文件偏移 | `0xEFDE9` | `0x2D8431` |
| 模数 body 偏移 | `0xEFBE9` | `0xBA721` |
| 指数文件偏移 | `0xEFDE6` | `0x2D842E` |
| 指数值 | `01 00 01` | `01 00 01` |

> 官方镜像里 aee 的模数在 `0x2D83E1`；构建时先在 lk 后的 cert2 插入 90 字节，
> 整个 aee 往后移 0x50，所以构建后的 aee 模数在 `0x2D8431`。

公钥模数就是 `keys/modulus.txt` 里的 256 字节；指数保持 65537，代码里的
长度参数也是 3，所以不需要改代码。

### 4.2 cert2 与哈希覆盖

每个 lk/aee 子镜像后面都跟着 `cert1` + `cert2`：

- `cert1` 是根证书（自签），里面授权了叶公钥；
- `cert2` 是镜像证书（叶密钥自签），扩展里带两个哈希：
  - `2.16.886.2454.2.1` = 镜像 body 的 SHA-256；
  - `2.16.886.2454.2.4` = GFH 头（0x200 字节）的 SHA-256。

官方 cert2 的这两个值对应官方镜像。我们改了 lk/aee 的 body（换公钥），body
哈希就变了；preloader 会因此拒绝启动。

我们的做法是在 cert2 DER **前面**插入 90 字节：

```
a0 58
  06 07 60 86 76 93 16 02 04 03 21 00 <32 字节 GFH 头 SHA-256>
  06 07 60 86 76 93 16 02 01 03 21 00 <32 字节新 body SHA-256>
```

- `a0 58` 是 ASN.1 `[0]` 构造类型，长度 0x58；
- 两个 OID 分别对应 header hash 和 image hash；
- 原 cert2 DER 一个字都不改，所以它的自签名仍然有效；
- preloader 的 ASN.1 解析器会从前面这个未签名的 `0xA0` 块读取哈希，而不是
  只使用证书内签名过的扩展，从而接受修改后的镜像。

这是 MTK cert2 解析的已知逻辑缺陷，公开研究包括
[pwnage24mtk](https://github.com/kasnria001/pwnage24mtk)
以及同类 CVE（如 CVE-2023-20696）。本项目只针对 rodin 的 303/304 镜像。

### 4.3 插入后的布局

在构建好的镜像里：

| 项目 | 偏移 |
|---|---|
| lk 后 cert2 GFH | `0x1127B0` |
| lk cert2 的 `0xA0` 块 | `0x1129B0` |
| lk cert2 的 2.4 header hash | `0x1129BE` |
| lk cert2 的 2.1 body hash | `0x1129EA` |
| aee 后 cert2 GFH | `0x325180` |
| aee cert2 的 `0xA0` 块 | `0x325380` |
| aee cert2 的 2.4 header hash | `0x32538E` |
| aee cert2 的 2.1 body hash | `0x3253BA` |
| cert2 dsize | `0x3D6 → 0x430` |

每个 cert2 增加 90 字节，但吃掉了原来的 10 字节对齐填充，净增 80 字节；
所以 lk 之后的子镜像整体 +0x50，aee 之后再 +0x50。`bl2_ext`、`lk_main_`、
`lk_dtbo` 等的内容与官方逐字节相同，只是位置后移。

### 4.4 为什么 aee 也要改

`aee` 里也有同样的 unlock-token 验签代码和一份相同的公钥。如果只改 lk，aee
路径仍会用旧公钥，某些启动/解锁路径可能不认我们的 token；而且 preloader 也会
验证 aee。因此两个子镜像都要换公钥，并分别更新 cert2 的 image hash。

---

## 5. 改了之后的验证

- `lk` / `aee` 的 body：只差 256 字节公钥；
- 原 cert2 DER：与官方逐字节一致；
- cert2 的 `2.4` 头哈希：不变（GFH 头没改）；
- cert2 的 `2.1` body 哈希：等于构建后镜像 body 的 SHA-256；
- 其他子镜像：与官方逐字节一致（忽略 16MB 尾部补零）。
- 镜像与第三方解锁镜像的差异：只有两把公钥和两个 2.1 哈希。

运行 `python3 tools/verify_our_lk.py --all` 可以复现这些检查。

---

## 6. 进一步阅读

- [03-build.md](03-build.md)：从官方镜像复现构建
- [04-sign-token.md](04-sign-token.md)：token 格式与离线签名
- [CUSTOM_KEY.md](CUSTOM_KEY.md)：换成你自己的密钥
- [pwnage24mtk](https://github.com/kasnria001/pwnage24mtk)：MTK cert2 哈希覆盖的公开研究
