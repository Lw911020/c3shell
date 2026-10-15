#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 c3shell APK 里解出原始资产（build_apk.py 的 _enc 的逆运算）。

用法: python3 tools/extract_assets.py <apk> <输出目录>

格式（见 java/com/padagent/c3shell/Sec.java）:
  "C3S1" + be32(明文长度) + RC4(key="C3Shell2026-PAD") 密文 + be32(明文字节和)
  keys/ 下的文件与 .wav 不加密，原样输出。
"""
import sys, os, zipfile, hashlib

KEY = bytes([0x43, 0x33, 0x53, 0x68, 0x65, 0x6c, 0x6c, 0x32, 0x30,
             0x32, 0x36, 0x2d, 0x50, 0x41, 0x44])   # C3Shell2026-PAD


def keystream(n):
    S = list(range(256))
    j = 0
    for i in range(256):
        j = (j + S[i] + KEY[i % len(KEY)]) & 255
        S[i], S[j] = S[j], S[i]
    out = bytearray()
    i2 = j = 0
    for _ in range(n):
        i2 = (i2 + 1) & 255
        j = (j + S[i2]) & 255
        S[i2], S[j] = S[j], S[i2]
        out.append(S[(S[i2] + S[j]) & 255])
    return bytes(out)


def xcrypt(data):
    k = keystream(len(data))
    return bytes(a ^ b for a, b in zip(data, k))


def decrypt(all_bytes, name):
    if len(all_bytes) < 12 or all_bytes[:4] != b"C3S1":
        raise ValueError("资产头无效: " + name)
    n = int.from_bytes(all_bytes[4:8], "big")
    if n < 0 or len(all_bytes) < 12 + n:
        raise ValueError("资产长度无效: " + name)
    plain = xcrypt(all_bytes[8:8 + n])
    if (sum(plain) & 0xFFFFFFFF) != int.from_bytes(all_bytes[8 + n:12 + n], "big"):
        raise ValueError("资产校验失败: " + name)
    return plain


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    apk, dest = sys.argv[1], sys.argv[2]
    z = zipfile.ZipFile(apk)
    os.makedirs(dest, exist_ok=True)
    rows = []
    for info in z.infolist():
        n = info.filename
        if not n.startswith("assets/") or n.endswith("/"):
            continue
        rel = n[len("assets/"):]
        data = z.read(n)
        if rel.endswith(".enc"):
            rel = rel[:-4]
            data = decrypt(data, rel)
        fp = os.path.join(dest, rel)
        d = os.path.dirname(fp)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(fp, "wb") as f:
            f.write(data)
        rows.append((rel, len(data), hashlib.md5(data).hexdigest()))
    rows.sort()
    for rel, size, md5 in rows:
        print("%9d  %s  %s" % (size, md5, rel))
    print("共 %d 个文件 → %s" % (len(rows), dest))
    return 0


if __name__ == "__main__":
    sys.exit(main())

