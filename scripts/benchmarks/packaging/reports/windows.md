临时：原始文件丢失，待 Windows 重跑替换

本文件不是测速脚本生成的报告，仓库里也没有对应的 `windows.json`。下面的表和机器信息照录自上述评论，待 Windows 验收机重跑后用脚本输出整文件替换。

- https://github.com/zhouxiaoka/autoclip/pull/314#issuecomment-6093245237
- https://github.com/zhouxiaoka/autoclip/pull/314#issuecomment-6093609293

## 评论 6093245237

## Windows M0 测速结果（腾讯云验收机）

PR head `9640e4f9` 的脚本在腾讯云 Windows 验收机跑完：2 秒短烟测通过，70 秒完整 editorial 用系统 Edge 退出码 0。仅计叠加层抓帧 + 本次编码，不含底层成片与质检。

| 方案 | 抓帧 | 编码 | 总耗时 | 抓帧数 | 相对基线 |
|---|---:|---:|---:|---:|---:|
| 基线·单条：720p 全帧、单页、两遍 x264 | 110.4s | 144.9s | 255.2s | 2100 | 1.00× |
| 优化1·双平台不复用（对照） | 220.8s | 289.7s | 510.5s | 4200 | 2.00× |
| 优化1·双平台叠加层复用 | 110.4s | 289.7s | 400.1s | 2100 | 1.57× |
| 优化2·只抓变化帧（单条，两遍） | 15.7s | 144.9s | 160.5s | 214 | 0.63× |
| 优化3·1080p 全帧单页（对照） | 173.7s | 144.9s | 318.6s | 2100 | 1.25× |
| 优化3·720p + 2 页并行 | 80.6s | 144.9s | 225.5s | 2100 | 0.88× |
| 优化4·单遍 h264_args | 110.4s | 50.7s | 161.1s | 2100 | 0.63× |
| 组合·单条 | 11.7s | 50.7s | 62.4s | 214 | 0.24× |
| 组合·双平台 | 11.7s | 101.4s | 113.1s | 214 | 0.44× |

组合单条 0.24×、双平台组合 0.44×，与 Linux（0.22× / 0.39×）接近。

**机器**：AMD EPYC 7K62 2 vCPU @2.6GHz、8GB、Windows Server 2025 (10.0.26100)。Python 3.13.13 + ffmpeg N-127252（均为 AutoClip 1.5.6 自带），Playwright 1.63.0，系统 Edge 155 headless。核数是 Linux 参照机的一半，是耗时约 2× 的主因。

**硬件编码**：无可用。仅 Microsoft Basic Display Adapter；ffmpeg 虽带 NVENC/QSV/AMF，但产品 encoder 检测选了 libx264（单遍回退 veryfast crf20，两遍 medium 8.09Mbps）。

未跑 Docker 行（本次未加 `--docker`）。验收机已清理，1.5.6 安装未受影响。

## 评论 6093609293

## Windows 复测（HEAD `6e3ebce7`，腾讯云验收机）

两个修复均通过，未设任何 ffmpeg/pip 环境变量，直接 `--install-runtime`。

| 修复 | 结果 |
|---|---|
| pip 国内镜像回退 | **PASS**。日志：`包装组件 pip 从 pypi 失败（pypi: 退出码 1），改用 mirror` → `安装完成`。未卡住，事前未设 PIP_INDEX_URL / pip.ini / AUTOCLIP_PIP_INDEX。 |
| ffmpeg 路径查找 | **PASS**。未设 AUTOCLIP_FFMPEG_PATH/FFPROBE，解析到 `...\AutoClip Desktop\resources\ffmpeg\ffmpeg.exe`。 |

### 组合·单平台（70s editorial，msedge）

| | 抓帧 | 编码 | 总耗时 | 抓帧数 | 相对基线 |
|---|---:|---:|---:|---:|---:|
| 组合·单条 | 12.2s | 50.3s | 62.4s | 214 | 0.24× |

总耗时与上轮 Windows 一致（62.4s）。编码仍 libx264（无可用硬件编码），系统 Edge 155 headless。EXIT=0，验收机已清理，1.5.6 未受影响。
