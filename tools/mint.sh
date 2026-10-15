#!/system/bin/sh
# 一条命令发卡（2026-09-25）—— 在**这个 DSH 环境**里跑（私钥只在这个应用的家目录里 ✓）
#
# 用法：  bash /storage/emulated/0/openpilot/c3shell/tools/mint.sh <C3 设备码> [天数=365] [套餐=pro] [序号]
# 例子：  bash /storage/emulated/0/openpilot/c3shell/tools/mint.sh c5f64914
#        bash /storage/emulated/0/openpilot/c3shell/tools/mint.sh c5f64914 30 basic
#
# 也可以直接在对话里跟 AI 说「给 C3-XXXX 发一张一年的卡」，它会用同一条命令签 ✓
D=/storage/emulated/0/openpilot/c3shell
DEV="$1"; DAYS="${2:-365}"; PLAN="${3:-pro}"; SEQ="$4"
if [ -z "$DEV" ]; then
  echo "用法: bash tools/mint.sh <C3 设备码> [天数=365] [套餐=pro] [序号]"
  echo "C3 设备码在 APP 里：软件设置 → 激活 / 授权 → 「C3 设备码」→ 点「读取」"
  exit 1
fi
[ -z "$SEQ" ] && SEQ=$(date +%s | tail -c 5)
python3 "$D/tools/license_mint.py" mint --device "$DEV" --days "$DAYS" --plan "$PLAN" --seq "$SEQ"
