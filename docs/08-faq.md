# 08 — FAQ

## 这套东西到底做了什么？

把 `lk` / `aee` 里验证解锁 token 的 RSA 公钥换成项目自己的，并在 cert2 前插入
哈希覆盖块，让 preloader 接受修改后的镜像。token 由公开私钥离线签名。
没有改代码。详见 [02-principle.md](02-principle.md)。

## 为什么要公开私钥？

目标就是“任何人随时离线解锁”。私钥公开后，不需要云端、账号、access code，
每个人都能自己签 token。代价是：任何拿到镜像的人都能为刷了镜像的设备签 token。
如果你要独占，用自己的密钥重建（[CUSTOM_KEY.md](CUSTOM_KEY.md)）。

## 这个私钥是小米/MTK 泄漏的吗？

不是。它是为本项目生成的 RSA-2048 密钥。官方固件不认它；它只对刷了本仓库
镜像的设备有效。

## 别人能拿这个私钥解锁我的手机吗？

只有刷了本仓库镜像、且能物理访问/进入 fastboot 的设备才会用到它。bootloader
解锁本来就需要物理访问；如果别人已经能刷你的 `lk`，设备安全边界已经被突破。
想要独占私钥，请重建。

## 能绕过屏幕锁、账号锁、FRP 吗？

不能。这不是账号锁/FRP 工具。bootloader 解锁通常会清数据，且需要物理访问。
不要用它处理来源不明的设备。

## 会清数据吗？

解锁通常会导致 userdata/metadata 被清空。操作前备份。可以在解锁后手动：

```bash
fastboot erase userdata
fastboot erase metadata
```

## 支持哪些版本/机型？

只支持 Redmi Turbo 4（rodin）303 / 304。其他版本（305+）和其他机型不支持；
偏移、cert2 布局、preloader 行为可能不同，可能变砖。

## 为什么有 303 和 304 两个镜像？

两个版本的官方 `lk` 基座不同（例如 `lk_dtbo` 大小）。必须用匹配的镜像。
`images/manifest.json` 里有官方镜像哈希，可用于确认。

## 为什么双槽都要做？

两个槽各有自己的 `lk` 分区和 token challenge。只改一个槽，另一个槽仍用旧公钥/
旧镜像，不认你的 token。

## 为什么 token 要现场取？

token 包含 challenge，重启、切槽、或先执行 `oem unlock` 都会刷新 challenge。
旧 token 立即失效。流程必须是：`get_token` → 签名 → `stage` → `oem unlock`。

## 为什么 `fastboot stage` 显示 0 KB？

签名文件是 256 字节，小于 1KB 时按 KB 显示为 0。文件实际有内容，正常。

## 为什么镜像只差几个字节？

相对官方镜像，只改了：

- lk 的 256 字节公钥；
- aee 的 256 字节公钥；
- 两个 cert2 的 90 字节覆盖块（含新的 body hash）；
- cert2 dsize 和后续偏移/补零。

`bl2_ext`、`lk_main_`、`lk_dtbo` 等与官方逐字节一致。

## 为什么要改 aee？

aee 里也有同一套 unlock-token 验签代码和公钥，而且 preloader 也会验证它。
只改 lk 可能导致某些路径不认你的 token。

## 为什么不用官方证书重新签名？

我们没有小米/MTK 的证书私钥。cert2 的哈希覆盖块利用了 MTK 解析器的已知逻辑
缺陷；原 cert2 DER 和签名保持不变。相关公开研究：pwnage24mtk、CVE-2023-20696。

## 需要 root 吗？

写入 `lk` 分区通常需要 root/adb（或 EDL/授权工具）。已经解锁的设备可以用
fastboot/root 方式；未解锁设备如果没有 root，单靠本 kit 不能写入。不要在不
了解状态的情况下乱刷。

## 设备已经解锁了，还需要再解锁吗？

不需要为了刷镜像而重新解锁。刷入后，以后需要解锁/换槽时，token 要用本仓库
的私钥签。刷镜像不会改变当前 `seccfg` 锁定状态。

## 可以回锁吗？

本仓库不提供回锁流程。`fastboot oem lock` 的风险因版本/状态而异，可能导致
无法启动。没有完整备份和验证流程时不要尝试。

## 可以用于 305 吗？

未验证。305 的 `lk`、cert2 布局、preloader 可能不同；用错可能变砖。等有人
验证并提交对应版本再说。

## 怎么验证镜像没被改过？

```bash
(cd images && sha256sum -c SHA256SUMS.txt)
python3 tools/verify_our_lk.py --all
```

公钥指纹：

```
ca6b606035ebe83cddd515a3d47f2e5f5b396c37d38edc0a6027afed22ebc704
```

## 怎么自己构建/换密钥？

见 [03-build.md](03-build.md) 和 [CUSTOM_KEY.md](CUSTOM_KEY.md)。

## AGPL-3.0 对本地使用有影响吗？

本地刷机和签名不触发 AGPL 的额外义务。如果你分发修改版，或把修改版作为网络
服务提供，需要按 AGPL-3.0 提供对应源代码。固件镜像本身不属于 AGPL-3.0。

## 可以重新分发吗？

代码/文档是 **AGPL-3.0-only**；`images/` 是官方固件修改版，不属于 AGPL-3.0，
见 [NOTICE](../NOTICE)。请保留
免责声明、版权/商标说明，不要把它包装成官方工具。

## GitHub 会不会把私钥当成泄漏？

可能会触发 secret scanning 提示。这个仓库的 PEM 是**项目生成、故意公开**的，
不是泄漏的第三方凭据。仓库所有者可以在 GitHub UI 里确认。不要为了绕过扫描
把它改成编码/混淆形式；直接公开是设计目标。

## 失败/变砖怎么办？

先看 [07-troubleshooting.md](07-troubleshooting.md)。能进 bootloader 就刷回
备份/官方 `lk`；不能进就考虑 EDL/授权维修。不要在未知状态反复盲刷。

## 为什么仓库里带固件镜像？

为了让没有官方固件包的人也能直接使用。镜像由官方固件修改而来，仅用于互操作/
维修/安全研究；见 [NOTICE](../NOTICE)。如果你有版权顾虑，可以只用
`tools/build_our_lk.py` 从你自己的官方镜像构建。

## 这个项目和小米/MTK 有关系吗？

没有。非官方项目，无隶属/背书关系。相关商标归各自所有者。
