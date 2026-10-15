# -*- coding: utf-8 -*-
"""R68：AI 分析页四处修复
① 扫描进度每条都写（原来每 25 条才写 → 小范围看不到）
② 综合分析改成"等路线扫完，一次性出全部结果"
③ 报告：大数据平台按钮=下载（新增 /api/save 写到系统下载目录），去掉「导出到「下载」」
④ 本地规则建议：加容错 + 立即反馈（原来点了可能静默失败）
"""
import io, os
D = '/storage/emulated/0/openpilot/c3shell'

# ── ① 设备侧扫描脚本：进度每条都写 ────────────────────────────────
SR = os.path.join(D, 'assets/remote/scan_routes.py')
s = io.open(SR, encoding='utf-8').read()
old1 = """    per_seg = []
    for i, d in enumerate(dirs):"""
new1 = """    per_seg = []
    # 2026-09-24 R68：开扫先写一条 0 进度（进度条立刻出现 ✓）
    if args.progress:
        try:
            with open(args.progress, 'w') as pf:
                pf.write(json.dumps({'scanned': 0, 'total': len(dirs), 'pct': 0.0, 'cur': '', 'elapsedS': 0, 'etaS': None}))
        except OSError:
            pass
    for i, d in enumerate(dirs):"""
assert s.count(old1) == 1, 'scan_routes 定位1失败'
s = s.replace(old1, new1)
old2 = """        if args.progress and (i + 1) % 25 == 0:
            try:
                with open(args.progress, 'w') as pf:
                    pf.write(json.dumps({'scanned': i + 1, 'total': len(dirs),
                                         'pct': round(100.0 * (i + 1) / max(1, len(dirs)), 1),
                                         'elapsedS': round(time.time() - t_start, 1),
                                         'etaS': round((time.time() - t_start) / max(1, i + 1) * (len(dirs) - i - 1), 1)}))
            except OSError:
                pass"""
new2 = """        # 2026-09-24 R68：**每条都写进度**（原来 %25 → 扫 6 条时全程看不到进度 ✗）
        if args.progress:
            try:
                with open(args.progress, 'w') as pf:
                    pf.write(json.dumps({'scanned': i + 1, 'total': len(dirs),
                                         'pct': round(100.0 * (i + 1) / max(1, len(dirs)), 1),
                                         'cur': os.path.basename(d)[:44],
                                         'elapsedS': round(time.time() - t_start, 1),
                                         'etaS': round((time.time() - t_start) / max(1, i + 1) * (len(dirs) - i - 1), 1)}))
            except OSError:
                pass"""
assert s.count(old2) == 1, 'scan_routes 定位2失败'
s = s.replace(old2, new2)
io.open(SR, 'w', encoding='utf-8').write(s)
print('OK  scan_routes.py 进度每条都写')

# ── ② page.html ──────────────────────────────────────────────────
P = os.path.join(D, 'assets/page.html')
h = io.open(P, encoding='utf-8').read()
def rep(old, new, tag):
    global h
    assert h.count(old) == 1, tag + ': count=' + str(h.count(old))
    h = h.replace(old, new); print('OK  ' + tag)

# ②-1 进度文案带上"正在读哪条"
rep("""          showProgress(pr.pct||0, '扫描中 '+(pr.scanned||0)+'/'+(pr.total||'?')+'（'+(pr.pct||0)+'%）'+eta+'　← 可以切到别的页面，回来会接着显示 ✓');""",
"""          var cur=pr.cur?(' · 正在读 '+pr.cur):'';
          showProgress(pr.pct||0, '扫描中 '+(pr.scanned||0)+'/'+(pr.total||'?')+' 条（'+(pr.pct||0)+'%）'+cur+eta+'　← 可以切页面，回来接着显示 ✓');""",
    'pollScan 显示当前条')

# ②-2 新增 waitScanDone()：等扫描真正结束再返回结果（不立刻渲染）
rep("""  function routeScan(){""",
"""  /* 2026-09-24 R68：等扫描**真正结束**再返回结果（综合分析要"一次性出全部" ✓） */
  function waitScanDone(){
    return new Promise(function(resolve){
      var t0=Date.now();
      (function tick(){
        fetch('/api/ssh/routes/scan/status').then(function(r){return r.json()}).then(function(j){
          var pr=(j&&j.progress)||null;
          if(pr){
            var eta=''; if(pr.etaS>0) eta=(pr.etaS>90?('　约还要 '+(pr.etaS/60).toFixed(1)+' 分钟'):('　约还要 '+Math.round(pr.etaS)+' 秒'));
            var cur=pr.cur?(' · 正在读 '+pr.cur):'';
            showProgress(pr.pct||0, '扫描中 '+(pr.scanned||0)+'/'+(pr.total||'?')+' 条（'+(pr.pct||0)+'%）'+cur+eta);
          } else showProgress(3,'正在启动扫描…');
          if(j&&j.result){ showProgress(100,'✓ 扫描完成'); resolve(j.result); return; }
          if(Date.now()-t0 > 6*60*1000){ resolve(null); return; }
          setTimeout(tick, 1500);
        }).catch(function(){ setTimeout(tick, 2000); });
      })();
    });
  }
  function routeScan(){""", '新增 waitScanDone()')

