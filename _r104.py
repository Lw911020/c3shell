# -*- coding: utf-8 -*-
"""R104：手机/平板模式下二级页签也去掉重复项（软件设置 / 参数）"""
import io
D = '/storage/emulated/0/openpilot/c3shell/'
def rd(p): return io.open(D + p, encoding='utf-8').read()
def wr(p, s): io.open(D + p, 'w', encoding='utf-8').write(s)
def sub(s, old, new, tag):
    assert s.count(old) == 1, '%s 未命中 %d' % (tag, s.count(old))
    return s.replace(old, new)

# ① page.html：把 settings 也加进"已在原生一级菜单、二级里不再重复"的名单 ✓
P = 'assets/page.html'
s = rd(P)
s = sub(s, 'html.c3-hide-dup[data-layout="tablet"] nav.tabs button[data-tab="cast"],html.c3-hide-dup[data-layout="tablet"] nav.tabs button[data-tab="aian"],html.c3-hide-dup[data-layout="tablet"] nav.tabs button[data-tab="uiset"]{display:none !important}   /* 手机模式：这三个已在原生一级菜单 ✓ 避免重复 */',
'html.c3-hide-dup[data-layout="tablet"] nav.tabs button[data-tab="cast"],html.c3-hide-dup[data-layout="tablet"] nav.tabs button[data-tab="aian"],html.c3-hide-dup[data-layout="tablet"] nav.tabs button[data-tab="uiset"],html.c3-hide-dup[data-layout="tablet"] nav.tabs button[data-tab="settings"]{display:none !important}   /* 手机模式：这几个已在原生一级菜单 ✓ 避免重复（2026-09-24 R104 补 settings ✓）*/',
'page.html 隐藏 settings 页签')

# ② 平板模式下隐藏"软件设置"卡里的重复入口提示（保留原有文案不动）
wr(P, s)

# ③ diag.html：手机/平板模式下隐藏「参数」页签（它已升为一级菜单 ✓；车机模式由侧边栏过滤 ✓）
P = 'assets/diag.html'
s = rd(P)
s = sub(s, '.tab{padding:7px 14px;border-radius:9px 9px 0 0;background:transparent;border:1px solid transparent;',
'/* 2026-09-24 R104（用户反馈：平板手机模式下菜单没改）：「参数」已提升为一级菜单（原生顶栏「参数设置」✓）')
# 上面那行只是注释，真正的规则插在 .tab 定义之前的独立行
s = s.replace('/* 2026-09-24 R104（用户反馈：平板手机模式下菜单没改）：「参数」已提升为一级菜单（原生顶栏「参数设置」✓）\n.tab{padding:7px 14px;',
              '/* 2026-09-24 R104（用户反馈：平板手机模式下菜单没改）：「参数」已提升为一级菜单（原生顶栏「参数设置」✓）\n   手机/平板模式下二级页签里不再重复显示；车机模式由侧边栏的过滤逻辑处理 ✓ */\nhtml[data-layout="tablet"] .tab[data-p="p3"],html[data-layout="phone"] .tab[data-p="p3"]{display:none !important}\n.tab{padding:7px 14px;')
wr(P, s)
print('OK  R104 完成')
