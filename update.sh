#!/usr/bin/env bash
# EdgeLab skills 一键更新：拉最新 + 同步到已安装的 skills 目录
# 支持 Claude Code / Codex / CodeBuddy / WorkBuddy，检测到哪个 runtime 就同步哪个
# 用法：在 elab-skills 目录里跑  bash update.sh
set -euo pipefail
cd "$(cd "$(dirname "$0")" && pwd)"

OLD_HEAD="$(git rev-parse HEAD)"
echo "== 1/3 拉取最新 =="
if ! git pull --ff-only; then
  echo "❌ git pull 失败（多半本地有改动）。先 'git stash' 或 'git status' 看一下再重跑。"
  exit 1
fi

echo
echo "== 2/3 本次拉到的更新 =="
if [ "$OLD_HEAD" != "$(git rev-parse HEAD)" ]; then
  git log --oneline "${OLD_HEAD}..HEAD"
else
  echo "(已是最新，无新提交)"
fi
echo
echo "-- 当前版本表 + 最新条目（CHANGELOG 顶部）--"
sed -n '1,42p' CHANGELOG.md 2>/dev/null || echo "(无 CHANGELOG)"

echo
echo "== 3/3 同步到已安装的 skills 目录 =="
SYNCED=0
for DEST in "$HOME/.claude/skills" "$HOME/.codex/skills" \
            "$HOME/.codebuddy/skills" "$HOME/.workbuddy/skills"; do
  # 只同步"该 runtime 存在或此处已装过 elab"的目录，不硬造
  RUNTIME_DIR="$(dirname "$DEST")"
  [ -d "$RUNTIME_DIR" ] || [ -e "$DEST/elab" ] || continue
  mkdir -p "$DEST"
  if [ -L "$DEST/elab" ]; then
    # 软链安装：git pull 已让软链指向的源更新，无需拷贝；只补 _shared 软链兜底
    [ -e "$DEST/_shared" ] || ln -sfn "$(pwd)/_shared" "$DEST/_shared"
    echo "✅ $DEST：软链安装，git pull 已自动生效。"
  else
    # 复制安装：逐个 rm 再 cp，干净覆盖（避免 cp -R 进已存在目录产生嵌套）
    for d in elab elab-* _shared; do
      [ -e "$d" ] || continue
      rm -rf "${DEST:?}/$d"
      cp -R "$d" "$DEST/"
    done
    echo "✅ $DEST：复制安装，已覆盖同步（含 _shared）。"
  fi
  SYNCED=1
done
if [ "$SYNCED" = 0 ]; then
  echo "⚠️ 未发现任何支持的 runtime，跳过同步。手动把 elab* + _shared 拷进你 agent 的 skills 目录（见 README §安装）。"
fi

echo
echo "🎉 更新完成。当前版本见 CHANGELOG.md 顶部版本表。"
