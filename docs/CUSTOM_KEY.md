# 自定义密钥

预构建镜像使用的是仓库里的公开私钥。如果你想要**只由自己掌握**的私钥，
按下面步骤用自己的密钥重建镜像。私钥只留在本地，镜像里只放公钥模数。

> 注意：换密钥后，旧镜像的 token 不再适用；必须把新镜像刷到**两个槽**。

## 1. 生成 RSA-2048（e=65537）

```bash
openssl genpkey -algorithm RSA \
  -pkeyopt rsa_keygen_bits:2048 \
  -pkeyopt rsa_keygen_pubexp:65537 \
  -out my_priv.pem

openssl rsa -in my_priv.pem -pubout -out my_pub.pem
openssl rsa -in my_priv.pem -noout -modulus > my_modulus.txt
```

要求：

- 2048-bit（256 字节模数）；
- e=65537（`01 00 01`）。LK 里的指数长度固定为 3 字节，不要换成其他指数；
- 模数为奇数且最高位为 1（正常生成的 RSA 密钥都满足）。

检查：

```bash
grep Modulus my_modulus.txt
# 应有 512 个 hex 字符
```

## 2. 用你的模数构建镜像

需要对应版本的官方 `lk.img`。

```bash
# 303
python3 tools/build_our_lk.py \
  --official /path/to/303lk.img \
  --modulus my_modulus.txt \
  --out build/rodin_303_mykey.img

# 304
python3 tools/build_our_lk.py \
  --official /path/to/304lk.img \
  --modulus my_modulus.txt \
  --out build/rodin_304_mykey.img
```

构建脚本会自检公钥出现两次、cert2 覆盖块哈希正确、原 DER 不变。

## 3. 校验

```bash
python3 tools/verify_our_lk.py \
  --image build/rodin_304_mykey.img \
  --modulus my_modulus.txt
```

可选地和官方镜像对比：

```bash
python3 tools/verify_our_lk.py \
  --image build/rodin_304_mykey.img \
  --modulus my_modulus.txt \
  --official /path/to/304lk.img
```

## 4. 用自己的私钥签 token

```bash
fastboot oem get_token | tee token.txt

python3 tools/sign_token.py \
  -k my_priv.pem \
  --token-file token.txt \
  -o unlock.sig --raw

fastboot stage unlock.sig
fastboot oem unlock
fastboot oem lks
```

`sign_token.py` 默认用仓库里的公开私钥；`-k` 会覆盖成你的私钥。
签名对象是 `token1+token2` 的 base64 字符串，不是解码后的二进制；换私钥不影响格式。

## 5. 发布/分享

如果你要把自己的版本发给别人：

- **只发布公钥/模数**（`my_pub.pem`、`my_modulus.txt`）；
- **不要发布 `my_priv.pem`**；
- 更新你的镜像清单/checksums；
- 别人要用你的镜像时，必须用你的公钥对应的私钥签 token；如果你不公开私钥，
  别人就无法自己签，除非你提供签名服务/预签 token（这会重新引入中心化）。

如果你愿意像本仓库一样公开私钥，那也可以，但要明确告知用户：任何拿到镜像的人
都能为这些设备签 token。

## 6. 轮换密钥

1. 生成新密钥；
2. 用新模数重建镜像；
3. 把新镜像刷到**两个槽**；
4. 旧镜像/旧 token 不再有效；
5. 旧私钥可以销毁（先确认没有设备还在用旧镜像）。

## 7. 备份

- 私钥至少离线备份两份；
- 不要放在公开仓库、网盘、聊天记录；
- 如果丢失，只能再次重建并刷机；
- 不要用弱口令/可预测的密钥。

## 8. 不要做的事

- 不要用 1024-bit 或非 RSA 密钥（LK 按 256 字节模数、3 字节指数处理）；
- 不要改指数为非 65537 的值（除非你同时确认代码中的指数长度/值）；
- 不要在 303 镜像里用 304 的官方基座（或反过来）；
- 不要把私钥和公钥版本混用：token 必须用与镜像模数配对的私钥签。
