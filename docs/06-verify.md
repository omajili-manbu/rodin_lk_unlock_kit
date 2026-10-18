# 06 — 校验与复现

## 一键校验

```bash
scripts/verify_all.sh
```

等价于：

```bash
(cd images && sha256sum -c SHA256SUMS.txt)
python3 tools/verify_our_lk.py --all
python3 tools/sign_token.py --self-test
```

## 镜像校验器做了什么

`tools/verify_our_lk.py --all` 检查：

- 文件大小 = 0x1000000（16MB）；
- 15 个 GFH 子镜像；
- lk / aee 的 256 字节模数 = `keys/modulus.txt`；
- 两处指数 = `01 00 01`；
- 模数正好出现两次；
- 两个 cert2 的 dsize = 0x430，GFH dsize 字段 = 0x430；
- cert2 前有 `a0 58` 覆盖块；
- 覆盖块里的 `2.4` = 最终镜像 GFH 头 SHA-256；
- 覆盖块里的 `2.1` = 最终镜像 body SHA-256；
- cert2 原始 DER 仍然存在（982 字节）。

可选地与官方镜像对比：

```bash
python3 tools/verify_our_lk.py \
  --image images/rodin_304_our_lk.img \
  --modulus keys/modulus.txt \
  --official /path/to/304lk.img
```

额外检查：

- lk/aee body 只差 256 字节公钥；
- 原 cert2 DER 与官方逐字节一致；
- 其他子镜像内容与官方逐字节一致。

可选地与第三方解锁镜像对比：

```bash
python3 tools/verify_our_lk.py \
  --image images/rodin_304_our_lk.img \
  --modulus keys/modulus.txt \
  --reference /path/to/304lkunlock.img
```

预期差异只在两把公钥和两个 `2.1` body hash。

## 公钥指纹

```bash
openssl pkey -pubin -in keys/rodin_unlock_pub.pem -outform DER \
  | sha256sum
```

期望：

```
ca6b606035ebe83cddd515a3d47f2e5f5b396c37d38edc0a6027afed22ebc704
```

## 签名器自测

```bash
python3 tools/sign_token.py --self-test
```

它会用 `keys/rodin_unlock_priv.pem` 对一个合成的 token 做签名和反验签，确认：

- 私钥能解析；
- RSA-2048 / e=65537；
- PKCS#1 type-1 填充正确；
- 输出 256 字节。

## 对已有签名做复核

```bash
python3 tools/sign_token.py --token-file token.txt -o unlock.sig --verify
```

它会用私钥里的公钥参数重新计算 `sig^e mod n`，检查 type-1 padding，并和 token
比较。

可选地用 OpenSSL 交叉验证（`rsautl` 在新版本已弃用，仅作参考）：

```bash
python3 tools/sign_token.py --token-file token.txt -o unlock.sig --raw
openssl rsautl -verify -pubin -inkey keys/rodin_unlock_pub.pem \
  -in unlock.sig -out recovered.bin
cmp recovered.bin unlock.sig.token.bin && echo MATCH
```

## 手动验证覆盖块

以 304 的 lk 为例：

```bash
python3 - <<'PY'
import hashlib, struct
d = open('images/rodin_304_our_lk.img','rb').read()
# lk body: 0x200..0x200+0x111CE0
lk_body = d[0x200:0x200+0x111CE0]
print('lk body sha256 ', hashlib.sha256(lk_body).hexdigest())
# lk cert2 prefix at 0x1129B0
blk = d[0x1129B0:0x1129B0+90]
print('2.4 in prefix  ', blk[14:46].hex())
print('2.1 in prefix  ', blk[58:90].hex())
print('header sha256  ', hashlib.sha256(d[0:0x200]).hexdigest())
PY
```

`2.4` 应等于 header sha256，`2.1` 应等于 body sha256。

## CI

`.github/workflows/verify.yml` 在每次 push/PR 时运行：

- 编译所有 Python 工具；
- 校验两张镜像的 SHA-256；
- 运行镜像结构校验；
- 运行签名器自测。

CI 不需要官方镜像，也不需要网络。
