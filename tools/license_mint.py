#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c3shell 卡密签发机（离线签名卡密 · 2026-09-24）

设计要点（为什么这样设计，改之前先读这段）：
  · 卡密 = 一段**自包含 + 带签名**的字符串：APP 只内置**公钥**，离线就能验真伪 ✓
    私钥只在你这台机器上（~/.c3license/key.hex）→ 别人反编译 APP 也**伪造不出卡密** ✓
  · 一码一台：卡密里**签进了「C3 设备码」摘要** → 买家把 C3 设备码发你，你签一张只认那台 C3 的卡 ✓
  （同一台 C3：手机、车机、换手机都能用 ✓；换 C3 才需要换卡 ✓）
    摘要取 7 字节（56 位）→ 想「凑出」一台假设备撞上它要试 2^56 次，做不到 ✓
  · 有效期写在卡里（自 2026-01-01 起的天数，0 = 永久）✓
  · 签名用 ECDSA P-256 / SHA-256，**纯标准库实现**（不装任何依赖，平板/电脑都能跑）✓
    签名按 IEEE P1363 存成 64 字节定长（r||s），APP 那边自己拼回 DER 给 java 验 ✓

卡密格式（Crockford Base32，字母表已去掉易混的 I/L/O/U）：
    C3-XXXXXXXX-XXXXXXXX-…        （16 字节载荷 + 64 字节签名 + 2 字节校验 = 82 字节 → 132 字符）
    载荷 16 字节： [0]版本| [1]功能位 | [2]套餐 | [3]保留 | [4-5]到期天数 | [6-8]序号 | [9-15]C3 设备码摘要

用法：
    python3 tools/license_mint.py genkey                      # 首次：生成密钥（只做一次！）
    python3 tools/license_mint.py pubkey                      # 打印要填进 Java 的公钥常量
    python3 tools/license_mint.py mint --c3 c5f64914 --days 365        # c5f64914 = C3 设备码
    python3 tools/license_mint.py mint --any --days 30        # 不绑 C3 的通用卡（试用/自用）
    python3 tools/license_mint.py show C3-XXXX-XXXX-…         # 解码 + 验签（核对用）
    python3 tools/license_mint.py qr C3-XXXX-… --out card.png # 打成二维码（可选）
