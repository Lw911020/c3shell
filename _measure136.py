# -*- coding: utf-8 -*-
import sys, importlib.util
spec = importlib.util.spec_from_file_location('pngcrop', '/storage/emulated/0/openpilot/c3shell/tools/pngcrop.py')
m = importlib.util.module_from_spec(spec)
sys.argv = ['x', '/dev/null', '/dev/null', '0', '0', '1', '1']
try: spec.loader.exec_module(m)
except BaseException: pass
W, H, ch, rows = m.decode('/storage/emulated/0/openpilot/c3shell/_attic/now/v136_cast_full.png')
print('screen', W, H)
x1, x2 = int(W*0.15), int(W*0.85); span = x2-x1
cands = []
for y in range(1500, H):
    r = rows[y]; black = 0
    for x in range(x1, x2):
        o = x*ch
        if r[o] <= 16 and r[o+1] <= 16 and r[o+2] <= 16: black += 1
    if black > span*0.9: cands.append(y)
if cands:
    top, bot = cands[0], cands[-1]
    r = rows[cands[len(cands)//2]]
    xs = [x for x in range(W) if r[x*ch] <= 16 and r[x*ch+1] <= 16 and r[x*ch+2] <= 16]
    DPR = 2.5
    print('画面区: 设备像素 高=%d 宽=%d  → CSS 高=%.0f 宽=%.0f' % (bot-top+1, xs[-1]-xs[0]+1, (bot-top+1)/DPR, (xs[-1]-xs[0]+1)/DPR))
    print('画面区顶部距窗口顶(1658): %d 设备 = %.0f CSS（=控制区高度）' % (top-1658, (top-1658)/DPR))
    print('窗口底=3421 → 画面区可见高度 %.0f CSS（区域总高 %.0f）' % ((3421-top)/DPR, (bot-top+1)/DPR))
else:
    print('未找到纯黑带')
