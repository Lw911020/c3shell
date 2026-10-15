#!/data/data/com.dsharnessmobile.shell/files/usr/bin/bash
# c3shell 一键构建/发布（在**平板**上跑；产物给**手机**装）
#
# 用法:
#   bash build.sh            # 用当前版本号构建，导出到 releases/ 和 /sdcard/Download/
#   bash build.sh 1.6        # 先把版本改成 1.6（versionCode 自动 +1）再构建
set -eo pipefail
D=/storage/emulated/0/openpilot/c3shell
# 用工作区里那份**已打补丁**的构建器（支持 libs/*.jar 与 assets/）；
# niw/apks 那份是原始版，不含这些改动。
BUILDER=/storage/emulated/0/openpilot/c3shell/build_apk.py
NEWVER="$1"
TRIAL="$2"
if [ "$NEWVER" = "trial" ] || [ "$NEWVER" = "--trial" ]; then TRIAL="trial"; NEWVER=""; fi
SUF=""
if [ "$TRIAL" = "trial" ] || [ "$TRIAL" = "--trial" ]; then
  TRIAL="trial"; SUF="-体验版"; export C3_TRIAL=1      # → build_apk.py 写 TrialInfo.java（倒计时体验期，默认 3 天）
  echo "  构建类型: 体验版（体验期由构建决定，默认 2026-09-25 08:00 → 2026-09-28 08:00，3 天 / 72 小时）"
else
  export C3_TRIAL=0
  echo "  构建类型: 正式版"
fi

cd "$D"
if [ -n "$NEWVER" ]; then
  python3 - "$NEWVER" <<'PY'
import re, sys
new = sys.argv[1]
p = '/storage/emulated/0/openpilot/c3shell/AndroidManifest.xml'
s = open(p, encoding='utf-8').read()
m = re.search(r'android:versionCode="(\d+)"', s)
code = (int(m.group(1)) + 1) if m else 1
s = re.sub(r'android:versionCode="\d+"', 'android:versionCode="%d"' % code, s)
s = re.sub(r'android:versionName="[^"]*"', 'android:versionName="%s"' % new, s)
open(p, 'w', encoding='utf-8').write(s)
print('  版本 → %s(%d)' % (new, code))
PY
fi

VER=$(python3 -c "
import re;s=open('$D/AndroidManifest.xml',encoding='utf-8').read()
print(re.search(r'android:versionName=\"([^\"]+)\"',s).group(1))")
CODE=$(python3 -c "
import re;s=open('$D/AndroidManifest.xml',encoding='utf-8').read()
print(re.search(r'android:versionCode=\"([^\"]+)\"',s).group(1))")

echo "[1/3] 构建（$VER / code $CODE）"
BUILD_LOG=$(mktemp)
if ! python3 "$BUILDER" "$D" "$D/c3shell.apk" >"$BUILD_LOG" 2>&1; then
  echo "  ✗ 构建失败，未导出任何包。错误如下："
  grep -E "error|错误|失败" "$BUILD_LOG" | head -12
  exit 1
fi
tail -2 "$BUILD_LOG"
if ! grep -q "产物" "$BUILD_LOG"; then
  echo "  ✗ 没看到成功标志，按失败处理（不导出）"; tail -5 "$BUILD_LOG"; exit 1
fi

echo "[2/3] 导出"
mkdir -p "$D/releases"
OUT="$D/releases/c3shell-$VER$SUF.apk"
cp -f "$D/c3shell.apk" "$OUT"
# R8 混淆映射表（解混淆堆栈用；存在才拷）
[ -f "$D/c3shell.apk.mapping.txt" ] && cp -f "$D/c3shell.apk.mapping.txt" "$D/releases/c3shell-$VER$SUF-mapping.txt" && echo "     映射表: releases/c3shell-$VER$SUF-mapping.txt"
PHONE="/sdcard/Download/c3shell-$VER$SUF.apk"
cp -f "$D/c3shell.apk" "$PHONE" 2>/dev/null && echo "     平板下载目录: $PHONE（手机可直接取）" || echo "     复制到 /sdcard/Download 失败（不影响 releases/）"

echo "[3/3] 完成"
ls -la "$OUT" | awk '{print "     产物: "$9" ("$5" 字节)"}'
echo "     源码/构建都在平板: $D"
