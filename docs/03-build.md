# 03 — 从官方镜像构建

`tools/build_our_lk.py` 从**官方** `lk.img` 生成我们自己的 16MB 镜像。它会：

1. 在 `lk` / `aee` 里找到原厂 unlock-token 公钥（256 字节），替换成
   `--modulus` 指定的模数；
2. 计算修改后 `lk` / `aee` 的 body SHA-256 和 GFH 头 SHA-256；
3. 在 `lk` / `aee` 的 cert2 DER 前插入 90 字节 `0xA0` 覆盖块；
4. 把 cert2 dsize 从 `0x3D6` 改成 `0x430`，按新长度重排后续子镜像；
5. 补零到 16MB。

原 cert2 DER 不变；`lk` / `aee` 的指数 `01 00 01` 不变。

## 前置条件

- Python 3.8+（只用标准库）；
- 对应版本的官方 `lk.img`：
  - 303：`303lk.img`，3,829,328 字节；
  - 304：`304lk.img`，3,829,600 字节；
- 公钥模数 `keys/modulus.txt`（或你自己的 `Modulus=...` 文件）。

官方 `lk.img` 可从对应版本的 fastboot 固件包里提取。校验官方镜像哈希：

```bash
sha256sum 303lk.img 304lk.img
```

参考值见 [../images/manifest.json](../images/manifest.json)。

## 构建 303

```bash
python3 tools/build_our_lk.py \
  --official /path/to/303lk.img \
  --modulus keys/modulus.txt \
  --out build/rodin_303_our_lk.img
```

## 构建 304

```bash
python3 tools/build_our_lk.py \
  --official /path/to/304lk.img \
  --modulus keys/modulus.txt \
  --out build/rodin_304_our_lk.img
```

运行时会打印：

- 原公钥和新公钥；
- 两个子镜像的 header/body SHA-256；
- 两个 90 字节覆盖块；
- cert2 的 dsize 变化和插入位置；
- 自检结果（公钥出现两次、覆盖块哈希、原 DER 等）。

## 可选：和参考镜像做差异检查

如果你有第三方解锁镜像，可以加 `--reference`：

```bash
python3 tools/build_our_lk.py \
  --official /path/to/304lk.img \
  --modulus keys/modulus.txt \
  --reference /path/to/304lkunlock.img \
  --out build/rodin_304_our_lk.img
```

预期差异只有：

- lk 的 256 字节公钥；
- aee 的 256 字节公钥；
- 两个 cert2 的 32 字节 `2.1` image hash。

## 复现性

使用同一个官方镜像和同一个 `keys/modulus.txt`，构建结果应与仓库里的
`images/rodin_*_our_lk.img` **逐字节一致**：

```bash
sha256sum build/rodin_304_our_lk.img images/rodin_304_our_lk.img
```

两者应相同。不同则检查：

- 官方镜像版本是否匹配；
- `keys/modulus.txt` 是否被改过；
- 是否用错了 303/304 基座。

## 校验生成的镜像

```bash
python3 tools/verify_our_lk.py \
  --image build/rodin_304_our_lk.img \
  --modulus keys/modulus.txt
```

可选地和官方镜像对比：

```bash
python3 tools/verify_our_lk.py \
  --image build/rodin_304_our_lk.img \
  --modulus keys/modulus.txt \
  --official /path/to/304lk.img
```

## 换自己的密钥

见 [CUSTOM_KEY.md](CUSTOM_KEY.md)。核心是把 `--modulus` 换成你自己的
`Modulus=...` 文件，然后用你的私钥签 token。

## 常见构建错误

| 错误 | 原因 |
|---|---|
| `expected 2 occurrences of official key` | 官方镜像版本不对，或不是 rodin 的 `lk` |
| `part 'aee' not found` / `cert2 not found` | 不是预期的 15-part lk 镜像 |
| `modulus hex must be 512 chars` | `modulus.txt` 不是 2048-bit 模数 |
| 输出和仓库镜像不一致 | 官方基座或模数不同 |