# ②-3 综合分析：等路线扫完 → 一次性渲染
rep("""    var pRt=fetch('/api/ssh/routes/scan/status').then(function(r){return r.json()}).then(function(j){
      if(j&&j.progress && !j.result){ try{ showProgress(j.progress.pct||0,'后台扫描进行中…（进度见下方 ✓）'); pollScan(); }catch(e){} return; }
      try{ showProgress(2,'开始扫描最近路线（1~3 分钟，进度见下方 ✓）'); }catch(e){}
      try{ routeScan(); }catch(e){}
    }).catch(function(){});
    Promise.all([pStat,pAll,pRt]).then(function(){
      renderAll(out);""",
"""    var pRt=fetch('/api/ssh/routes/scan/status').then(function(r){return r.json()}).then(function(j){
      if(j&&j.progress && !j.result){ /* 后台已在扫 → 直接等它结束 ✓ */ }
      else { try{ showProgress(2,'开始扫描最近路线（1~3 分钟，进度见下方 ✓）'); routeScan(); }catch(e){} }
      return waitScanDone();
    }).then(function(res){ if(res) LASTROUTE=res; }).catch(function(){});
    Promise.all([pStat,pAll,pRt]).then(function(){
      /* 2026-09-24 R68：等三路都齐了再一次性渲染（用户要求"综合分析一起出来"✓） */
      renderAll(out);""", '综合分析等扫完再渲染')

io.open(P, 'w', encoding='utf-8').write(h)

# ── ③ Java：新增 /api/save（把文本写到系统「下载」目录）──────────
AP = os.path.join(D, 'java/com/padagent/c3shell/Api.java')
a2 = io.open(AP, encoding='utf-8').read()
anchor = """        if (path.equals("/api/log")) {"""
add = """        // 2026-09-24 R68：页面把文本写进系统「下载」目录（体检报告下载 ✓）
        if (path.equals("/api/save")) {
            String name = jstr(body, "name");
            if (name == null || name.length() == 0) name = "c3-report-" + System.currentTimeMillis() + ".txt";
            String text = jstr(body, "text");
            if (text == null) return "{\\"ok\\":false,\\"error\\":{\\"message\\":\\"text 必填\\"}}";
            String saved = null;
            try {
                byte[] bytes = text.getBytes("UTF-8");
                try {
                    Class<?> dl = Class.forName("android.provider.MediaStore$Downloads");
                    android.net.Uri ext = (android.net.Uri) dl.getField("EXTERNAL_CONTENT_URI").get(null);
                    android.content.ContentValues cv = new android.content.ContentValues();
                    cv.put("_display_name", name);
                    cv.put("mime_type", "text/plain");
                    try { cv.put("relative_path", "Download/"); } catch (Throwable ignore) { }
                    android.net.Uri item = ctx.getContentResolver().insert(ext, cv);
                    if (item != null) {
                        java.io.OutputStream os = ctx.getContentResolver().openOutputStream(item);
                        os.write(bytes); os.flush(); os.close();
                        saved = "下载/" + name;
                    }
                } catch (Throwable ignore) { }
                if (saved == null) {
                    java.io.File d = ctx.getExternalFilesDir(null);
                    if (d == null) d = ctx.getFilesDir();
                    java.io.File f = new java.io.File(d, name);
                    java.io.FileOutputStream fo = new java.io.FileOutputStream(f);
                    fo.write(bytes); fo.flush(); fo.close();
                    saved = f.getAbsolutePath();
                }
            } catch (Throwable e) { return "{\\"ok\\":false,\\"error\\":{\\"message\\":\\"" + Ssh.esc(String.valueOf(e.getMessage())) + "\\"}}"; }
            Logs.add("SAVE", "报告已写入 " + saved);
            return "{\\"ok\\":true,\\"path\\":\\"" + Ssh.esc(saved) + "\\"}";
        }
        if (path.equals("/api/log")) {"""
assert a2.count(anchor) == 1, 'Api.java 锚点失败'
a2 = a2.replace(anchor, add)
io.open(AP, 'w', encoding='utf-8').write(a2)
print('OK  Api.java 新增 /api/save')
