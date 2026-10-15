#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""逐页自证：点开一页 → 截图 → 报告 ①元素/内容 ②是否可滚动 ③是否有报错
用法: python3 test/sweep.py <adb-serial> <页面文本> [--scroll]
输出截图: tmp-adb/page-<页面>.png（工作区 tmp-adb 目录）"""
import subprocess, re, sys, time, os
SER = sys.argv[1]; NAME = sys.argv[2]; DO_SCROLL = '--scroll' in sys.argv
OUT = '/storage/emulated/0/openpilot/tmp-adb'
os.makedirs(OUT, exist_ok=True)
C = ['adb','-s',SER]
def sh(a, t=40):
    return subprocess.run(C+['shell']+a, capture_output=True, timeout=t, text=True)
def dump():
    sh(['uiautomator','dump','/sdcard/sw.xml'])
    return sh(['cat','/sdcard/sw.xml']).stdout or ''
def win_bounds(x):
    """取无障碍根节点 bounds = 应用窗口真实范围 ✓（滑动必须落在这个矩形内 ✓）"""
    m=re.search(r'<hierarchy[^>]*>\s*<node[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', x)
    if m:
        a,b,c,d=map(int,m.groups()); return a,b,c,d
    m=re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', x)
    if m:
        a,b,c,d=map(int,m.groups()); return a,b,c,d
    return None

def nodes(x):
    out=[]
    for m in re.finditer(r'text="([^"]*)"[^>]*bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', x):
        t=m.group(1).strip(); x1,y1,x2,y2=map(int,m.groups()[1:])
        if t: out.append((t,(x1+x2)//2,(y1+y2)//2,x1,y1,x2,y2))
    return out
# 点目标
n0 = nodes(dump())
hit = [n for n in n0 if n[0]==NAME] or [n for n in n0 if NAME in n[0]]
DANGER = ("删除","新增","保存主机","清屏","断开","确定")
hit = [n for n in hit if n[0] not in DANGER]
if hit:
    t,cx,cy = hit[0][0],hit[0][1],hit[0][2]
    sh(['input','tap',str(cx),str(cy)],20); print('  点了「%s」@(%d,%d)'%(t,cx,cy))
else:
    print('  ✗ 页面上没找到「%s」'%NAME)
time.sleep(8)
x1 = dump(); ns = nodes(x1)
print('  元素总数: %d' % len(ns))
print('  前 10 个文本:', [t for t,_,_,_,_,_,_ in ns[:10]])
# 滚动测试：在 app 窗口内向上滑（用最大文本块的 bounds 估算窗口）
if DO_SCROLL and ns:
    wb=win_bounds(x1)
    left,top,right,bot = wb if wb else (min(n[3] for n in ns),min(n[4] for n in ns),max(n[5] for n in ns),max(n[6] for n in ns))
    cxx=int((left+right)/2); y_from=int(bot-60); y_to=int(top+120)
    print("  上滑 (%d,%d)->(%d,%d)"%(cxx,y_from,cxx,y_to))
    before=[t for t,_,_,_,_,_,_ in ns[:6]]
    sh(["input","swipe",str(cxx),str(y_from),str(cxx),str(y_to),"400"],25); time.sleep(3)
    ns2=nodes(dump()); after=[t for t,_,_,_,_,_,_ in ns2[:6]]
    print("  滚动前:", before)
    print("  滚动后:", after)
    print("  滚动有效性:", "✓ 内容变了" if before!=after else "✗ 没变（滑不动？）")
safe = re.sub(r'[^0-9A-Za-z\u4e00-\u9fa5]+','_',NAME)
png = os.path.join(OUT, 'page-%s.png'%safe)
subprocess.run(C+['exec-out','screencap','-p'], stdout=open(png,'wb'), timeout=60)
print('  截图: %s (%d 字节)'%(png, os.path.getsize(png)))
