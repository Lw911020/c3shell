# -*- coding: utf-8 -*-
"""量投屏画面区（纯黑底）的实际像素高宽 —— 用 pngcrop 的 decode，不依赖 PIL"""
import sys, importlib.util
spec = importlib.util.spec_from_file_location('pngcrop', '/storage/emulated/0/openpilot/c3shell/tools/pngcrop.py')
m = importlib.util.module_from_spec(spec)
sys.argv = ['pngcrop.py', '/dev/null', '/dev/null', '0', '0', '1', '1']   # 防止它执行裁剪主体
try:
    spec.loader.exec_module(m)
except SystemExit:
    pass
except Exception:
    pass

path = sys.argv[0] if False else '/storage/emulated/0/openpilot/c3shell/_attic/now/v135_cast_full.png'
W, H, ch, rows = m.decode(path)
print('screen', W, H, 'ch', ch)
x1, x2 = int(W*0.15), int(W*0.85)
span = x2 - x1
cands = []
for y in range(1500, H):
    r = rows[y]
    black = 0
    for x in range(x1, x2):
        o = x*ch
        if r[o] <= 16 and r[o+1] <= 16 and r[o+2] <= 16:
            black += 1
    if black > span*0.9:
        cands.append(y)
if not cands:
    print('未找到纯黑带（画面可能贴边）'); sys.exit(0)
top, bot = cands[0], cands[-1]
# 该黑带行的左右边界 = 画面区宽度
r = rows[cands[len(cands)//2]]
xs = [x for x in range(W) if r[x*ch] <= 16 and r[x*ch+1] <= 16 and r[x*ch+2] <= 16]
print('黑带行数(上下带合计)', len(cands))
print('画面区 设备像素: 高=%d 宽=%d  比例=%.3f' % (bot-top+1, xs[-1]-xs[0]+1, (bot-top+1)/(xs[-1]-xs[0]+1)))
print('若 CSS 宽=838 则 CSS 高≈%.0f px  (目标 ≥500)' % ((bot-top+1)/((xs[-1]-xs[0]+1)/838.0)))
