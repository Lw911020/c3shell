#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""c3shell 发布页生成器（2026-09-24）

作用：一条命令生成「下载页 + 二维码 + APK」三件套，可以直接丢到任何静态托管上。

用法：
    python3 tools/publish.py --url https://xxx.tcloudbaseapp.com/dl        # 生成到 dist/
    python3 tools/publish.py --url https://xxx.tcloudbaseapp.com/dl --out dist

生成：
    dist/index.html              下载页（自带二维码，单文件、无外链 ✓）
    dist/c3shell-<版本>.apk      安装包
    dist/qr.png                  APK 直链二维码（备用，页面里已内嵌一份 ✓）

内容全部从仓库里读，不手写版本/大小：
    AndroidManifest.xml  → 版本号 / versionCode
    releases/*.apk       → 包大小
    assets/CHANGELOG-lite.md → 最新一段「重要更新」说明
"""
import argparse, base64, io, os, re, shutil, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_version():
    s = io.open(os.path.join(ROOT, 'AndroidManifest.xml'), encoding='utf-8').read()
    ver = re.search(r'android:versionName="([^"]+)"', s)
    code = re.search(r'android:versionCode="(\d+)"', s)
    return (ver.group(1) if ver else '?'), (code.group(1) if code else '?')


def read_notes(limit=6):
    """取精简版日志里 v3.00 系列的最新几条（重要功能/修复 ✓）"""
    p = os.path.join(ROOT, 'assets', 'CHANGELOG-lite.md')
    out = []
    try:
        for line in io.open(p, encoding='utf-8'):
            line = line.strip()
            if not line.startswith('- '):
                continue
            if line.startswith('- **v3.00') or line.startswith('- **v2.'):
                out.append(line[2:])
            if len(out) >= limit:
                break
    except Exception as e:
        out.append('（读取更新说明失败：%s）' % e)
    return out


def apk_path(ver):
    p = os.path.join(ROOT, 'releases', 'c3shell-%s.apk' % ver)
    if os.path.exists(p):
        return p
    p2 = os.path.join(ROOT, 'c3shell.apk')
    if os.path.exists(p2):
        return p2
    raise SystemExit('找不到 APK：先跑 bash build.sh')


def make_qr(data):
    """返回 (png bytes, data-uri)；没装 segno 就退化成 None（页面隐藏二维码 ✓）"""
    try:
        import segno
    except ImportError:
        print('  ! 没装 segno → 不生成二维码（pip install segno 即可）')
        return None, None
    buf = io.BytesIO()
    segno.make(data, error='m').save(buf, kind='png', scale=6, border=2, dark='#111827', light='#ffffff')
    b = buf.getvalue()
    return b, 'data:image/png;base64,' + base64.b64encode(b).decode('ascii')


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>C3 控制台 · 下载（v__VER__）</title>
<style>
  :root{--bg:#f5f7fa;--card:#ffffff;--fg:#1f2430;--dim:#6b7280;--acc:#1f6feb;--line:#e5e7eb;--ok:#12a150}
  @media (prefers-color-scheme: dark){
    :root{--bg:#0f1218;--card:#161b22;--fg:#e6edf3;--dim:#8b949e;--acc:#2f81f7;--line:#243040}
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);
       font:15px/1.7 -apple-system,BlinkMacSystemFont,"Noto Sans SC","Microsoft YaHei",sans-serif}
  .wrap{max-width:720px;margin:0 auto;padding:28px 18px 60px}
  h1{font-size:22px;margin:0 0 4px}
  .sub{color:var(--dim);font-size:13px;margin-bottom:22px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;margin-bottom:16px;
        box-shadow:0 1px 2px rgba(0,0,0,.04),0 8px 24px rgba(0,0,0,.05)}
  .ver{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
  .ver b{font-size:26px}
  .pill{font-size:12px;padding:2px 10px;border-radius:999px;background:rgba(31,111,235,.12);color:var(--acc)}
  .meta{color:var(--dim);font-size:13px;margin-top:6px}
  a.dl{display:block;text-align:center;text-decoration:none;background:var(--acc);color:#fff;font-weight:600;
       padding:14px;border-radius:12px;margin-top:16px;font-size:16px}
  a.dl:active{opacity:.85}
  ul{margin:8px 0 0;padding-left:20px}
  li{margin:4px 0}
  .qr{display:flex;gap:18px;align-items:center;flex-wrap:wrap}
  .qr img{width:168px;height:168px;image-rendering:pixelated;border:1px solid var(--line);border-radius:12px;background:#fff;padding:6px}
  .steps{color:var(--dim);font-size:13px;margin:0;padding-left:20px}
  code{background:rgba(127,127,127,.14);padding:1px 6px;border-radius:6px;font-size:13px}
  .foot{color:var(--dim);font-size:12px;text-align:center;margin-top:26px}
</style>
</head>
<body>
<div class="wrap">
  <h1>C3 控制台</h1>
  <div class="sub">给 comma 三/五（C3/C3X）辅助驾驶设备用的手机端控制台 · 内置服务，装完即用</div>

  <div class="card">
    <div class="ver">
      <b>v__VER__</b>
      <span class="pill">versionCode __CODE__</span>
    </div>
    <div class="meta">安装包 __SIZE__ MB · 更新日期 __DATE__ · 支持 Android 4.4+</div>
    <a class="dl" href="__APK__" download>下载 APK（v__VER__）</a>
  </div>

  <div class="card">
    <div><b>这次更新了什么</b></div>
    <ul>
__NOTES__
    </ul>
  </div>

  <div class="card">
    <div><b>手机扫码直接装</b></div>
    <div class="qr" style="margin-top:12px">
      __QRIMG__
      <ol class="steps">
        <li>手机相机 / 微信扫一扫，对准左边二维码</li>
        <li>打开后点「下载 APK」</li>
        <li>首次安装会提示「允许安装未知应用」→ 允许即可</li>
        <li>装完打开 App，添加主机（默认 C3 设备），点「测试连接」</li>
      </ol>
    </div>
    __QRNOTE__
  </div>

  <div class="card">
    <div><b>装完之后</b></div>
    <ul>
      <li>连设备：SSH 控制台 → 主机管理 → 测试连接（内置密钥，不用配 SSH）</li>
      <li>看曲线：运行曲线 → 开始采样；调参数：参数设置 → 下发（自动备份，可回滚）</li>
      <li>有问题：软件设置 → 问题反馈（可以直接上传给我）</li>
    </ul>
  </div>

  <div class="foot">C3 控制台 · 本页由 <code>tools/publish.py</code> 自动生成，改版本/换地址重跑一次即可</div>
</div>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True, help='线上基础地址，例如 https://xxx.tcloudbaseapp.com/dl（不要结尾斜杠）')
    ap.add_argument('--out', default=os.path.join(ROOT, 'dist'))
    a = ap.parse_args()
    base = a.url.rstrip('/')
    ver, code = read_version()
    apk = apk_path(ver)
    size_mb = os.path.getsize(apk) / 1048576.0
    apk_name = 'c3shell-%s.apk' % ver

    os.makedirs(a.out, exist_ok=True)
    shutil.copyfile(apk, os.path.join(a.out, apk_name))

    apk_url = '%s/%s' % (base, apk_name)
    qr_png, qr_uri = make_qr(apk_url)
    if qr_png:
        io.open(os.path.join(a.out, 'qr.png'), 'wb').write(qr_png)
        qrimg = '<img src="%s" alt="扫码下载 v%s">' % (qr_uri, ver)
        qrnote = '<div class="meta" style="margin-top:10px">二维码指向：<code>%s</code></div>' % apk_url
    else:
        qrimg = ''
        qrnote = '<div class="meta">（本机没装 segno，未生成二维码：<code>pip install segno</code>）</div>'

    notes = '\n'.join('      <li>%s</li>' % re.sub(r'\*\*', '', n) for n in read_notes())
    html = (PAGE.replace('__VER__', ver).replace('__CODE__', str(code))
                .replace('__SIZE__', '%.2f' % size_mb)
                .replace('__DATE__', datetime.date.today().isoformat())
                .replace('__APK__', apk_name)
                .replace('__NOTES__', notes)
                .replace('__QRIMG__', qrimg)
                .replace('__QRNOTE__', qrnote))
    io.open(os.path.join(a.out, 'index.html'), 'w', encoding='utf-8').write(html)

    print('发布页已生成 → %s' % a.out)
    print('  版本      : v%s (code %s)' % (ver, code))
    print('  安装包    : %s  (%.2f MB)' % (apk_name, size_mb))
    print('  线上地址  : %s' % base)
    print('  下载直链  : %s' % apk_url)
    print('  二维码    : %s' % ('qr.png + 页面内嵌 ✓' if qr_png else '未生成 ✗'))
    print('  上传这三样: index.html / %s / qr.png' % apk_name)


if __name__ == '__main__':
    main()
