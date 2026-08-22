#!/usr/bin/env bash
# EdgeLab Skills 一键安装 · by 杰尼马（EdgeLab）
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
cd "$REPO"

# runtime key | 显示名 | 配置目录 | skills 目录
RUNTIMES=(
  "claude|Claude Code|$HOME/.claude|$HOME/.claude/skills"
  "codex|OpenAI Codex|$HOME/.codex|$HOME/.codex/skills"
  "codebuddy|CodeBuddy|$HOME/.codebuddy|$HOME/.codebuddy/skills"
  "workbuddy|WorkBuddy|$HOME/.workbuddy|$HOME/.workbuddy/skills"
)

MODE=copy
LIST_ONLY=0
WANT=()

for arg in "$@"; do
  case "$arg" in
    --link) MODE=link ;;
    --copy) MODE=copy ;;
    --list) LIST_ONLY=1 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    -*) echo "❌ 未知参数：$arg（-h 看用法）"; exit 1 ;;
    *) WANT+=("$arg") ;;
  esac
done

# 待装的 skill 目录（elab 入口 + 各子 skill + 共享契约）
UNITS=()
for d in elab elab-* _shared; do
  [ -d "$d" ] && UNITS+=("$d")
done
if [ "${#UNITS[@]}" -eq 0 ]; then
  echo "❌ 当前目录没有 elab* 目录。请在 elab-skills 仓库根目录里跑这个脚本。"
  exit 1
fi

echo "EdgeLab Skills · by 杰尼马（EdgeLab）"
echo "源目录：$REPO"
echo "待装 ${#UNITS[@]} 项：${UNITS[*]}"
echo

FOUND=0
INSTALLED=0
for row in "${RUNTIMES[@]}"; do
  IFS='|' read -r key label conf dest <<<"$row"

  # 指定了 runtime 就只装指定的
  if [ "${#WANT[@]}" -gt 0 ]; then
    hit=0
    for w in "${WANT[@]}"; do [ "$w" = "$key" ] && hit=1; done
    [ "$hit" = 1 ] || continue
  fi

  # 没装这个 agent 就跳过，不硬造目录（除非用户显式点名）
  if [ ! -d "$conf" ] && [ "${#WANT[@]}" -eq 0 ]; then
    printf "  ·  %-14s 未安装，跳过\n" "$label"
    continue
  fi
  FOUND=1

  if [ "$LIST_ONLY" = 1 ]; then
    printf "  ✓  %-14s → %s\n" "$label" "$dest"
    continue
  fi

  mkdir -p "$dest"
  for d in "${UNITS[@]}"; do
    rm -rf "${dest:?}/$d"
    if [ "$MODE" = link ]; then
      ln -sfn "$REPO/$d" "$dest/$d"
    else
      cp -R "$d" "$dest/"
    fi
  done
  printf "  ✅ %-14s → %s（%s）\n" "$label" "$dest" \
    "$([ "$MODE" = link ] && echo 软链 || echo 复制)"
  INSTALLED=$((INSTALLED + 1))
done

echo
if [ "$FOUND" = 0 ]; then
  echo "⚠️ 没识别到任何支持的 agent。"
  echo "   手动装：把 elab* 和 _shared 拷进你 agent 的 skills 目录即可（见 README §安装）。"
  echo "   连 skill 机制都没有的 agent 也能用：让它读 elab/SKILL.md 当入口，按需读各子 skill。"
  exit 0
fi

[ "$LIST_ONLY" = 1 ] && exit 0

echo "🎉 已装到 $INSTALLED 个 runtime。"
if [ "$MODE" = link ]; then
  echo "   软链模式：以后在本目录 git pull，所有 runtime 自动跟着更新。"
  echo "   ⚠️ 别把本目录挪走或删掉，软链会断。"
else
  echo "   复制模式：更新用 bash update.sh（拉最新 + 重新同步）。"
fi
echo
echo "怎么用：Claude Code 敲 /elab，Codex 敲 \$elab，其他 agent 直接说「帮我看看这笔交易」。"
echo "开源地址 github.com/edgelab101/elab-skills · 公众号 杰尼马"
