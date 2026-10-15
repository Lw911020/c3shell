# -*- coding: utf-8 -*-
"""R71：软件设置（及其它内容页）的卡片跟随屏幕宽度（原来被 .card 的 860px 上限卡住）"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
old = ".card{background:var(--bg2);border:1px solid var(--line);border-radius:12px;width:min(860px,96vw);max-height:92dvh;display:flex;flex-direction:column}"
assert h.count(old) == 1, 'card 规则未命中'
new = old + """
/* 2026-09-24 R71（用户要求）：内容页卡片**跟随屏幕宽度自适应** ✓
   原来 .card 统一 width:min(860px,96vw) → 宽屏（平板/车机大屏）右侧一大片留白 ✗
   只放内容卡片（main section>），弹窗里的 .card 仍用各自的行内宽度 ✓ */
main section>.card{width:auto;max-width:none}"""
h = h.replace(old, new)
io.open(P, 'w', encoding='utf-8').write(h)
print('OK  内容卡片自适应宽度')
