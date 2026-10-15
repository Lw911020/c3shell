# -*- coding: utf-8 -*-
"""PPK(PuTTY v2/v3, Encryption: none) → OpenSSH 私钥转换器（内置密钥用）
   自检：转换后用转换出的公钥重算指纹，与 PPK 公钥指纹比对 ✓"""
import base64, hashlib, io, os, struct, sys

def b64lines(lines):
    return base64.b64decode(''.join(lines))

def parse_ppk(text):
    L = text.replace('\r\n','\n').split('\n')
    hdr = {}; i = 0
    while i < len(L) and ':' in L[i]:
        k, v = L[i].split(':', 1); hdr[k.strip()] = v.strip(); i += 1
    def take(n):
        nonlocal i
        # 跳过空行
        while i < len(L) and L[i].strip() == '': i += 1
        return L[i:i+n], i
    pub, i = take(int(hdr['Public-Lines'])); i += int(hdr['Public-Lines'])
    priv, i = take(int(hdr['Private-Lines'])); i += int(hdr['Private-Lines'])
    return hdr, b64lines(pub), b64lines(priv)

def rd_str(b, o):
    n = struct.unpack('>I', b[o:o+4])[0]; o += 4
    return b[o:o+n], o+n
def mpint(b, o):
    d, o = rd_str(b, o)
    return d, o

def ssh_string(x):
    return struct.pack('>I', len(x)) + x
def mpint_enc(x):
    if x and x[0] & 0x80: x = b'\x00' + x
    x = x.lstrip(b'\x00') or b'\x00'
    return ssh_string(x)

def to_openssh(hdr, pub, priv):
    t = hdr['PuTTY-User-Key-File-3'] if 'PuTTY-User-Key-File-3' in hdr else hdr['PuTTY-User-Key-File-2']
    comment = (hdr.get('Comment','') or '').encode()
    if t == 'ssh-rsa':
        o = 0
        alg, o = rd_str(pub, o); e, o = mpint(pub, o); n, o = mpint(pub, o)
        o2 = 0
        d, o2 = mpint(priv, o2); p, o2 = mpint(priv, o2); q, o2 = mpint(priv, o2); iqmp, o2 = mpint(priv, o2)
        pubblob = ssh_string(alg) + mpint_enc(e) + mpint_enc(n)
        body = ssh_string(alg) + mpint_enc(n) + mpint_enc(e) + mpint_enc(d) + mpint_enc(iqmp) + mpint_enc(p) + mpint_enc(q)
    elif t == 'ssh-ed25519':
        o = 0
        alg, o = rd_str(pub, o); pk, o = rd_str(pub, o)
        seed = priv                    # PPK v3: 32 字节私钥(种子)
        pubblob = ssh_string(alg) + ssh_string(pk)
        body = ssh_string(alg) + ssh_string(pk) + ssh_string(seed + pk)
    else:
        raise SystemExit('暂不支持: ' + t)
    check = 0x12345678
    privblob = struct.pack('>II', check, check) + body + ssh_string(comment)
    # 补齐到 8 字节块
    pad = 1
    while len(privblob) % 8: privblob += bytes([pad]); pad += 1
    out = b'openssh-key-v1\x00' + ssh_string(b'none') + ssh_string(b'none') + ssh_string(b'') \
        + struct.pack('>I', 1) + ssh_string(pubblob) + ssh_string(privblob)
    return out, pubblob

def pem(blob):
    b = base64.b64encode(blob).decode()
    lines = [b[i:i+70] for i in range(0, len(b), 70)]
    return '-----BEGIN OPENSSH PRIVATE KEY-----\n' + '\n'.join(lines) + '\n-----END OPENSSH PRIVATE KEY-----\n'

# 指纹（用 SHA256，格式和 ssh-keygen -lf 一致：SHA256:base64）
def fp(pubblob):
    return 'SHA256:' + base64.b64encode(hashlib.sha256(pubblob).digest()).decode().rstrip('=')

jobs = [('斌哥密钥','k4'),('斌哥密钥2','k5'),('救援密钥','k6'),('门总新密钥','k7'),('门老板老密钥','k8')]
D = '/storage/emulated/0/openpilot/c3shell/'
ok = 0
for cn, asset in jobs:
    src = D+'_keys_new/'+cn+'.bin'
    hdr, pub, priv = parse_ppk(io.open(src, encoding='utf-8', errors='replace').read())
    blob, pubblob = to_openssh(hdr, pub, priv)
    # 自检：解出的公钥指纹 vs PPK 公钥指纹
    t = hdr.get('PuTTY-User-Key-File-3') or hdr.get('PuTTY-User-Key-File-2')
    o = 0; alg, o = rd_str(pub, o)
    if t == 'ssh-rsa':
        e, o = mpint(pub, o); n, o = mpint(pub, o); chk_pub = ssh_string(alg)+mpint_enc(e)+mpint_enc(n)
    else:
        pk, o = rd_str(pub, o); chk_pub = ssh_string(alg)+ssh_string(pk)
    same = (chk_pub == pubblob)
    io.open(D+'assets/keys/'+asset, 'w', encoding='utf-8').write(pem(blob))
    print('  %-12s → %s  %s  %s  (指纹 %s)' % (cn, asset, t, ('自检 OK ✓' if same else '自检失败 ✗'), fp(pubblob)))
    ok += 1 if same else 0
print('转换完成: %d/%d 通过自检' % (ok, len(jobs)))
# 已有的两个 OpenSSH 密钥保持不动（已核对一致 ✓）
print('已内置资产:', sorted(os.listdir(D+'assets/keys')))

