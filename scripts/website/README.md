# 官网（autoclip_intro）随正式版自动更新

官网仓库是 [zhouxiaoka/autoclip_intro](https://github.com/zhouxiaoka/autoclip_intro)，GitHub Pages 发布在 <https://zhouxiaoka.github.io/autoclip_intro/>。页面不在本仓库。这里保存同步脚本，避免本仓库的旧副本以后覆盖官网。

```
git tag vX.Y.Z ─▶ desktop-build.yml ─▶ Pre-release（官网不动）
                              … 真机冒烟 + 观察期 …
promote-release.yml promote ─▶ 转正为 GitHub Latest
                        │
                        └─▶ repository_dispatch(autoclip-release, {tag})
                                      │
                                      ▼
                         autoclip_intro/sync-release.yml
                           读 Release API，拒绝 draft / prerelease
                           写入 data/release.json 和当前版本槽位
                           提交 main，再请求 Pages 构建
```

halt 时通知使用 fallback 正式版。没配 `WEBSITE_DISPATCH_TOKEN` 时跳过通知，不影响转正；官网每天 03:17 UTC 读取 GitHub Latest。API 失败、预发布或缺少 macOS / Windows 安装包时，官网脚本失败且不提交，页面保持上一份正式版。

手动更正：在官网 Actions 里运行 Sync release info，tag 留空取 Latest，或填写一个已经转正的 tag。

## 安装到官网仓库

```bash
bash scripts/website/install.sh ../autoclip_intro
```

默认只更新同步脚本和 workflow，并按当前正式版重写发布槽位。不会覆盖已经独立维护的 `guides/publish/index.html`。

发布教程页的旧模板仍在 `scripts/website/guides/publish/`。只有确认要用这份旧模板替换官网页面时，才设置 `WITH_PUBLISH_GUIDE=1`。

## 发版即时触发

1. Fine-grained token：Repository access 只选 `autoclip_intro`，Contents 为 Read and write。
2. 本仓库 Actions secret：`WEBSITE_DISPATCH_TOKEN`。
3. token 只出现在 secret 里。官网提交使用它自己的 `GITHUB_TOKEN`。

打 tag 只出 Pre-release，`promote-release.yml` 发现目标仍是 draft / prerelease 时不发送通知。

## 文件

| 文件 | 去处 | 作用 |
|---|---|---|
| `sync_release.py` | `autoclip_intro/scripts/` | 读正式 Release，改当前版本槽位 |
| `sync-release.yml` | `autoclip_intro/.github/workflows/` | dispatch / cron / 手动；失败不提交 |
| `guides/publish/index.html` | 仅在 `WITH_PUBLISH_GUIDE=1` 时覆盖 | 旧的八语发布教程模板 |
| `install_publish_guide.py` | 留在这里 | 重装教程页并补首页入口 |
| `install.sh` | 留在这里 | 复制同步脚本 |

通知步骤在 `.github/workflows/promote-release.yml`，不在 `desktop-build.yml`。
