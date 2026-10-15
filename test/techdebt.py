#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技术债度量（TECHDEBT.md 的可执行版）：每条给出 PASS/FAIL → 用于"先红后绿"闭环。
用法: python3 test/techdebt.py
"""
import os, re, sys
SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def rd(p):
    try: return open(os.path.join(SRC, p), encoding='utf-8').read()
    except Exception: return ""
page, diag, css = rd('assets/page.html'), rd('assets/diag.html'), rd('assets/theme.css')
R = []
def chk(item, desc, ok, val):
    R.append((item, desc, bool(ok), val))
# ── A 结构性 ──
ids_p = set(re.findall(r'id="([A-Za-z0-9_\-]+)"', page)); ids_d = set(re.findall(r'id="([A-Za-z0-9_\-]+)"', diag))
chk('A1', '两页 id 冲突=0（合并前置）', not (ids_p & ids_d), '冲突 %s' % (sorted(ids_p & ids_d) or '无'))
chk('A1b', '/diag 已并入单一文档（diag.html 不再独立）', False if diag else True, 'diag.html %d 字节' % len(diag))
chk('A2', 'page/diag 内不再内联 askConfirm', 'function askConfirm' not in page and 'function askConfirm' not in diag, 'page=%d diag=%d' % (page.count('function askConfirm'), diag.count('function askConfirm')))
chk('A2b', 'page/diag 内不再内联 nestedMenu', '/* nestedMenu' not in page and '/* nestedMenu' not in diag, 'page=%d diag=%d' % (page.count('/* nestedMenu'), diag.count('/* nestedMenu')))
add_p = len(re.findall(r'<script>\s*/\*', page)); add_d = len(re.findall(r'<script>\s*/\*', diag))
MARKS = ['nestedMenu','busyCache','sideEditor','fsFilterHook','moveOpsCards','termStatObserver']
left = [m for m in MARKS if m in page or m in diag]
chk('A3', '追加模块已全部收编（标记残留=0）', not left, '公共模块 %d 个 · 残留 %s' % (len(re.findall(r'src="app/[^"]+\.js"', page + diag)), left or '无'))
dm_ok = ('data-displaymode' in rd('assets/app/displaymode.js')) and (css.count('min-width:900px') == 0)
chk('A4', '显示模式为显式设置（无 900px heuristic）', dm_ok, 'heuristic=%d 次 · displaymode.js=%s' % (css.count('min-width:900px'), 'data-displaymode' in rd('assets/app/displaymode.js')))
imp = css.count('!important')
chk('A5', '!important ≤ 20（现 %d）' % imp, imp <= 20, '%d 处' % imp)
# ── B 功能债 ──
refs = sum(page.count(x) for x in ("f_pw", "f_root", "f_extra", "f_note"))
chk('B1', '被隐藏的字段真删（无 hide 行/无 JS 引用）', refs == 0 and 'class="f hide"' not in page, 'hide行=%d JS引用=%d' % (page.count('class="f hide"'), refs))
silent = len(re.findall(r'catch\s*\([A-Za-z_]*\)\s*\{\s*\}', page)) + len(re.findall(r'catch\s*\([A-Za-z_]*\)\s*\{\s*\}', diag))
chk('B8', '静默吞错 ≤ 10（现 %d）' % silent, silent <= 10, '%d 处' % silent)
mv = rd('java/com/padagent/c3shell/MainActivity.java')
chk('B6', '版本号单一来源（原生已移除，非隐藏）', ('hideNativeVer' not in mv) and ('removeNativeVersion' in mv), 'hideNativeVer=%d removeNativeVersion=%d' % (mv.count('hideNativeVer'), mv.count('removeNativeVersion')))
chk('B12', 'e2e 含 DOM/视觉断言', '[layout]' in rd('test/e2e.py'), '需在 e2e 中加入元素可见性/布局断言')
mn = rd('assets/app/menu.js')
nv = rd('assets/app/nav.js')
chk('D1', '统一数据层 /api/store（服务端+客户端+使用）', ('/api/store' in rd('java/com/padagent/c3shell/Api.java')) and ('window.Store' in rd('assets/app/store.js')) and ('Store.' in rd('assets/app/displaymode.js')), 'Api=%s store.js=%s' % ('/api/store' in rd('java/com/padagent/c3shell/Api.java'), 'window.Store' in rd('assets/app/store.js')))
chk('D2', '菜单按视图选容器（防诊断子菜单丢失回归）', ('diagHost' in mn) and ('data-view' in mn) and ('/diag/' in mn), 'diagHost=%s data-view=%s' % ('diagHost' in mn, 'data-view' in mn))
chk('D3', '菜单由统一配置驱动（NAV + menu 读取）', ('window.NAV' in nv) and ('window.NAV' in mn), 'nav.js=%d 字节 menu读取NAV=%s' % (len(nv), 'window.NAV' in mn))
tj = rd('assets/theme.js')
mvsrc = rd('java/com/padagent/c3shell/MainActivity.java')
calls = [l for l in mvsrc.split('\n') if 'recreate();' in l and not l.strip().startswith('//')]
mvsrc = rd('java/com/padagent/c3shell/MainActivity.java')
calls = [l for l in mvsrc.split('\n') if 'recreate();' in l and not l.strip().startswith('//')]
chk('D4', '主题切换不触发 APP 重建（无 c3shell://theme、无 recreate 调用）', ('c3shell://theme' not in tj) and (len(calls) == 0), 'theme通知=%s recreate调用=%d' % ('c3shell://theme' in tj, len(calls)))
chk('D5', 'onCreate 记录会话标识（可判"是否被重建"）',
    'session=' in rd('java/com/padagent/c3shell/MainActivity.java'),
    'session 日志=%s' % ('session=' in rd('java/com/padagent/c3shell/MainActivity.java')))
dp = rd('assets/app/diagpage.js')
init_line = [l for l in dp.split('\n') if l.strip().startswith('mkParams();')]
heavy_on_init = any(('readCurated()' in l or 'devstat()' in l or 'listFiles()' in l or 'jobsList()' in l) for l in init_line)
chk('D6', '诊断页重活按需加载（初始不得直跑 4 件重活）', (not heavy_on_init) and ('__lazyLoad' in dp), '初始重活=%s 懒加载=%s' % (heavy_on_init, '__lazyLoad' in dp))
pg = rd('assets/page.html')
chk('D7', '终端按能力选单一渲染器（无"3 秒猜"、xterm 条件加载）',
    ('__TERM_PLAIN' in pg) and ('__TERM_PLAIN' in rd('assets/app/displaymode.js')) and ('3 秒仍没有内容' not in pg) and ('xterm.js"><' not in pg[:200000] or 'document.write' in pg),
    'TERM_PLAIN=%s 猜测段残留=%s' % ('__TERM_PLAIN' in pg, '3 秒仍没有内容' in pg))
ap = rd('java/com/padagent/c3shell/Api.java')
chk('D8', '语音包生成+推送一体化（收包/推送/客户端）',
    ('/api/voice/import' in ap) and ('/api/voice/push' in ap) and ('voicepush.js' in pg),
    'import=%s push=%s 客户端=%s' % ('/api/voice/import' in ap, '/api/voice/push' in ap, 'voicepush.js' in pg))
csssrc = rd('assets/theme.css')
chk('D9', '非激活视图的页签容器被隐藏（防两套左栏重叠）',
    ('data-view="diag"] nav.tabs' in csssrc) and ('data-view="console"] #diagHost' in csssrc or 'data-view="diag"] #diagHost' in csssrc),
    '隐藏规则=%s' % ('data-view="diag"] nav.tabs' in csssrc))
chk('D10', '统计状态透明可控（设置页可见 + 可开关）',
    ('/api/stats' in ap) and ('statsinfo.js' in pg), 'api=%s 客户端=%s' % ('/api/stats' in ap, 'statsinfo.js' in pg))
import subprocess as _sp
try:
    _cr = _sp.run(['python3', os.path.join(SRC, 'test/contrast.py')], capture_output=True, text=True, timeout=60).stdout
    _crok = ('全部达标' in _cr)
except Exception:
    _crok = False
chk('D11', '浅色主题对比度全部达标（WCAG 计算 ✓）', _crok, '见 test/contrast.py 输出')
ok = sum(1 for _,_,o,_ in R if o)
for it,d,o,v in R:
    print('  %s %-4s %-38s %s' % ('✅' if o else '❌', it, d, v))
print('\n  技术债: %d/%d 条已闭环' % (ok, len(R)))
sys.exit(0 if ok == len(R) else 1)
