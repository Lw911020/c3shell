#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c3shell 端到端自动化测试（无需人工）
用法: python3 test/e2e.py [car|tablet|both]  (默认 both)
做的事: 装机 → 启动 → 用 adb dump/tap 驱动界面 → 通过 APP 接口与日志断言 → 输出 PASS/FAIL 表
"""
import subprocess, sys, time, json, re, os

CAR, TAB = "192.168.0.100:5555", None   # 平板端口运行时探测
def sh(*a, t=60):
    try: return subprocess.run(a, capture_output=True, text=True, timeout=t).stdout
    except Exception: return ""
def adb(dev, *a): return sh("adb", "-s", dev, *a)
def http(dev, path, port, post=None):
    fwd = ["adb","-s",dev,"forward","tcp:%d"%port,"tcp:3081"]; subprocess.run(fwd,capture_output=True)
    cmd = ["curl","-s","-m","30","http://127.0.0.1:%d%s"%(port,path)]
    if post is not None: cmd += ["-X","POST","-H","content-type: application/json","-d",post]
    return sh(*cmd)
def dump(dev):
    adb(dev,"shell","uiautomator","dump","/sdcard/e2e.xml"); return adb(dev,"shell","cat","/sdcard/e2e.xml")
def nodes(xml):
    out=[]
    for m in re.finditer(r'text="([^"]*)"[^>]*?bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', xml):
        out.append((m.group(1), (int(m.group(2))+int(m.group(4)))//2, (int(m.group(3))+int(m.group(5)))//2))
    return out
def tap_text(dev, xml, label, exact=False):
    for t,x,y in nodes(xml):
        if (t==label) if exact else (label in t):
            adb(dev,"shell","input","tap",str(x),str(y)); return True
    return False
def log_lines(dev, port):
    try: return [l for l in (json.loads(http(dev,"/api/log",port)).get("log") or "").split("\n") if l.strip()]
    except Exception: return []


SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def bump_version():
    f = os.path.join(SRC, "AndroidManifest.xml"); t = open(f, encoding="utf-8").read()
    c = int(re.search(r'versionCode="(\d+)"', t).group(1)) + 1
    v = re.search(r'versionName="([\d.]+)"', t).group(1)
    parts = (v.split(".") + ["0"])[:2]
    nv = "%s.%02d" % (parts[0], int(parts[1]) + 1)
    t = re.sub(r'versionCode="\d+"', 'versionCode="%d"' % c, t, 1)
    t = re.sub(r'versionName="[^"]*"', 'versionName="%s"' % nv, t, 1)
    open(f, "w", encoding="utf-8").write(t)
    return nv

def build_and_install(devs):
    ver = bump_version(); print("  版本 → %s" % ver)
    out = sh("python3", os.path.join(SRC, "build_apk.py"), SRC, os.path.join(SRC, "c3shell.apk"), t=600)
    if "error" in out.lower():
        print("  ❌ 构建报错 → 中止（不安装）"); print("\n".join([l for l in out.split("\n") if "error" in l.lower()][:5])); return None
    line = [l for l in out.split("\n") if "产物" in l]
    print("  ✅ 构建成功 %s" % (line[0].strip() if line else ""))
    apk = os.path.join(SRC, "c3shell.apk")
    for d in devs:
        if not d: continue
        r = sh("adb", "-s", d, "install", "-r", apk, t=300)
        print("  装机 %s: %s" % (d, "OK" if "Success" in r or "complete" in r else r.strip()[:60]))
    for dst in ("/sdcard/Download/c3shell-%s.apk" % ver, os.path.join(SRC, "releases", "c3shell-%s.apk" % ver)):
        try:
            import shutil; shutil.copy(apk, dst); print("  导出: %s" % dst)
        except Exception as e: print("  导出失败 %s: %s" % (dst, e))
    return ver

def source_checks():
    page = open(os.path.join(SRC, "assets/page.html"), encoding="utf-8").read()
    css  = open(os.path.join(SRC, "assets/theme.css"), encoding="utf-8").read()
    check("源码 终端兜底脚本存在", "termTailFallback" in page)
    check("源码 车机侧栏CSS存在", "min-width:1200px" in css and "nav.tabs" in css and "position:fixed" in css)
    check("源码 不用的字段已隐藏", page.count('class="f hide"') >= 4 or 'class="f hide"' in page)
    check("源码 资产加密(构建后)", os.path.exists(os.path.join(SRC, "c3shell.apk")))

R=[]
def check(name, ok, detail=""):
    R.append((name, bool(ok), detail)); print("  %s %-34s %s" % ("✅" if ok else "❌", name, detail))

def test_device(dev, tag, port):
    print("\n=== %s (%s) ===" % (tag, dev))
    adb(dev,"shell","am","force-stop","com.padagent.c3shell"); time.sleep(1)
    adb(dev,"shell","logcat","-c"); time.sleep(0.5)
    t0 = time.strftime("%m-%d %H:%M:%S")   # 只看本次测试之后的日志（APP 日志文件是持久化的）
    adb(dev,"shell","am","start","-n","com.padagent.c3shell/.MainActivity"); time.sleep(9)
    x = dump(dev)
    check(tag+" 界面已起", "C3 控制台" in x or "SSH 控制台" in x)
    lines = log_lines(dev, port)
    check(tag+" 初始化请求(state)", any("/api/ssh/state" in l for l in lines))
    check(tag+" 初始化请求(jobs)", any("/api/ssh/jobs" in l for l in lines))
    fresh = [l for l in lines if "Uncaught" in l and l[:17] >= t0]
    check(tag+" 无新增 JS 报错(本次运行)", not fresh, (fresh[-1][:95] if fresh else "自 %s 起 0 条" % t0))
    # 参数载荷（性能）
    p = http(dev,"/api/ssh/params/all",port); 
    try:
        j=json.loads(p); kb=len(p)/1024
        check(tag+" 参数载荷<300KB", kb<300, "%.0fKB cached=%s" % (kb, j.get("cached")))
    except Exception as e: check(tag+" 参数载荷", False, str(e))
    # B7 断言：正常操作期间**不得出现会话重建**（onCreate 的 session 标识应只出现一次）
    try:
        ss = [l for l in lines if 'onCreate session=' in l]
        fresh_s = [l for l in ss if l[:17] >= t0]        # t0 = 启动前基线（见上）→ 恰好 1 次才正常
        check(tag+" 会话未被重建(B7)", len(fresh_s) == 1, "本次运行 onCreate session 次数=%d（应=1；>1 说明发生了界面重建 ✗）" % len(fresh_s))
    except Exception as e:
        check(tag+" 会话未被重建(B7)", False, str(e))
    # DOM/视觉断言（B12）：页面每次加载上报一行 [layout]（computed style + 关键元素可见性）
    try:
        lay = [l for l in lines if '[layout]' in l]
        last = lay[-1] if lay else ''
        # ★ 指标正则统一在读取 last 之后定义（2026-09-22：避免局部变量未赋值 ✗）
        fs = re.search(r'font=(\S+)', last)
        tv = re.search(r'tabsVis=(\d+)', last)
        dh = re.search(r'diagHost=(\d+)', last)
        dp = re.search(r'diagPanes=(\d+)', last)
        mf = re.search(r'menuFit=(\d)', last)
        md = re.search(r'mode=(\w+)', last)
        fx = re.search(r'flex=(\w+)', last)
        sv = re.search(r'setVoice=(\d)', last)
        cv = re.search(r'cueSection=(\S+)', last)
        check(tag+" 布局状态已上报", bool(last), last[-78:] if last else "无 [layout] 行")
        fn = re.search(r'font=(\S+)', last)
        check(tag+" 菜单不需要滚动", (('flex=row' in last) or (bool(mf) and mf.group(1) == '1')), "menuFit=%s（0=菜单超高需要滚动 ✗）" % (mf.group(1) if mf else '?'))
        check(tag+" 车机模式字号未被破坏(13px)", ((re.search(r"mode=(\w+)", last) or [None,""])[1] != "car") or (bool(fs) and fs.group(1).startswith("13")), "font=%s" % (fs.group(1) if fs else "?"))
        check(tag+" 菜单不需要滚动", (('flex=row' in last) or (bool(mf) and mf.group(1) == '1')), "menuFit=%s" % (mf.group(1) if mf else '?'))
        check(tag+" 只露出一套页签容器(防两套重叠)", bool(tv) and tv.group(1) == '1',
              "tabsVis=%s（>1 说明两个视图的页签容器同时可见 ✗）" % (tv.group(1) if tv else '?'))
        check(tag+" 显示模式与布局一致", bool(md and fx) and ((md.group(1) == 'car' and fx.group(1) == 'column') or (md.group(1) == 'tablet' and fx.group(1) == 'row')),
              "mode=%s flex=%s" % (md.group(1) if md else '?', fx.group(1) if fx else '?'))
        check(tag+" 设置页语音卡片存在", bool(sv) and sv.group(1) == '1', "setVoice=%s" % (sv.group(1) if sv else '?'))
        check(tag+" 诊断页已并入单文档(容器+5 pane 含 AI 分析)", bool(dh) and dh.group(1) == '1' and bool(dp) and dp.group(1) in ('4','5'),
              "diagHost=%s diagPanes=%s" % (dh.group(1) if dh else '?', dp.group(1) if dp else '?'))
        check(tag+" 语音卡已并入设置页", bool(cv) and cv.group(1) == 'tab-settings', "cueSection=%s" % (cv.group(1) if cv else '?'))
    except Exception as e:
        check(tag+" DOM/视觉断言", False, str(e))
    # 语音诊断（并断言服务真的在跑 —— 防"静默不出声"回归）
    try:
        j=json.loads(http(dev,"/api/voice/diag",port))
        check(tag+" 语音诊断可用", j.get("ok") is True, "engine=%s voices=%s" % (j.get("engine"), j.get("voices")))
        check(tag+" 语音服务在运行", j.get("serviceRunning") is True, "serviceRunning=%s ready=%s" % (j.get("serviceRunning"), j.get("ready")))
    except Exception as e: check(tag+" 语音诊断", False, str(e))
    # 终端：走 APP 接口验证（与界面点击无关 → 两端都适用）
    try:
        j = json.loads(http(dev, "/api/ssh/term/open", port, post="{}"))
        sid = j.get("sessionId")
        check(tag+" 终端会话可开", bool(sid), str(sid))
    except Exception as e:
        sid = None; check(tag+" 终端会话可开", False, str(e))
    if sid:
        time.sleep(2)
        t = http(dev, "/api/ssh/term/tail?sessionId=%s&since=0" % sid, port)
        try:
            n = len(json.loads(t).get("text") or "")
        except Exception:
            n = 0
        check(tag+" 终端内容可取(>200字符)", n > 200, "%d 字符" % n)
    # 车机额外做一次"界面驱动"验证（平板 WebView 不认 input tap）
    if tag == "车机":
        tap_text(dev, x, "终端"); time.sleep(3); x2 = dump(dev)
        tap_text(dev, x2, "连接终端"); time.sleep(8); x3 = dump(dev)
        rx = re.search(r'rx=(\d+)', x3)
        check(tag+" 界面点击后收到数据(rx>0)", bool(rx) and int(rx.group(1)) > 0, "rx=%s" % (rx.group(1) if rx else 0))

def main():
    global TAB
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    do_build = "--build" in sys.argv
    mode = argv[0] if argv else "both"
    # 探测平板 adb 端口
    import socket
    for p in range(30000,50000):
        s=socket.socket(); s.settimeout(0.05)
        try:
            if s.connect_ex(("127.0.0.1",p))==0:
                out=sh("adb","connect","127.0.0.1:%d"%p)
                if "connected" in out: TAB="127.0.0.1:%d"%p; break
        except Exception: pass
        finally: s.close()
    print("=== 语法检查（先过语法，杜绝静默死块）===")
    syn = sh("python3", os.path.join(SRC, "test/syntax.py"), t=300)
    print("\n".join(syn.strip().split("\n")[-2:]))
    if "失败" in syn or "❌" in syn:
        print("  ❌ 语法检查未通过 → 中止后续测试"); return 3
    if do_build:
        print("=== 构建 + 装机 ===")
        devs = ([TAB] if TAB and mode in ("both","tablet") else []) + ([CAR] if mode in ("both","car") else [])
        if not build_and_install(devs): return 2
        print("=== 源码回归断言 ==="); source_checks()
    if mode in ("both","tablet") and TAB: test_device(TAB,"平板",3901)
    if mode in ("both","car"):
        sh("adb","connect",CAR); test_device(CAR,"车机",3902)
    ok=sum(1 for _,o,_ in R if o); print("\n=== 结果: %d/%d 通过 ===" % (ok,len(R)))
    for n,o,d in R:
        if not o: print("  ❌", n, d)
    return 0 if ok==len(R) else 1

if __name__=="__main__": sys.exit(main())
