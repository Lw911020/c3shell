#!/system/bin/sh
# 打开 C3 控制台 —— 按"点桌面图标"的方式启动 ✓
#
# 2026-09-22 用户要求（原话："打开 mt管理器旁边的，不要去底部那个"）：
#   桌面上 MT管理器 旁边的「C3 控制台」图标 = 正常启动，窗口落在用户想要的位置 ✓
#   而我之前用的  am start -f 0x10001000（FLAG_ACTIVITY_LAUNCH_ADJACENT）
#   会被系统塞到"旁边那一格"（曾出现落到下面/底部）—— 不再使用 ✓
ADB_SERIAL=""
if [ -z "$ADB_SERIAL" ]; then
  P=$(cat "$HOME/tmp/adbport" 2>/dev/null)
  [ -z "$P" ] && P=37209
  ADB_SERIAL="127.0.0.1:$P"
fi
echo "[open_app] 用启动器意图打开 C3 控制台（serial=$ADB_SERIAL）"
adb -s "$ADB_SERIAL" shell am start \
  -a android.intent.action.MAIN \
  -c android.intent.category.LAUNCHER \
  -n com.padagent.c3shell/.MainActivity

