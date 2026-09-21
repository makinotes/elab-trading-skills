#!/usr/bin/env bash
# EdgeLab Skills 更新/回退：默认拉最新；--to vX.Y.Z 从已发布 tag 安装指定版本。
# 支持 Claude Code / Codex / CodeBuddy / WorkBuddy。
# Parse the whole update before fast-forwarding a checkout that may replace this file.
main() {
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

command -v python3 >/dev/null 2>&1 || { echo "更新需要 Python 3.9+。"; exit 1; }
SOURCE_ROOT="$REPO"
ADVANCE=()
MODE=auto
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
  MODE=copy
  echo "目标提交：$(git rev-list -n 1 "$TARGET")"
else
  OLD_HEAD="$(git rev-parse HEAD)"
  if [ -n "$(git status --porcelain)" ]; then
    echo "更新需要干净的 Git 工作树；请先保存或备份本地改动。"
    exit 1
  fi
  UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}')" || {
    echo "当前分支没有上游，无法更新。"; exit 1;
  }
  echo "== 1/3 获取上游版本（暂不改变工作树） =="
  git fetch
  NEW_HEAD="$(git rev-parse "$UPSTREAM^{commit}")"
  git merge-base --is-ancestor "$OLD_HEAD" "$NEW_HEAD" || {
    echo "当前分支无法 fast-forward，保留原工作树与安装。"; exit 1;
  }
  TEMP_ROOT="$(mktemp -d)"
  git archive "$NEW_HEAD" | tar -x -C "$TEMP_ROOT"
  SOURCE_ROOT="$TEMP_ROOT"
  ADVANCE=(--advance-repo "$REPO" --advance-commit "$NEW_HEAD" --expected-head "$OLD_HEAD")

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
  if [ "$OLD_HEAD" != "$NEW_HEAD" ]; then
    git log --oneline "${OLD_HEAD}..${NEW_HEAD}"
  else
    echo "(已是最新，无新提交)"
  fi
fi
echo
sed -n '1,55p' "$SOURCE_ROOT/CHANGELOG.md" 2>/dev/null || echo "(无 CHANGELOG)"

echo
echo "== 3/3 同步到已安装的 skills 目录 =="
# The current helper also installs legacy tags that predate the helper/manifest.
python3 "$REPO/scripts/install_runtime.py" --source "$SOURCE_ROOT" \
  --link-root "$REPO" --version "$SUITE_VERSION" --mode "$MODE" --update \
  ${ADVANCE[@]+"${ADVANCE[@]}"}

echo
if [ "$PINNED" = 1 ]; then
  echo "🎉 已安装/回退到 EdgeLab Skills ${SUITE_VERSION}（${TARGET}）；当前 Git 工作树未改变。"
else
  echo "🎉 更新完成：EdgeLab Skills ${SUITE_VERSION}。"
fi

}

{
  main "$@"
  exit
}
