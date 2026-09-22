#!/usr/bin/env bash
# 把官网自动同步这套东西装进 autoclip_intro 仓库（一次性）。
#
#   bash scripts/website/install.sh ../autoclip_intro
#
# 之后在 autoclip_intro 里 `git add -A && git commit -m "build: sync release info automatically" && git push`。
# 主仓库这端的 repository_dispatch 见 .github/workflows/desktop-build.yml 的 "Notify website" 步骤，
# 需要在主仓库 Settings → Secrets 里加 WEBSITE_DISPATCH_TOKEN（fine-grained PAT：仓库 autoclip_intro，Contents: Read and write）。
# 不加也行：官网 workflow 里有每日 cron 兜底，只是会晚最多一天。
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
echo "现在同步一次到最新 Release："
(cd "$TARGET" && python3 scripts/sync_release.py)
echo
echo "写入发布教程页，并在首页 FAQ / 页脚留下入口："
python3 "$HERE/install_publish_guide.py" "$TARGET"
echo
echo "下一步：cd $TARGET && git add -A && git commit -m 'docs: add the publish guide page' && git push"
