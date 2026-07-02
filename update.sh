#!/usr/bin/env bash
# EdgeLab skills 一键更新：拉最新 + 同步到 ~/.claude/skills/
# 用法：在 elab-skills 目录里跑  bash update.sh
set -euo pipefail
cd "$(cd "$(dirname "$0")" && pwd)"

echo "== 1/3 拉取最新 =="
if ! git pull --ff-only; then
  echo "❌ git pull 失败（多半本地有改动）。先 'git stash' 或 'git status' 看一下再重跑。"
  exit 1
fi

echo
echo "== 2/3 本次变更（CHANGELOG 顶部）=="
sed -n '1,42p' CHANGELOG.md 2>/dev/null || echo "(无 CHANGELOG)"

DEST="$HOME/.claude/skills"
mkdir -p "$DEST"
echo
echo "== 3/3 同步到 $DEST =="
if [ -L "$DEST/elab" ]; then
  # 软链安装：git pull 已让软链指向的源更新，无需拷贝；只补 _shared 软链兜底
  [ -e "$DEST/_shared" ] || ln -sfn "$(pwd)/_shared" "$DEST/_shared"
  echo "✅ 软链安装：git pull 已自动生效，无需 cp。"
else
  # 复制安装：逐个 rm 再 cp，干净覆盖（避免 cp -R 进已存在目录产生嵌套）
  for d in elab elab-* _shared; do
    [ -e "$d" ] || continue
    rm -rf "${DEST:?}/$d"
    cp -R "$d" "$DEST/"
  done
  echo "✅ 复制安装：已覆盖同步（含 _shared）。"
fi

echo
echo "🎉 更新完成。当前版本见 CHANGELOG.md 顶部版本表。"
