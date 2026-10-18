# 04 — token 与离线签名

## token 长什么样

`fastboot oem get_token` 打印两行 base64：

```
(bootloader) token: <token1>
(bootloader) token: <token2>
```

两段拼接后是一个约 80 个 ASCII 字符的 base64 字符串；base64 解码后是一个
约 59 字节的二进制 token（challenge 长度可能让长度略有变化）。它不是纯随机数据，通常包含：

- magic `0x5501`；
- type / 长度；
- 设备 ID（`rodin`）；
- 随机 challenge；
- 固定后缀（token2 部分）。

token 与 **challenge + 槽位** 绑定：

- 重启后 challenge 重置；
- 执行 `fastboot oem unlock`（即使没 stage）会重置；
- 切换槽位后必须重新取；
- 每个槽的 token 不同。

所以：**取 token → 立即签 → 立即 stage + unlock**，中间不要重启/切槽/执行其他
`oem` 命令。

## 签名原理

`lk` 验证的是 **裸 RSA PKCS#1 v1.5 type-1**：

```
EM  = 00 01 FF FF ... FF 00 || base64(token1 + token2)
sig = EM^d mod n          # 256 字节
```

注意：

- **签名对象是 base64 字符串**（约 80 个 ASCII 字符），不是解码后的二进制；
- 不是 `openssl dgst -sign` 那种“先 hash 再加 DigestInfo”的签名；
- 这里是把 base64 字符串直接做 type-1 填充，再用私钥指数运算；
- `lk` 验签恢复出这个字符串后，再 base64 解码，解析 magic/type/设备 ID/challenge。

这一点已用旧版第三方解锁留下的真实 `unlock_a.sig` / `unlock_b.sig` 验证：
旧签名恢复出的 payload 是 80 字符 base64 字符串，解码后 59 字节、magic
`0x5501`、TLV type 1/3/2、包含 `rodin`。

`tools/sign_token.py` 用纯 Python 标准库实现：

- 解析 PKCS#1/PKCS#8 私钥（PEM）；
- 计算 `pow(EM, d, n)`；
- 本地反验签；
- 输出 256 字节 `unlock.sig`。

## 用法

### 从 fastboot 输出文件

```bash
fastboot oem get_token | tee token.txt
python3 tools/sign_token.py --token-file token.txt -o unlock.sig --raw
```

`token.txt` 里可以保留 `(bootloader) token:` 前缀，工具会自动提取。

### 直接传两段

```bash
python3 tools/sign_token.py --token1 '<token1>' --token2 '<token2>' -o unlock.sig
```

### 传拼接后的单段

```bash
python3 tools/sign_token.py --token '<token1><token2>' -o unlock.sig
```

### 传原始二进制（hex）

```bash
python3 tools/sign_token.py --token-hex 5501... -o unlock.sig
```

### 指定私钥（你自己的密钥）

```bash
python3 tools/sign_token.py -k /path/to/my_priv.pem --token-file token.txt -o unlock.sig
```

### 复核签名

```bash
python3 tools/sign_token.py --token-file token.txt -o unlock.sig --verify
```

### 自测（不需要设备）

```bash
python3 tools/sign_token.py --self-test
```

## 签名对象与 token 校验

工具签的是 `token1 + token2` 直接拼接后的 **base64 字符串**。它同时会：

- 打印这个字符串（约 80 字符）和 SHA-256；
- base64 解码并打印二进制长度、hex、magic、是否包含 `rodin`；
- 用 `--raw` 时把字符串保存为 `<out>.token.txt`（不是二进制）。

如果两段 token 的拼接方式特殊（例如中间有 `=`），直接用 `--token` 传完整的
拼接字符串，工具会原样签名：

```bash
python3 tools/sign_token.py --token '<token1><token2>' -o unlock.sig
```

`--token-hex` 用于你已经有解码后的二进制、想反推 base64 字符串的场景：工具会
先把 hex 转成字节再 base64 编码，然后签名。

正常情况下工具会打印类似：

```
token string: 80 chars
  VQEC...
  decoded binary: 59 bytes
  magic: 5501  rodin: True
```

如果 magic 不是 `0x5501`，先检查 token 是否完整、是否被换行/空格截断。

## 签名文件

- 大小固定 **256 字节**；
- `fastboot stage unlock.sig` 显示 `(0 KB)` 是正常的（小于 1KB 按 KB 显示为 0）；
- 不要用文本方式保存，必须保存为二进制。

## token 失效/失败

| 现象 | 原因 |
|---|---|
| `token sig decrypt failed` | token 字符串不完整/拼接错、token 过期、镜像公钥不匹配 |
| `[unlock_token]no token found` | base64 字符串解码后不是 token（拼接/截断） |
| `Failed to set lock state` | 没先 stage、token 过期、或之前误执行过 `oem unlock` |
| `cpuid mismatch` / `device name mismatch` | token 不属于这台设备 |
| `token verify fail! Can not be write into rpmb` | RPMB/锁定状态或 token 问题 |

处理顺序：

1. 重新 `get_token`（确保 challenge 是新的）；
2. 确认当前槽位；
3. 用 `--raw` 保存签名对应的 base64 字符串，并看工具打印的解码结果（magic/长度）；
4. 重新签名；
5. 立即 `fastboot stage` + `oem unlock`；
6. 检查 `fastboot oem lks` 是否为 0。

更完整排错见 [07-troubleshooting.md](07-troubleshooting.md)。
