#!/usr/bin/env bash
# 可选 · 一次性设置：每日自动更新 EdgeLab skills（cron 每天调 update.sh）
# 用法：在 elab-skills 目录里跑一次  bash install-autoupdate.sh
# 取消：crontab -e 删掉含 elab-skills/update.sh 的那行
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"

if ! command -v crontab >/dev/null 2>&1; then
  echo "❌ 没有 crontab。手动更新用：bash update.sh"; exit 1
fi

HOUR="${1:-9}"   # 默认每天 09:00，可传参数改，如 bash install-autoupdate.sh 21
LINE="0 ${HOUR} * * * cd '$REPO' && bash update.sh >> '$REPO/.update.log' 2>&1"

# 去重旧行后写入
( crontab -l 2>/dev/null | grep -v "elab-skills.*update.sh" || true; echo "$LINE" ) | crontab -

echo "✅ 已设置：每天 ${HOUR}:00 自动 git pull + 同步到 ~/.claude/skills/"
echo "   日志：$REPO/.update.log"
echo "   取消：crontab -e 删掉含 update.sh 那行"
echo
echo "⚠️ 自动更新 = 主理人 push 后你这边静默跟进最新版。想先看变更再更，别开这个，改用手动 bash update.sh + 看 CHANGELOG。"
