# -*- coding: utf-8 -*-
import base64, hashlib, struct, io
D='/storage/emulated/0/openpilot/c3shell/'
def parse(t):
    b=base64.b64decode(''.join(t.strip().split('\n')[1:-1]))
    assert b.startswith(b'openssh-key-v1\x00'), '头不对'
    o=15
    def rd(o):
        n=struct.unpack('>I', b[o:o+4])[0]; return b[o+4:o+4+n], o+4+n
    cipher,o = rd(o); kdf,o = rd(o); salt,o = rd(o)
    nk = struct.unpack('>I', b[o:o+4])[0]; o+=4
    pub,o = rd(o)
    priv,o = rd(o)
    return pub, priv, nk
def mpints(b, limit=None):
    o=0; out=[]
    while o+4 <= len(b) and (limit is None or len(out) < limit):
        n=struct.unpack('>I', b[o:o+4])[0]; o+=4
        if o+n > len(b): break
        out.append(b[o:o+n]); o+=n
    return out
names={'k1':'神牛','k2':'雨落倾城','k3':'老门新密钥(本机)','k4':'斌哥密钥','k5':'斌哥密钥2','k6':'救援密钥','k7':'门总新密钥','k8':'门老板老密钥'}
pubs={}; mods={}
print('  资产  名称                  nkeys  公钥md5前10   公钥sha256前20')
for k,n in names.items():
    t=io.open(D+'assets/keys/'+k,encoding='utf-8').read()
    pub,priv,nk = parse(t)
    pubs[k]=pub
    parts = mpints(pub)
    alg = parts[0].decode()
    if alg=='ssh-rsa':
        mods[k]=parts[2].hex()[:40]
    print('  %-5s %-18s %-6d %-14s %s' % (k,n,nk, hashlib.md5(pub).hexdigest()[:10], hashlib.sha256(pub).hexdigest()[:20]))
print()
print('=== 重复检测（按完整公钥 ✓）===')
seen={}
for k in names:
    h=hashlib.sha256(pubs[k]).hexdigest()
    if h in seen: print('  ✗ %s(%s) 与 %s(%s) 是**同一把钥匙**（公钥完全相同）' % (k,names[k],seen[h],names[seen[h]]))
    else: seen[h]=k
print()
print('=== RSA 模数前 40 位 hex（同一把应完全相同 ✓）===')
for k in ('k3','k7'):
    print('  %-4s %-18s %s' % (k, names[k], mods.get(k,'(非RSA)')))
print()
print('=== 私钥自洽（转换是否无损 ✓）===')
for k,n in names.items():
    t=io.open(D+'assets/keys/'+k,encoding='utf-8').read()
    pub,priv,nk = parse(t)
    vals = mpints(priv, 9)
    if vals[0].decode()!='ssh-rsa':
        print('  %-5s %-18s ed25519（种子 %d 字节 %s）' % (k,n,len(vals[3]),'✓' if len(vals[3])==32 else '✗'))
        continue
    N=int.from_bytes(vals[1],'big'); E=int.from_bytes(vals[2],'big'); Dd=int.from_bytes(vals[3],'big')
    P=int.from_bytes(vals[5],'big'); Q=int.from_bytes(vals[6],'big')
    ok = (P*Q==N) and (pow(pow(2,Dd,N),E,N)==2)
    print('  %-5s %-18s 公钥/私钥自洽 %s' % (k,n,'✓ 完好' if ok else '✗ 有问题'))

