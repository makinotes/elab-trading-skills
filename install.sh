#!/usr/bin/env bash
# EdgeLab Trading Skills 一键安装 · by 杰尼马（EdgeLab）
#
# 自动识别你机器上装了哪些 agent，把 elab* + _shared 装进各自的 skills 目录。
#
#   bash install.sh                     # 自动识别，全部安装（复制模式）
#   bash install.sh --link              # 软链模式：git pull 后自动生效，不用重装
#   bash install.sh claude codex        # 只装指定 runtime
#   bash install.sh --list              # 只看识别结果，不动文件
#
# 支持：claude（Claude Code）· codex（OpenAI Codex）· codebuddy（CodeBuddy）· workbuddy（WorkBuddy）
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
command -v python3 >/dev/null 2>&1 || { echo "安装需要 Python 3.9+。"; exit 1; }
MODE=copy
LIST=()
WANT=()
for arg in "$@"; do
  case "$arg" in
    --link) MODE=link ;;
    --copy) MODE=copy ;;
    --list) LIST=(--list) ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    claude|codex|codebuddy|workbuddy) WANT+=("$arg") ;;
    *) echo "未知参数：$arg（-h 看用法）"; exit 1 ;;
  esac
done
[ -f "$REPO/_shared/SUITE_VERSION" ] || { echo "安装源缺少 _shared/SUITE_VERSION。"; exit 1; }
SUITE_VERSION="$(tr -d '[:space:]' < "$REPO/_shared/SUITE_VERSION")"
# Python performs all ownership checks before staging or replacing any runtime.
# These expansions also work with macOS Bash 3.2 and empty arrays under nounset.
python3 "$REPO/scripts/install_runtime.py" --source "$REPO" --version "$SUITE_VERSION" \
  --mode "$MODE" ${LIST[@]+"${LIST[@]}"} ${WANT[@]+"${WANT[@]}"}
