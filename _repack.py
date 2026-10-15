# -*- coding: utf-8 -*-
"""在 2.119 的 APK 上只替换 assets/page.html（打两处补丁），其余原样 → 2.119.2 ✓"""
import io, os, re, sys, zipfile, shutil, subprocess

D = '/storage/emulated/0/openpilot/c3shell/'
SRC = D + 'releases/c3shell-2.119.apk'
WORK = D + '_attic/repack/'
OUT = D + 'releases/c3shell-2.119.2.apk'

KEY = bytes([0x43,0x33,0x53,0x68,0x65,0x6c,0x6c,0x32,0x30,0x32,0x36,0x2d,0x50,0x41,0x44])
def ks(n):
    S = list(range(256)); j = 0
    for i in range(256):
        j = (j + S[i] + KEY[i % len(KEY)]) & 255; S[i], S[j] = S[j], S[i]
    out = bytearray(); i2 = j = 0
    for _ in range(n):
        i2 = (i2 + 1) & 255; j = (j + S[i2]) & 255; S[i2], S[j] = S[j], S[i2]
        out.append(S[(S[i2] + S[j]) & 255])
    return bytes(out)
def enc(data):
    k = ks(len(data)); body = bytes(a ^ b for a, b in zip(data, k))
    s = sum(data) & 0xFFFFFFFF
    return b'C3S1' + len(data).to_bytes(4, 'big') + body + s.to_bytes(4, 'big')
def dec(raw):
    assert raw[:4] == b'C3S1', '不是 C3S1 容器'
    n = int.from_bytes(raw[4:8], 'big'); body = raw[8:8+n]; chk = int.from_bytes(raw[8+n:12+n], 'big')
    data = bytes(a ^ b for a, b in zip(body, ks(n)))
    assert (sum(data) & 0xFFFFFFFF) == chk, '校验失败'
    return data

# 1) 解包原 APK（保留每个条目的压缩方式 ✓）
if os.path.isdir(WORK): shutil.rmtree(WORK)
os.makedirs(WORK)
zin = zipfile.ZipFile(SRC)
items = [(i, zin.read(i.filename)) for i in zin.infolist()]
zin.close()
print('APK 条目:', len(items))

# 2) 解密 page.html
target = 'assets/page.html.enc'
raw = dict((i.filename, b) for i, b in items).get(target)
if raw is None: sys.exit('找不到 ' + target)
html = dec(raw).decode('utf-8')
print('page.html 解密:', len(html), '字符')

# 3) 补丁 ①：resumeScan 用 fetch（原来调未定义的 api ✗）
a = "api('/routes/scan/status',{}).then(function(j){"
b = "fetch('/api/ssh/routes/scan/status').then(function(r){return r.json()}).then(function(j){"
n1 = html.count(a)
html = html.replace(a, b)
print('补丁① resumeScan:', n1, '处')

# 4) 补丁 ②：扫描进行中再点按钮 → 不重启，只继续看进度 ✓
old = "  function routeScan(){"
new = ("  var SCANRUN=false;\n"
       "  function routeScan(){\n"
       "    if(SCANRUN){ try{ showProgress(3,'扫描已在后台进行，继续显示进度…（要重来请先等它结束或刷新页面）'); pollScan(); }catch(e){} return; }  // ✓ 防重复点击重启\n"
       "    SCANRUN=true;")
n2 = html.count(old)
html = html.replace(old, new, 1)
# 结束后解除标志（在完成分支里）
old2 = "          showProgress(100, '✓ 扫描完成');"
new2 = "          SCANRUN=false;\n          showProgress(100, '✓ 扫描完成');"
n3 = html.count(old2)
html = html.replace(old2, new2, 1)
print('补丁② 防重复再启动:', 'routeScan 找到', n2, '处 / 完成分支', n3, '处')
if n1 != 1 or n2 != 1 or n3 != 1: sys.exit('补丁锚点异常，放弃（避免改坏 ✗）')

# 5) 回写：加密 → 替换条目 → 重新打包（保持压缩方式 ✓）
newenc = enc(html.encode('utf-8'))
if os.path.exists(OUT): os.remove(OUT)
zout = zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED)
for info, data in items:
    if info.filename == target:
        data = newenc
    zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    zi.compress_type = info.compress_type
    zi.external_attr = info.external_attr
    zi.internal_attr = info.internal_attr
    zi.create_system = info.create_system
    zout.writestr(zi, data)
zout.close()
print('已重新打包:', OUT, os.path.getsize(OUT), '字节')

