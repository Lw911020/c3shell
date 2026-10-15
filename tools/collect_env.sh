#!/bin/sh
# collect_env.sh — C3 设备「系统指纹 + APP 适配面」只读采集（2026-09-24）
#
# 用途：CP / SP2024 / SP2025 等不同 openpilot 系统之间做适配比对。
#       换系统后（或每次系统更新后）在设备上跑一次，把结果留档，
#       再对着 c3shell/ADAPTATION.md 的矩阵填差异。
#
# 运行：sh collect_env.sh [输出目录]      默认 /tmp
# 只读：绝不写 /data、不改设备状态、不启停服务。输出 = stdout + 两个文件
#       <out>/dsh-env-<UTC时间>.txt   （人看的）
#       <out>/dsh-env-<UTC时间>.json  （机器比对的，有 python3 才生成）
#
# 原则：只采事实，不做判断；取不到的项写 unknown，不猜。

OP=/data/openpilot
DSH=$OP/.dsh
OUT=${1:-/tmp}
TS=$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || echo unknown)
TXT="$OUT/dsh-env-$TS.txt"
KV="$OUT/dsh-env-$TS.kv"
: > "$KV"

sec() { printf '\n== %s ==\n' "$1" | tee -a "$TXT"; }
emit() { printf '%-24s %s\n' "$1" "$2" | tee -a "$TXT"; printf '%s\t%s\n' "$1" "$2" >> "$KV"; }
have() { [ -e "$1" ] && echo yes || echo no; }
rd()  { cat "$1" 2>/dev/null | head -c 300; }

echo "collect_env.sh  ts=$TS  host=$(hostname 2>/dev/null)" | tee "$TXT"

sec "1 系统"
emit hostname      "$(hostname 2>/dev/null || echo unknown)"
emit kernel        "$(uname -r 2>/dev/null || echo unknown)"
emit arch          "$(uname -m 2>/dev/null || echo unknown)"
emit os_release    "$(grep -h PRETTY_NAME /etc/os-release 2>/dev/null | cut -d= -f2- | tr -d '\"')"
emit agnos         "$(rd /AGNOS; grep -h AGNOS_VERSION $OP/launch_env.sh 2>/dev/null | head -1)"
emit uptime        "$(uptime 2>/dev/null | tr -s ' ')"
emit comma_service "$(systemctl is-active comma 2>/dev/null || echo unknown)"

sec "2 openpilot 代码"
emit op_path       "$(have $OP)"
emit git_branch    "$(git -C $OP rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
emit git_head      "$(git -C $OP rev-parse HEAD 2>/dev/null || echo unknown)"
emit git_head_date "$(git -C $OP log -1 --format=%ci 2>/dev/null || echo unknown)"
emit git_remote    "$(git -C $OP remote -v 2>/dev/null | head -1)"
emit git_dirty     "$(git -C $OP status --porcelain --untracked-files=no 2>/dev/null | wc -l)"

sec "3 fork 标记（决定 APP 走哪条适配分支）"
for p in selfdrive/carrot selfdrive/frogpilot sunnypilot selfdrive/ui/sunnypilot \
         selfdrive/ui/qt/offroad/settings.cc common/params_keys.h \
         system/manager/manager.py system/manager/process_config.py \
         selfdrive/ui/ui selfdrive/ui/carrot.cc selfdrive/carrot/config.py \
         selfdrive/carrot/nav_params.json; do
  emit "path:$p" "$(have $OP/$p)"
done

sec "4 参数体系"
emit params_link   "$(ls -l /data/params 2>/dev/null | tr -s ' ')"
emit params_d      "$(readlink -f /data/params/d 2>/dev/null || echo unknown)"
emit params_count  "$(ls /data/params/d 2>/dev/null | wc -l)"
emit pkeys_count   "$(grep -c '{' $OP/common/params_keys.h 2>/dev/null || echo unknown)"
emit key_GitBranch "$(rd /data/params/d/GitBranch)"
emit key_GitCommit "$(rd /data/params/d/GitCommit)"
emit key_ActiveModel "$(rd /data/params/d/ActiveModelName)"
emit key_CarFingerprint "$(rd /data/params/d/CarFingerprint)"
emit carrot_key_sample "$(ls /data/params/d 2>/dev/null | grep -Ei 'carrot|frog|sunny|auto|alpha' | head -20 | tr '\n' ' ')"

sec "5 运行时 / python"
for py in /usr/local/venv/bin/python3 $OP/.venv/bin/python3 /usr/bin/python3; do
  if [ -x "$py" ]; then
    emit "py:$py" "ver=$($py -c 'import sys;print(sys.version.split()[0])' 2>/dev/null) capnp=$($py -c 'import capnp' 2>/dev/null && echo yes || echo no) zstd=$($py -c 'import zstandard' 2>/dev/null && echo yes || echo no)"
  fi
done
emit ss_listen     "$(ss -ltn 2>/dev/null | awk 'NR>1{print $4}' | tr '\n' ' ')"

sec "6 界面 / 投屏 / 触控（APP 适配重点）"
emit fb_size       "$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null || echo unknown)"
emit ui_proc       "$(ps -ef 2>/dev/null | grep -E '[/ ]ui\b' | grep -v grep | head -3 | tr -s ' ' | tr '\n' '|')"
emit ui_ldpreload  "$(for p in $(pgrep -x ui 2>/dev/null); do tr '\0' '\n' < /proc/$p/environ 2>/dev/null | grep LD_PRELOAD; done | head -3)"
emit ui_maps_hook  "$(for p in $(pgrep -x ui 2>/dev/null); do grep -c uihook /proc/$p/maps 2>/dev/null; done | tr '\n' ' ')"
emit proc_conf_ui  "$(grep -n "'ui'" $OP/system/manager/process_config.py 2>/dev/null | head -6 | tr '\n' '|')"
emit proc_conf_bak "$(have $OP/system/manager/process_config.py.dsh-bak)"
emit devshm        "$(ls /dev/shm 2>/dev/null | tr '\n' ' ')"

sec "7 设备侧被 APP 推送的资产"
emit dsh_dir       "$(ls $DSH 2>/dev/null | tr '\n' ' ')"
emit profiles      "$(ls $OP/dsh-profiles 2>/dev/null | tr '\n' ' ')"

sec "8 数据 / route"
emit realdata_size "$(du -sh /data/media/0/realdata 2>/dev/null | awk '{print $1}')"
emit routes        "$(ls -d /data/media/0/realdata/*--* 2>/dev/null | wc -l)"

sec "9 混淆 / 编译产物（决定「能改什么」）"
emit so_files      "$(find $OP -maxdepth 3 -name '*.so' 2>/dev/null | head -20 | tr '\n' ' ')"
emit byd_dir       "$(have $OP/opendbc_repo/opendbc/car/byd/values.py)"
emit pyarmor_mark  "$(head -c 60 $OP/opendbc_repo/opendbc/car/byd/values.py 2>/dev/null | tr '\n' ' ')"

if command -v python3 >/dev/null 2>&1; then
  python3 - "$KV" "$OUT/dsh-env-$TS.json" <<'PY'
import json, sys
kv, out = sys.argv[1], sys.argv[2]
d = {}
for line in open(kv, encoding='utf-8', errors='replace'):
    if '\t' in line:
        k, v = line.rstrip('\n').split('\t', 1)
        d[k] = v
json.dump(d, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('\nJSON -> ' + out)
PY
fi
echo "TXT  -> $TXT"
echo "把 TXT 内容贴回来（或回传两个文件）即可填 ADAPTATION.md 的矩阵。"
