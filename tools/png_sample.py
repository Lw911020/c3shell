# -*- coding: utf-8 -*-
"""极简 PNG 采样：读 Android screencap 的 PNG，打印若干坐标的 RGB（验证底色是否一致）"""
import zlib, struct, sys

def load_png(path):
    b = open(path,'rb').read()
    assert b[:8] == b'\x89PNG\r\n\x1a\n'
    i, idat, w, h, ct, bd = 8, b'', 0, 0, 0, 0
    while i < len(b):
        ln = struct.unpack('>I', b[i:i+4])[0]; typ = b[i+4:i+8]; data = b[i+8:i+8+ln]
        if typ == b'IHDR':
            w, h, bd, ct = struct.unpack('>IIBB', data[:10])
        elif typ == b'IDAT':
            idat += data
        elif typ == b'IEND':
            break
        i += 12 + ln
    raw = zlib.decompress(idat)
    ch = {0:1, 2:3, 3:1, 4:2, 6:4}[ct]
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        f = raw[pos]; pos += 1
        line = bytearray(raw[pos:pos+stride]); pos += stride
        if f == 1:
            for x in range(ch, stride): line[x] = (line[x] + line[x-ch]) & 255
        elif f == 2:
            for x in range(stride): line[x] = (line[x] + prev[x]) & 255
        elif f == 3:
            for x in range(stride):
                a = line[x-ch] if x >= ch else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:
            for x in range(stride):
                a = line[x-ch] if x >= ch else 0
                c = prev[x-ch] if x >= ch else 0
                p = a + prev[x] - c
                pa, pb, pc = abs(p-a), abs(p-prev[x]), abs(p-c)
                pr = a if (pa <= pb and pa <= pc) else (prev[x] if pb <= pc else c)
                line[x] = (line[x] + pr) & 255
        out[y*stride:(y+1)*stride] = line
        prev = line
    return w, h, ch, out

def px(w,h,ch,out,x,y):
    o = (y*w + x) * ch
    return tuple(out[o:o+3])

path = sys.argv[1]
w,h,ch,out = load_png(path)
print('图片:', w, 'x', h, '通道', ch)
pts = {'输入条左侧(让位处)': (1780, 2185), '输入条本体': (2300, 2185), '网页背景(中部)': (2600, 1200), '左侧栏中部': (1800, 900)}
for name,(x,y) in pts.items():
    if 0 <= x < w and 0 <= y < h:
        print('  %-16s (%d,%d) = #%02X%02X%02X' % ((name,x,y) + px(w,h,ch,out,x,y)))

