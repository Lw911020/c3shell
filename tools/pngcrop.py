# -*- coding: utf-8 -*-
"""pngcrop.py —— 纯 Python PNG 裁剪+放大（不依赖 PIL）
用法: pngcrop.py in.png out.png x1 y1 x2 y2 [scale]
坐标可用 0~1 的小数表示比例 ✓"""
import sys, zlib, struct

def decode(path, stop_y=None):
    d = open(path, 'rb').read()
    assert d[:8] == b'\x89PNG\r\n\x1a\n', 'not png'
    o = 8; idat = []; w = h = bd = ct = None
    while o < len(d):
        ln = struct.unpack('>I', d[o:o+4])[0]; typ = d[o+4:o+8]; data = d[o+8:o+8+ln]; o += 12 + ln
        if typ == b'IHDR': w, h, bd, ct, comp, filt, inter = struct.unpack('>IIBBBBB', data)
        elif typ == b'IDAT': idat.append(data)
        elif typ == b'IEND': break
    raw = zlib.decompress(b''.join(idat))
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ct]
    stride = w * ch
    rows = []; prev = bytearray(stride); pos = 0
    ymax = h if stop_y is None else min(h, stop_y)
    for y in range(ymax):
        f = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos+stride]); pos += stride
        if f == 1:
            for i in range(ch, stride): line[i] = (line[i] + line[i-ch]) & 255
        elif f == 2:
            for i in range(stride): line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i-ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i-ch] if i >= ch else 0
                bb = prev[i]; c = prev[i-ch] if i >= ch else 0
                p = a + bb - c; pa = abs(p-a); pb = abs(p-bb); pc = abs(p-c)
                pr = a if (pa <= pb and pa <= pc) else (bb if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        rows.append(bytes(line)); prev = line
    return w, h, ch, rows

def encode(path, w, h, ch, rows):
    ct = {1: 0, 3: 2, 4: 6}[ch]
    raw = b''.join(b'\x00' + r for r in rows)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, ct, 0, 0, 0)
    def chunk(t, data):
        return struct.pack('>I', len(data)) + t + data + struct.pack('>I', zlib.crc32(t + data) & 0xffffffff)
    out = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
    open(path, 'wb').write(out)

src, dst = sys.argv[1], sys.argv[2]
a = [float(x) for x in sys.argv[3:7]]
scale = int(sys.argv[7]) if len(sys.argv) > 7 else 2
W, H, ch, rows = decode(src)
def px(v, total):
    return int(round(v * total)) if v <= 1 else int(v)
x1, y1, x2, y2 = px(a[0], W), px(a[1], H), px(a[2], W), px(a[3], H)
crop = [r[x1*ch:x2*ch] for r in rows[y1:y2]]
cw, chh = x2 - x1, y2 - y1
if scale > 1:   # 最近邻放大
    big = []
    for r in crop:
        r2 = bytearray()
        for i in range(0, len(r), ch):
            r2 += r[i:i+ch] * scale
        for _ in range(scale): big.append(bytes(r2))
    crop, cw, chh = big, cw*scale, chh*scale
encode(dst, cw, chh, ch, crop)
print('crop', (x1, y1, x2, y2), '->', (cw, chh))

