#!/usr/bin/env bash
# EdgeLab Skills 更新/回退：默认拉最新；--to vX.Y.Z 从已发布 tag 安装指定版本。
# 支持 Claude Code / Codex / CodeBuddy / WorkBuddy。
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"

TARGET=""
case "${1:-}" in
  "") ;;
  --to)
    [ "$#" -eq 2 ] || { echo "❌ 用法：bash update.sh --to vX.Y.Z"; exit 1; }
    TARGET="$2"
    ;;
  -h|--help)
    echo "用法：bash update.sh              # 更新到默认分支最新版本"
    echo "      bash update.sh --to vX.Y.Z # 安装/回退到已发布 tag，不改变当前工作树"
    exit 0
    ;;
  *)
    echo "❌ 未知参数：$1（-h 看用法）"
    exit 1
    ;;
esac

SOURCE_ROOT="$REPO"
PINNED=0
TEMP_ROOT=""
cleanup() {
  [ -n "$TEMP_ROOT" ] && [ -d "$TEMP_ROOT" ] && rm -rf "$TEMP_ROOT"
}
trap cleanup EXIT

if [ -n "$TARGET" ]; then
  [[ "$TARGET" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
    echo "❌ 版本必须是 vX.Y.Z，例如 v0.4.0"
    exit 1
  }
  echo "== 1/3 读取已发布版本 $TARGET =="
  # Always refresh from origin. A same-named local tag may be stale, moved locally,
  # or never published; rollback must resolve the immutable published ref.
  git fetch --force origin "+refs/tags/$TARGET:refs/tags/$TARGET"
  git rev-parse --verify "refs/tags/$TARGET^{commit}" >/dev/null
  TEMP_ROOT="$(mktemp -d)"
  git archive "$TARGET" | tar -x -C "$TEMP_ROOT"
  SOURCE_ROOT="$TEMP_ROOT"
  PINNED=1
  echo "目标提交：$(git rev-list -n 1 "$TARGET")"
else
  OLD_HEAD="$(git rev-parse HEAD)"
  echo "== 1/3 拉取最新 =="
  if ! git pull --ff-only; then
    echo "❌ git pull 失败（多半本地有改动或当前分支无上游）。先用 git status 检查；不要覆盖本地改动。"
    exit 1
  fi
fi

if [ -f "$SOURCE_ROOT/_shared/SUITE_VERSION" ]; then
  SUITE_VERSION="$(tr -d '[:space:]' < "$SOURCE_ROOT/_shared/SUITE_VERSION")"
elif [ "$PINNED" = 1 ]; then
  # v0.4.0 才引入 SUITE_VERSION。旧版只有在显式语义化版本 tag 下才可回退，
  # 版本号取自已验证的 tag；默认分支仍拒绝缺少版本文件的不可追踪状态。
  SUITE_VERSION="${TARGET#v}"
  echo "ℹ️ $TARGET 是旧版发布，版本号取自 Git tag。"
else
  echo "❌ 当前默认分支缺少 _shared/SUITE_VERSION，拒绝安装不可追踪版本。"
  exit 1
fi

echo
echo "== 2/3 版本与变更 =="
echo "EdgeLab Skills $SUITE_VERSION"
if [ "$PINNED" = 0 ]; then
  if [ "$OLD_HEAD" != "$(git rev-parse HEAD)" ]; then
    git log --oneline "${OLD_HEAD}..HEAD"
  else
    echo "(已是最新，无新提交)"
  fi
fi
echo
sed -n '1,55p' "$SOURCE_ROOT/CHANGELOG.md" 2>/dev/null || echo "(无 CHANGELOG)"

echo
echo "== 3/3 同步到已安装的 skills 目录 =="
# _shared is a generic name. Check all runtimes before replacing any files.
for DEST in "$HOME/.claude/skills" "$HOME/.codex/skills" \
            "$HOME/.codebuddy/skills" "$HOME/.workbuddy/skills"; do
  RUNTIME_DIR="$(dirname "$DEST")"
  [ -d "$RUNTIME_DIR" ] || [ -e "$DEST/elab" ] || continue
  if [ -e "$DEST/_shared" ] || [ -L "$DEST/_shared" ]; then
    if ! { [ -f "$DEST/_shared/credit.md" ] && grep -q 'EdgeLab 署名规范' "$DEST/_shared/credit.md"; } &&
       ! { [ -f "$DEST/elab/SKILL.md" ] && grep -q 'EdgeLab 投研工具箱' "$DEST/elab/SKILL.md"; }; then
      echo "❌ $DEST/_shared 已存在且无法确认属于 EdgeLab；更新已停止，未修改任何 runtime。"
      exit 1
    fi
  fi
done
SYNCED=0
for DEST in "$HOME/.claude/skills" "$HOME/.codex/skills" \
            "$HOME/.codebuddy/skills" "$HOME/.workbuddy/skills"; do
  RUNTIME_DIR="$(dirname "$DEST")"
  [ -d "$RUNTIME_DIR" ] || [ -e "$DEST/elab" ] || continue
  mkdir -p "$DEST"
  WAS_LINK=0
  [ -L "$DEST/elab" ] && WAS_LINK=1
  LINK_MODE=0
  [ "$PINNED" = 0 ] && [ "$WAS_LINK" = 1 ] && LINK_MODE=1

  # EdgeLab owns the elab / elab-* / _shared namespace in an installation.
  # Clear it before rebuilding so removed/newer skills cannot survive a rollback.
  for installed in "$DEST"/elab "$DEST"/elab-* "$DEST"/_shared; do
    [ -e "$installed" ] || [ -L "$installed" ] || continue
    rm -rf "${installed:?}"
  done

  if [ "$LINK_MODE" = 1 ]; then
    for source in "$SOURCE_ROOT"/elab "$SOURCE_ROOT"/elab-* "$SOURCE_ROOT"/_shared; do
      [ -e "$source" ] || continue
      name="$(basename "$source")"
      ln -sfn "$source" "$DEST/$name"
    done
    echo "✅ ${DEST}：软链安装，已按当前仓库完整重建。"
  else
    if [ "$PINNED" = 1 ] && [ "$WAS_LINK" = 1 ]; then
      echo "ℹ️ ${DEST}：指定版本会把 elab 软链转换为版本固定的复制安装。"
    fi
    for source in "$SOURCE_ROOT"/elab "$SOURCE_ROOT"/elab-* "$SOURCE_ROOT"/_shared; do
      [ -e "$source" ] || continue
      name="$(basename "$source")"
      rm -rf "${DEST:?}/$name"
      cp -R "$source" "$DEST/"
    done
    echo "✅ ${DEST}：已同步 EdgeLab Skills ${SUITE_VERSION}（含 _shared）。"
  fi
  SYNCED=1
done
if [ "$SYNCED" = 0 ]; then
  echo "⚠️ 未发现任何支持的 runtime，跳过同步。手动把 elab* + _shared 拷进 skills 目录。"
fi

echo
if [ "$PINNED" = 1 ]; then
  echo "🎉 已安装/回退到 EdgeLab Skills ${SUITE_VERSION}（${TARGET}）；当前 Git 工作树未改变。"
else
  echo "🎉 更新完成：EdgeLab Skills $SUITE_VERSION。"
fi
