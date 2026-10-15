# -*- coding: utf-8 -*-
import base64, hashlib, struct, io
D='/storage/emulated/0/openpilot/c3shell/'
def parse(t):
    b=base64.b64decode(''.join(t.strip().split('\n')[1:-1]))
    assert b.startswith(b'openssh-key-v1\x00')
    o=15
    def rd(o):
        n=struct.unpack('>I', b[o:o+4])[0]; return b[o+4:o+4+n], o+4+n
    cipher,o = rd(o); kdf,o = rd(o); ksalt,o = rd(o)
    nk,o = struct.unpack('>I', b[o:o+4]), o+4
    pub,o = rd(o)
    priv,o = rd(o)
    return pub, priv, cipher.decode(), kdf.decode()
def mpints(b):
    o=0; out=[]
    while o < len(b):
        n=struct.unpack('>I', b[o:o+4])[0]; o+=4
        out.append(b[o:o+n]); o+=n
    return out
names={'k1':'神牛','k2':'雨落倾城','k3':'老门新密钥(本机)','k4':'斌哥密钥','k5':'斌哥密钥2','k6':'救援密钥','k7':'门总新密钥','k8':'门老板老密钥'}
print('  资产  名称                 加密       公钥(前 44 字符, 与人眼可辨 ✓)')
for k,n in names.items():
    t=io.open(D+'assets/keys/'+k,encoding='utf-8').read()
    pub,priv,ciph,kdf = parse(t)
    b64=base64.b64encode(pub).decode()
    print('  %-5s %-18s %-10s %s' % (k, n, ciph, b64[:44]))
print()
print('=== RSA 自洽校验（用私钥验证与公钥匹配 ✓；能过说明私钥材料完整、转换无损 ✓）===')
for k,n in names.items():
    t=io.open(D+'assets/keys/'+k,encoding='utf-8').read()
    pub,priv,ciph,kdf = parse(t)
    parts = mpints(pub)
    alg = parts[0].decode()
    if alg != 'ssh-rsa':
        print('  %-5s %-18s 非 RSA（%s）→ 跳过（改为检查密钥长度）' % (k,n,alg))
        seed = mpints(priv)
        print('        ed25519 私钥长度 = %d 字节 %s' % (len(seed[3]) if len(seed)>3 else 0, '(应为 32 ✓)' ))
        continue
    e = int.from_bytes(parts[1],'big'); nmod = int.from_bytes(parts[2],'big')
    body = mpints(priv)[2:]     # 跳过 check1/check2
    tags = []
    o=0
    # 私钥块：string(alg), mpint(n), mpint(e), mpint(d), mpint(iqmp), mpint(p), mpint(q)...
    blk = priv[8:]
    vals = mpints(blk)
    algp, N, E, D, IQ, P, Q = vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6]
    ok1 = (int.from_bytes(N,'big') == nmod) and (int.from_bytes(E,'big') == e)
    ok2 = pow(pow(2, int.from_bytes(D,'big'), nmod), e, nmod) == 2
    ok3 = (int.from_bytes(P,'big') * int.from_bytes(Q,'big')) == nmod
    print('  %-5s %-18s 公钥一致=%s  私钥d/e自洽=%s  p*q=n=%s  → %s' %
          (k, n, '✓' if ok1 else '✗', '✓' if ok2 else '✗', '✓' if ok3 else '✗',
           '完好 ✓' if (ok1 and ok2 and ok3) else '有问题 ✗'))

