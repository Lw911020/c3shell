# -*- coding: utf-8 -*-
import sys, importlib.util
spec = importlib.util.spec_from_file_location('pngcrop', '/storage/emulated/0/openpilot/c3shell/tools/pngcrop.py')
m = importlib.util.module_from_spec(spec); sys.argv = ['x','/dev/null','/dev/null','0','0','1','1']
try: spec.loader.exec_module(m)
except BaseException: pass
W,H,ch,rows = m.decode('/storage/emulated/0/openpilot/c3shell/_attic/now/v136_cast_full.png')
print('screen', W, H)
# 统计每行"纯黑"像素数（y>1700 的 APP 窗口区）
prof = []
for y in range(1700, H):
    r = rows[y]; c = 0
    for x in range(0, W):
        o = x*ch
        if r[o] <= 16 and r[o+1] <= 16 and r[o+2] <= 16: c += 1
    prof.append((y, c))
mx = max(c for _, c in prof)
bandrows = [y for y, c in prof if c > mx*0.8]
print('纯黑行峰值像素数 =', mx)
if bandrows:
    print('黑带行范围: %d .. %d  共 %d 行' % (bandrows[0], bandrows[-1], len(bandrows)))
    # 找出黑带的左右边界（取中位行）
    mid = bandrows[len(bandrows)//2]
    r = rows[mid]
    xs = [x for x in range(W) if r[x*ch] <= 16 and r[x*ch+1] <= 16 and r[x*ch+2] <= 16]
    print('该黑带: x %d..%d (宽 %d 设备 = %.0f CSS @2.5)' % (xs[0], xs[-1], xs[-1]-xs[0]+1, (xs[-1]-xs[0]+1)/2.5))
    print('画面区（黑带顶→底）高 = %d 设备 = %.0f CSS' % (bandrows[-1]-bandrows[0]+1, (bandrows[-1]-bandrows[0]+1)/2.5))
    print('窗口顶 1658 → 黑带顶 %d = 控制区 %.0f CSS' % (bandrows[0], (bandrows[0]-1658)/2.5))
    print('窗口底 3421 → 黑带底 %d 差 %d 设备' % (bandrows[-1], 3421-bandrows[-1]))
# 逐行黑像素轮廓（每 40 行采样）
print('--- 轮廓（y: 黑像素数）---')
for y, c in prof[::60]:
    print(' ', y, c)