"""
import argparse, base64, hashlib, hmac, io, json, os, sys, datetime

# ───────────────────────── ECDSA P-256（纯标准库）─────────────────────────
P  = 0xffffffff00000001000000000000000000000000ffffffffffffffffffffffff
A  = P - 3
B  = 0x5ac635d8aa3a93e7b3ebbd55769886bc651d06b0cc53b0f63bce3c3e27d2604b
GX = 0x6b17d1f2e12c4247f8bce6e563a440f277037d812deb33a0f4a13945d898c296
GY = 0x4fe342e2fe1a7f9b8ee7eb4a7c0f9e162bce33576b315ececbb6406837bf51f5
N  = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551
G  = (GX, GY)


def _inv(a, m):
    return pow(a % m, -1, m)


def _add(p1, p2):
    if p1 is None:
        return p2
    if p2 is None:
        return p1
    x1, y1 = p1
    x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P == 0:
        return None
    if p1 == p2:
        lam = (3 * x1 * x1 + A) * _inv(2 * y1, P) % P
    else:
        lam = (y2 - y1) * _inv(x2 - x1, P) % P
    x3 = (lam * lam - x1 - x2) % P
    return (x3, (lam * (x1 - x3) - y1) % P)


def _mul(k, pt):
    r = None
    while k:
        if k & 1:
            r = _add(r, pt)
        pt = _add(pt, pt)
        k >>= 1
    return r


def _rfc6979_k(x, h1, n=N):
    """RFC 6979 确定性随机数：同一个「私钥+内容」永远算出同一张卡（好核对、可复现）✓"""
    hlen = 32
    v = b"\x01" * hlen
    k = b"\x00" * hlen
    xb = x.to_bytes(32, "big")
    hb = (h1 % n).to_bytes(32, "big")
    k = hmac.new(k, v + b"\x00" + xb + hb, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    k = hmac.new(k, v + b"\x01" + xb + hb, hashlib.sha256).digest()
    v = hmac.new(k, v, hashlib.sha256).digest()
    while True:
        t = b""
        while len(t) < 32:
            v = hmac.new(k, v, hashlib.sha256).digest()
            t += v
        cand = int.from_bytes(t[:32], "big")
        if 1 <= cand < n:
            yield cand
        k = hmac.new(k, v + b"\x00", hashlib.sha256).digest()
        v = hmac.new(k, v, hashlib.sha256).digest()


def sign(priv_hex, msg):
    """返回 (r, s) 各 32 字节（已做 low-s 规范化，签名唯一 ✓）"""
    d = int(priv_hex, 16)
    e = int.from_bytes(hashlib.sha256(msg).digest(), "big")   # Java 侧用的是同一个 e ✓
    for k in _rfc6979_k(d, e):
        pt = _mul(k, G)
        r = pt[0] % N
        if r == 0:
            continue
        s = (_inv(k, N) * (e + r * d)) % N
        if s == 0:
            continue
        if s > N // 2:
            s = N - s
        return r.to_bytes(32, "big"), s.to_bytes(32, "big")
    raise RuntimeError("签名失败")


def pubkey_xy(priv_hex):
    pt = _mul(int(priv_hex, 16), G)
    return pt[0].to_bytes(32, "big"), pt[1].to_bytes(32, "big")


def spki_der(priv_hex):
    """P-256 公钥的标准 X.509 SubjectPublicKeyInfo（Java 直接 KeyFactory 解析 ✓）"""
    x, y = pubkey_xy(priv_hex)
    alg = bytes.fromhex("301306072a8648ce3d020106082a8648ce3d030107")
    bits = b"\x03\x42\x00\x04" + x + y
    body = alg + bits
    return b"\x30" + bytes([len(body)]) + body


# ───────────────────────── 卡密编解码 ─────────────────────────
ALPHA = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
DEC = {c: i for i, c in enumerate(ALPHA)}
DEC.update({"I": 1, "L": 1, "O": 0, "U": 27})          # 易混字符按惯例归一 ✓
EPOCH = datetime.date(2026, 1, 1)
PLANS = {0: "pro", 1: "basic", 2: "trial", 3: "internal"}
PLANS_REV = {v: k for k, v in PLANS.items()}
FEATS = [("ai", 0), ("routes", 1), ("feedback", 2)]


def b32e(data):
    bits = "".join(format(b, "08b") for b in data)
    bits += "0" * ((5 - len(bits) % 5) % 5)
    return "".join(ALPHA[int(bits[i:i + 5], 2)] for i in range(0, len(bits), 5))


def b32d(s):
    s = "".join(ch for ch in s.upper() if ch in DEC)
    bits = "".join(format(DEC[c], "05b") for c in s)
    out = bytearray()
    for i in range(0, len(bits) - len(bits) % 8, 8):
        out.append(int(bits[i:i + 8], 2))
    return bytes(out)


def payload(device, days, plan, feats, seq):
    if device:
        tag = hashlib.sha256(("c3:" + device.strip().lower()).encode("utf-8")).digest()[:7]
    else:
        tag = b"\x00" * 7
    exp = 0 if not days else (EPOCH + datetime.timedelta(days=int(days)) - EPOCH).days
    if days:
        exp = (datetime.date.today() + datetime.timedelta(days=int(days)) - EPOCH).days
        if exp < 0:
            exp = 0
    mask = 0
    for name, bit in FEATS:
        if name in feats:
            mask |= (1 << bit)
    b = bytearray(16)
    b[0] = 0x10
    b[1] = mask
    b[2] = PLANS_REV.get(plan, 0)
    b[3] = 0
    b[4:6] = exp.to_bytes(2, "big")
    b[6:9] = (int(seq) & 0xFFFFFF).to_bytes(3, "big")
    b[9:16] = tag
    return bytes(b)


def wrap(raw):
    groups = [raw[i:i + 8] for i in range(0, len(raw), 8)]
    return "C3-" + "-".join(groups)


def mint(priv, device, days, plan, feats, seq):
    pl = payload(device, days, plan, feats, seq)
    r, s = sign(priv, pl)
    body = pl + r + s
    chk = hashlib.sha256(body).digest()[:2]
    return wrap(b32e(body + chk))


def parse(card):
    c = card.strip().upper()
    if c.startswith('C3-'): c = c[3:]          # 前缀里的 C、3 也是合法 base32 字符 → 必须先剥掉 ✗
    elif c.startswith('C3'): c = c[2:]
    raw = b32d(c)
    if len(raw) < 82:
        raise ValueError("长度不对（%d 字节，应为 82）" % len(raw))
    pl, r, s, chk = raw[:16], raw[16:48], raw[48:80], raw[80:82]
    if hashlib.sha256(pl + r + s).digest()[:2] != chk:
        raise ValueError("校验位不对 → 卡密抄错了")
    exp_days = int.from_bytes(pl[4:6], "big")
    exp = "" if exp_days == 0 else (EPOCH + datetime.timedelta(days=exp_days)).isoformat()
    feats = [n for n, b in FEATS if pl[1] & (1 << b)]
    tag = pl[9:16].hex()
    return {
        "ver": pl[0] >> 4, "plan": PLANS.get(pl[2], "?"), "expires": exp,
        "seq": int.from_bytes(pl[6:9], "big"), "features": feats,
        "deviceTag": tag, "bound": tag != "00" * 7,
        "payload_hex": pl.hex(), "sig_hex": (r + s).hex(),
    }


# ───────────────────────── 命令行 ─────────────────────────
KEYDIR = os.path.expanduser("~/.c3license")
KEYFILE = os.path.join(KEYDIR, "key.hex")


def load_key(path=KEYFILE, must=True):
    if os.path.exists(path):
        return io.open(path).read().strip()
    if must:
        sys.exit("找不到私钥 %s\n先跑一次：python3 tools/license_mint.py genkey" % path)
    return None


def cmd_genkey(a):
    path = a.keyfile or KEYFILE
    if os.path.exists(path) and not a.force:
        sys.exit("私钥已存在：%s（要重建请加 --force，**重建后旧卡密全部作废** ✗）" % path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    while True:
        d = int.from_bytes(os.urandom(32), "big")
        if 1 <= d < N:
            break
    io.open(path, "w").write("%064x\n" % d)
    os.chmod(path, 0o600)
    print("私钥已生成：" + path)
    print("  ⚠️ 这是你唯一的发卡权：**务必备份**（丢了就再也发不出能用的卡 ✗）")
    print("  备份：把这一行抄到别处 ——")
    print("  " + "%064x" % d)
    print()
    println_pubkey("%064x" % d)


def println_pubkey(priv):
    der = spki_der(priv)
    print("把下面这行填进 java/com/padagent/c3shell/Lic.java 的 PUBKEY_B64（只做一次 ✓）：")
    print("  " + base64.b64encode(der).decode("ascii"))
    print("  指纹(SHA-256 前 8 字节)：%s" % hashlib.sha256(der).hexdigest()[:16])


def cmd_pubkey(a):
    println_pubkey(load_key(a.keyfile or KEYFILE))


def cmd_mint(a):
    priv = load_key(a.keyfile or KEYFILE)
    feats = [x.strip() for x in (a.features or "ai,routes,feedback").split(",") if x.strip()]
    card = mint(priv, None if a.any else a.device, a.days, a.plan, feats, a.seq)
    info = parse(card)
    print("卡密（发给买家，整段复制）：")
    print(card)
    print()
    print("  套餐    : %s" % info["plan"])
    print("  有效期  : %s" % (info["expires"] or "永久"))
    print("  功能    : %s" % ",".join(info["features"]))
    print("  序号    : %d" % info["seq"])
    print("  绑定    : %s" % ("不绑 C3（通用卡）" if not info["bound"] else "C3 设备码 " + a.device))
    print("  设备摘要: %s" % info["deviceTag"])
    if a.out:
        write_qr(card, a.out)
        print("  二维码  : %s（买家扫码 → 复制 → 粘贴到 APP 里激活 ✓）" % a.out)


def write_qr(text, out):
    try:
        import segno
    except ImportError:
        sys.exit("没装 segno：pip install segno")
    segno.make(text, error="l").save(out, scale=6, border=2, dark="#111827", light="#ffffff")


def cmd_qr(a):
    write_qr(a.card, a.out)
    print("二维码已生成：%s" % a.out)


def cmd_show(a):
    try:
        info = parse(a.card)
    except Exception as e:
        sys.exit("解析失败：%s" % e)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    priv = load_key(a.keyfile or KEYFILE, must=False)
    if priv:
        if a.device:
            tag = hashlib.sha256(("c3:" + a.device.strip().lower()).encode()).digest()[:7].hex()
            print("C3 设备码比对：卡里 %s / 这台 %s → %s"
                  % (info["deviceTag"], tag, "匹配 ✓" if tag == info["deviceTag"] else "不匹配 ✗"))
    else:
        print("（本机没有私钥，只做了格式与校验位检查；验签由 APP 用公钥做 ✓）")


def main():
    ap = argparse.ArgumentParser(description="c3shell 离线签名卡密 · 签发机")
    ap.add_argument("--keyfile", default=None, help="私钥路径（默认 ~/.c3license/key.hex）")
    sub = ap.add_subparsers(dest="cmd")

    g = sub.add_parser("genkey", help="首次生成密钥（只做一次）")
    g.add_argument("--force", action="store_true")
    g.set_defaults(func=cmd_genkey)

    p = sub.add_parser("pubkey", help="打印要填进 Java 的公钥")
    p.set_defaults(func=cmd_pubkey)

    m = sub.add_parser("mint", help="签发一张卡密")
    m.add_argument("--c3", "--device", dest="device", default=None,
                    help="C3 设备码（APP「激活 / 授权」里点「读取」；同一台 C3 的手机/车机通用 ✓）")
    m.add_argument("--any", action="store_true", help="不绑设备（通用卡）")
    m.add_argument("--days", type=int, default=365, help="有效天数（0 = 永久）")
    m.add_argument("--plan", default="pro", choices=list(PLANS_REV))
    m.add_argument("--features", default="ai,routes,feedback")
    m.add_argument("--seq", type=int, default=0, help="序号（你自己的台账用）")
    m.add_argument("--out", default=None, help="同时生成二维码 PNG")
    m.set_defaults(func=cmd_mint)

    s = sub.add_parser("show", help="解码 + 校验一张卡密")
    s.add_argument("card")
    s.add_argument("--c3", "--device", dest="device", default=None, help="顺便比对 C3 设备码摘要")
    s.set_defaults(func=cmd_show)

    q = sub.add_parser("qr", help="把卡密打成二维码")
    q.add_argument("card")
    q.add_argument("--out", default="card.png")
    q.set_defaults(func=cmd_qr)

    a = ap.parse_args()
    if not getattr(a, "cmd", None):
        ap.print_help()
        return
    a.func(a)


if __name__ == "__main__":
    main()
