# 官网（autoclip_intro）随发版自动更新

官网是 GitHub Pages 上的单文件 `index.html`，版本号、下载链接、安装包体积硬编码在十来处（四语各一份）。
以前发版后要手改三处；现在链路是：

```
git tag vX.Y.0 ─▶ desktop-build.yml ─▶ Release 出包
                        │
                        └─▶ repository_dispatch(autoclip-release, {tag}) ─▶ autoclip_intro/sync-release.yml
                                                                               │  python scripts/sync_release.py vX.Y.0
                                                                               │  （读 GitHub Release API，改 index.html）
                                                                               └▶ 提交到 main ─▶ Pages 约 1 分钟生效
```

兜底：官网 workflow 每天 03:17 UTC 也会拉一次 latest release，所以即使主仓库没配 token，官网最多落后一天。

## 一次性安装（官网仓库那边）

主仓库的 token 没有官网仓库的写权限，所以文件放在这里，由你复制过去：

```bash
bash scripts/website/install.sh ../autoclip_intro
cd ../autoclip_intro && git add -A && git commit -m "build: sync release info automatically" && git push
```

## 让发版即时触发（可选）

1. GitHub → Settings → Developer settings → Fine-grained tokens → 新建：Repository access 只选 `autoclip_intro`，Permissions → Contents: **Read and write**。
2. 主仓库 `autoclip` → Settings → Secrets and variables → Actions → 新建 `WEBSITE_DISPATCH_TOKEN`。
3. 之后每次 `desktop-build.yml` 的 `release` job 成功都会推一次 `autoclip-release` 事件；没配 token 时该步骤跳过，不影响发版。

## 文件

发布教程页（`guides/publish/`）也放在这个目录，应用内「操作教程」链到官网。改步骤只改官网这一页，不必发客户端。`install.sh` 会一并拷过去，并在首页 FAQ / 页脚加入口。

| 文件 | 去处 | 作用 |
|---|---|---|
| `sync_release.py` | `autoclip_intro/scripts/` | 读 Release → 改 `index.html`（`--check` 只报告） |
| `sync-release.yml` | `autoclip_intro/.github/workflows/` | 三种触发（dispatch / cron / 手动）→ 跑脚本 → 有改动就提交 |
| `guides/publish/index.html` | `autoclip_intro/guides/publish/` | 八语发布操作教程（Upload-Post、B 站三个 Cookie、仅自己试发） |
| `install_publish_guide.py` | 留在这里 | 拷教程页，并补首页 FAQ / 页脚 / sitemap |
| `install.sh` | 留在这里 | 复制同步脚本、教程页并同步一次 Release |

主仓库端：`.github/workflows/desktop-build.yml` → `release` job → "Notify website" 步骤。
