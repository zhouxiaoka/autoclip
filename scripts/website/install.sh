#!/usr/bin/env bash
# 把官网自动同步这套东西装进 autoclip_intro 仓库（一次性）。
#
#   bash scripts/website/install.sh ../autoclip_intro
#
# 复制后在官网仓库的分支上审阅再提交。不要直接推 main。
# 主仓库的通知在 .github/workflows/promote-release.yml。Pre-release 不通知。
# 可选 secret：WEBSITE_DISPATCH_TOKEN（fine-grained PAT，只授权 autoclip_intro，Contents: Read and write）。
# 没配 secret 时，官网每日 cron 读取 GitHub Latest。
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -f "$TARGET/index.html" ]]; then
  echo "用法: bash scripts/website/install.sh <autoclip_intro 仓库路径>（该目录下要有 index.html）" >&2
  exit 1
fi

mkdir -p "$TARGET/scripts" "$TARGET/.github/workflows"
cp "$HERE/sync_release.py" "$TARGET/scripts/sync_release.py"
cp "$HERE/sync-release.yml" "$TARGET/.github/workflows/sync-release.yml"
chmod +x "$TARGET/scripts/sync_release.py" "$HERE/install_publish_guide.py"
grep -q '__pycache__' "$TARGET/.gitignore" 2>/dev/null || echo '__pycache__/' >> "$TARGET/.gitignore"

echo "已复制到 $TARGET："
echo "  scripts/sync_release.py"
echo "  .github/workflows/sync-release.yml"
echo
echo "现在同步一次到最新正式 Release："
(cd "$TARGET" && python3 scripts/sync_release.py)
if [[ "${WITH_PUBLISH_GUIDE:-}" == "1" ]]; then
  echo
  echo "按显式要求重装发布教程页。这会覆盖官网已有的 guides/publish/index.html。"
  python3 "$HERE/install_publish_guide.py" "$TARGET"
else
  echo "未覆盖 guides/publish。该页已在官网单独维护；只有要重装旧模板时才设置 WITH_PUBLISH_GUIDE=1。"
fi
echo
echo "下一步：在 $TARGET 审阅 diff，再提交并推到官网仓库的分支。不要直接推 main。"
