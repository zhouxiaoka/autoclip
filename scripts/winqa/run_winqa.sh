#!/usr/bin/env bash
# AutoClip Windows 安装包自动验收（命令行部分）。从一台 Linux/macOS 机器通过 SSH 驱动专用 Windows 验收机。
# 用法见同目录 README.md；主机、账号、SSH 身份、模型地址和 key 只从环境变量/参数读，仓库里不放任何默认值：
#   ./run_winqa.sh --prev <上一正式版 setup.exe> --candidate <候选 setup.exe> --version X.Y.Z [选项]
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HOST="${WINQA_HOST:-}"
USER_="${WINQA_USER:-}"
IDENTITY="${WINQA_SSH_IDENTITY:-}"   # 可选：SSH 私钥文件路径；不设则用 ssh-agent / ~/.ssh/config
REPO="${WINQA_REPO:-$(cd "$HERE/../.." && pwd)}"
MODEL_BASE_URL="${WINQA_MODEL_BASE_URL:-}"; MODEL="${WINQA_MODEL:-}"; MODEL_PROVIDER="${WINQA_MODEL_PROVIDER:-dashscope}"
MODEL_API_KEY="${WINQA_MODEL_API_KEY:-${AUTOCLIP_QA_DASHSCOPE_KEY:-}}"
PREV=""; CAND=""; VERSION=""; PREV_VERSION=""
MARKER='resources\backend\services\studio\readiness.py'
UPDATER_URL='https://github.com/zhouxiaoka/autoclip/releases/latest/download/latest.json'
SMOKE=1; WITH_ASR=0; FAILURE=1; OUTDIR=""; FROM=0; TO=99; REAL=0; HF_MIRROR=0; BILI_URL=""; LOCAL_SECONDS=150

usage() { sed -n '2,4p' "$0"; cat <<'U'
  --prev FILE            上一个正式版安装包（先干净安装它，再覆盖升级）
  --candidate FILE       本次候选安装包
  --version X.Y.Z        候选版本号（安装后注册表/后端上报必须等于它）
  --prev-version X.Y.Z   上一版版本号（默认从文件名猜）
  --marker PATH          只在候选版存在的文件（相对安装目录），证明覆盖写入了新文件
  --updater-url URL      应用内更新读取的 latest.json
  --no-smoke             不跑 CI 同款 verify_windows_install.py
  --with-asr             额外跑 verify_sensevoice.py / verify_whisper_recovery.py（会下载运行时和模型，较慢）
  --no-failure           不跑失败事件/回退探针
  --out DIR              证据目录（默认 ${WINQA_EVIDENCE_ROOT:-/tmp/autoclip-winqa}/evidence-<时间戳>；不要放进仓库）
  --from-step N          从第 N 步续跑（0-14，需配合 --out 指向原证据目录；已完成的步骤不重跑）
  --to-step N            跑到第 N 步为止（之后仍会做第 8/9 步的收集与汇总）
  --real                 跑第 10-14 步真实模型场景（会产生模型费用，需授权）：key 只从环境变量 WINQA_MODEL_API_KEY 读、只经 stdin 传给验收机
  --model-base-url URL   第 10 步保存的模型接口地址（或 WINQA_MODEL_BASE_URL）
  --model ID             第 10 步的分析模型（或 WINQA_MODEL）
  --model-provider NAME  第 10 步的提供商（或 WINQA_MODEL_PROVIDER，默认 dashscope）
  --hf-mirror            第 11 步 Whisper 模型从 huggingface.co 下载失败时，临时设用户级 HF_ENDPOINT=hf-mirror.com 并重启应用再试（绕过办法，不算产品通过；第 14 步撤销）
  --bili-url URL         第 13 步用的 B 站公开短视频链接（<5 分钟）；不给则跳过
  --local-seconds N      第 12 步本地视频截取秒数（默认 150）
  必需环境变量：WINQA_HOST（验收机地址）、WINQA_USER（验收机上已登录交互桌面的 Windows 账号）
  可选环境变量：WINQA_SSH_IDENTITY、WINQA_REPO（默认本仓库根目录）、WINQA_EVIDENCE_ROOT
U
}
while [ $# -gt 0 ]; do
  case "$1" in
    --prev) PREV="$2"; shift 2;; --candidate) CAND="$2"; shift 2;; --version) VERSION="$2"; shift 2;;
    --prev-version) PREV_VERSION="$2"; shift 2;; --marker) MARKER="$2"; shift 2;; --updater-url) UPDATER_URL="$2"; shift 2;;
    --no-smoke) SMOKE=0; shift;; --with-asr) WITH_ASR=1; shift;; --no-failure) FAILURE=0; shift;; --out) OUTDIR="$2"; shift 2;; --from-step) FROM="$2"; shift 2;; --to-step) TO="$2"; shift 2;; --real) REAL=1; shift;; --hf-mirror) HF_MIRROR=1; shift;; --bili-url) BILI_URL="$2"; shift 2;; --local-seconds) LOCAL_SECONDS="$2"; shift 2;;
    --model-base-url) MODEL_BASE_URL="$2"; shift 2;; --model) MODEL="$2"; shift 2;; --model-provider) MODEL_PROVIDER="$2"; shift 2;;
    -h|--help) usage; exit 0;; *) echo "unknown arg $1"; usage; exit 2;;
  esac
done
[ -f "$PREV" ] && [ -f "$CAND" ] && [ -n "$VERSION" ] || { usage; exit 2; }
[ -n "$HOST" ] && [ -n "$USER_" ] || { echo "需要环境变量 WINQA_HOST 和 WINQA_USER"; exit 2; }
[ "$FROM" -gt 0 ] && [ -z "$OUTDIR" ] && { echo "--from-step 需要 --out 指向原证据目录"; exit 2; }
[ -n "$PREV_VERSION" ] || PREV_VERSION="$(basename "$PREV" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="${OUTDIR:-${WINQA_EVIDENCE_ROOT:-${TMPDIR:-/tmp}/autoclip-winqa}/evidence-$TS}"
mkdir -p "$OUT"
LOG="$OUT/run.log"
exec > >(tee -a "$LOG") 2>&1

ID_OPT=(); [ -n "$IDENTITY" ] && ID_OPT=(-i "$IDENTITY")
SSH=(ssh ${ID_OPT[@]+"${ID_OPT[@]}"} -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 "$USER_@$HOST")
SCP=(scp -q ${ID_OPT[@]+"${ID_OPT[@]}"} -o BatchMode=yes -o ConnectTimeout=20)
PS='powershell -NoProfile -ExecutionPolicy Bypass -File'
step() { echo; echo "==== [$(date +%H:%M:%S)] $*"; }
remote() { "${SSH[@]}" "$@"; }
rps() { "${SSH[@]}" 'powershell -NoProfile -ExecutionPolicy Bypass -Command -'; }  # PowerShell 脚本从 stdin 传，避免远端默认 shell 展开 $
record() { echo "$1=$2" >> "$OUT/steps.txt"; echo "-> $1: $2"; }  # 追加写，续跑时保留之前步骤的结果
want() { [ "$FROM" -le "$1" ] && [ "$1" -le "$TO" ]; }
pull() { "${SCP[@]}" "$USER_@$HOST:C:/winqa/out/$1" "$OUT/" 2>/dev/null || true; }
pull_all() { "${SCP[@]}" -r "$USER_@$HOST:C:/winqa/out/*" "$OUT/" 2>/dev/null || true; }

step "0. 本地准备  prev=$PREV ($PREV_VERSION)  candidate=$CAND ($VERSION)"
PREV_SHA=$(sha256sum "$PREV" | cut -d' ' -f1); CAND_SHA=$(sha256sum "$CAND" | cut -d' ' -f1)
want 0 && printf '{"prev":{"file":"%s","version":"%s","sha256":"%s"},"candidate":{"file":"%s","version":"%s","sha256":"%s"},"repo_commit":"%s","started_at":"%s"}\n' \
  "$(basename "$PREV")" "$PREV_VERSION" "$PREV_SHA" "$(basename "$CAND")" "$VERSION" "$CAND_SHA" \
  "$(git -C "$REPO" rev-parse HEAD 2>/dev/null)" "$(date -Iseconds)" > "$OUT/inputs.json"
cat "$OUT/inputs.json"
remote 'hostname' >/dev/null || { echo "SSH 不通（检查 WINQA_HOST / WINQA_USER / WINQA_SSH_IDENTITY）"; exit 3; }

if want 1; then
step "1. 上传脚本、安装包和 CI 冒烟用到的仓库文件"
remote 'powershell -NoProfile -Command "New-Item -ItemType Directory -Force C:\winqa\ps,C:\winqa\py,C:\winqa\inst,C:\winqa\out,C:\winqa\repo | Out-Null"'
"${SCP[@]}" "$HERE"/ps/*.ps1 "$USER_@$HOST:C:/winqa/ps/"
"${SCP[@]}" "$HERE"/py/*.py "$USER_@$HOST:C:/winqa/py/"
remote_hash() { remote "powershell -NoProfile -Command \"if (Test-Path C:\\winqa\\inst\\$1) { (Get-FileHash C:\\winqa\\inst\\$1).Hash.ToLower() }\"" | tr -d '\r'; }
upload_installer() { # 已在机器上且哈希一致就不重传；否则分 12 片、3 路并发、sftp reput 可续传，再在验收机上拼接
  local src="$1" dst="$2" sha="$3"
  if [ "$(remote_hash "$dst")" = "$sha" ]; then echo "$dst already on VM (hash ok)"; return 0; fi
  local tmp="/tmp/winqa-chunks/$dst"; rm -rf "$tmp"; mkdir -p "$tmp"
  split -n 12 -d -a 2 "$src" "$tmp/p"
  # 先在验收机上建空分片，reput 就总能从已传字节处续传
  rps <<PS
New-Item -ItemType Directory -Force C:\\winqa\\inst\\parts-$dst | Out-Null
foreach (\$n in '$(ls "$tmp" | paste -sd,)'.Split(',')) { \$f = 'C:\\winqa\\inst\\parts-$dst\\' + \$n; if (-not (Test-Path \$f)) { New-Item -ItemType File \$f | Out-Null } }
PS
  export IDENTITY USER_ HOST dst
  ls "$tmp" | xargs -P 3 -I{} bash -c 'for t in 1 2 3 4 5 6; do echo "reput '"$tmp"'/{} /C:/winqa/inst/parts-$dst/{}" | sftp -q ${IDENTITY:+-i "$IDENTITY"} -o BatchMode=yes -o ServerAliveInterval=15 -b - "$USER_@$HOST" >/dev/null && exit 0; sleep 5; done; exit 1'
  local parts; parts=$(ls "$tmp" | sed "s|^|C:\\winqa\\inst\\parts-$dst\\|" | paste -sd+)
  remote "cmd /c copy /y /b $parts C:\\winqa\\inst\\$dst"
  [ "$(remote_hash "$dst")" = "$sha" ] || { echo "upload of $dst failed hash check"; exit 4; }
  remote "powershell -NoProfile -Command \"Remove-Item -Recurse -Force C:\\winqa\\inst\\parts-$dst\""
  rm -rf "$tmp"
}
upload_installer "$PREV" prev-setup.exe "$PREV_SHA"
upload_installer "$CAND" candidate-setup.exe "$CAND_SHA"
tar --sort=name --mtime=@0 --owner=0 --group=0 -C "$REPO" -cf /tmp/winqa-repo.tar scripts/verify_windows_install.py scripts/installed_video_acceptance.py \
  scripts/windows_python_crt.py scripts/windows_desktop_crt.py scripts/verify_sensevoice.py scripts/verify_whisper_recovery.py \
  backend/assets/example/source.mp4 backend/assets/example/source.srt
TAR_SHA=$(sha256sum /tmp/winqa-repo.tar | cut -d' ' -f1)
[ "$(remote_hash ../repo.tar)" = "$TAR_SHA" ] || "${SCP[@]}" /tmp/winqa-repo.tar "$USER_@$HOST:C:/winqa/repo.tar"
remote 'tar -xf C:\winqa\repo.tar -C C:\winqa\repo'
fi

if want 2; then
step "2. 清理旧安装与用户数据（幂等）"
remote "$PS C:\\winqa\\ps\\clean.ps1" && record clean ok || record clean FAIL
remote "$PS C:\\winqa\\ps\\env.ps1 -PrevInstaller C:\\winqa\\inst\\prev-setup.exe -CandInstaller C:\\winqa\\inst\\candidate-setup.exe"
pull clean.json; pull env.json
fi

if want 3; then
step "3. 干净安装上一正式版 $PREV_VERSION 并在交互桌面启动"
remote "$PS C:\\winqa\\ps\\seed_privacy.ps1"
remote "$PS C:\\winqa\\ps\\install.ps1 -Installer C:\\winqa\\inst\\prev-setup.exe -Label prev -ExpectVersion $PREV_VERSION" && record install_prev ok || record install_prev FAIL
remote "$PS C:\\winqa\\ps\\launch.ps1 -Label prev" && record launch_prev ok || record launch_prev FAIL
remote "$PS C:\\winqa\\ps\\ui_probe.ps1 -Label prev" >/dev/null
remote "$PS C:\\winqa\\ps\\runpy.ps1 C:\\winqa\\py\\winqa_probe.py seed" && record seed_prev ok || record seed_prev FAIL
pull_all
fi

if want 4; then
step "4. 旧版仍在运行 + 模拟残留 python 占住 _asyncio.pyd，静默覆盖安装候选 $VERSION"
remote "$PS C:\\winqa\\ps\\install.ps1 -Installer C:\\winqa\\inst\\candidate-setup.exe -Label upgrade -ExpectVersion $VERSION -Marker '$MARKER' -LockLeftover -Interactive" && record upgrade ok || record upgrade FAIL
pull install-upgrade.json
fi

if want 5; then
step "5. 启动候选版并检查版本/健康/Celery/设置/预检/更新清单/项目列表"
remote "$PS C:\\winqa\\ps\\launch.ps1 -Label candidate" && record launch_candidate ok || record launch_candidate FAIL
remote "$PS C:\\winqa\\ps\\ui_probe.ps1 -Label candidate" >/dev/null
remote "$PS C:\\winqa\\ps\\runpy.ps1 C:\\winqa\\py\\winqa_probe.py check --label candidate --expect-version $VERSION --updater-url $UPDATER_URL" && record check_candidate ok || record check_candidate FAIL
fi
if [ "$FAILURE" = 1 ] && want 6; then
  step "6. 失败事件字段与预检回退（本机 loopback fixture / 关闭端口，零费用）"
  remote "$PS C:\\winqa\\ps\\runpy.ps1 C:\\winqa\\py\\winqa_probe.py failure" && record failure_probe ok || record failure_probe FAIL
fi
if want 6; then
remote "$PS C:\\winqa\\ps\\ui_probe.ps1 -Label after-probes" >/dev/null
remote "$PS C:\\winqa\\ps\\stop.ps1 -Label candidate" && record stop_candidate ok || record stop_candidate FAIL
fi
want 6 && pull_all

if [ "$SMOKE" = 1 ] && want 7; then
  step "7. CI 同款安装后冒烟：自带 Python 跑 verify_windows_install.py --launch-desktop"
  A=""; [ "$WITH_ASR" = 1 ] && A="-WithAsr"
  remote "$PS C:\\winqa\\ps\\smoke.ps1 -LaunchDesktop $A" && record smoke ok || record smoke FAIL
  remote "$PS C:\\winqa\\ps\\stop.ps1 -Label smoke" >/dev/null
fi

if [ "$REAL" = 1 ]; then
RP="$PS C:\\winqa\\ps\\runpy.ps1 C:\\winqa\\py\\winqa_real.py"
if want 10; then
  step "10. 真实模型：保存模型连接 + 连接测试 + #266 空 key 重存 + 预检（key 只经 stdin）"
  [ -n "$MODEL_API_KEY" ] || { echo "缺少 WINQA_MODEL_API_KEY"; exit 2; }
  [ -n "$MODEL_BASE_URL" ] && [ -n "$MODEL" ] || { echo "第 10 步需要 --model-base-url 和 --model（或 WINQA_MODEL_BASE_URL / WINQA_MODEL）"; exit 2; }
  "${SCP[@]}" "$HERE/py/winqa_real.py" "$USER_@$HOST:C:/winqa/py/winqa_real.py"
  remote "$PS C:\\winqa\\ps\\launch.ps1 -Label real" && record launch_real ok || record launch_real FAIL
  printf '%s\n' "$MODEL_API_KEY" | remote "$RP model --key-stdin --base-url '$MODEL_BASE_URL' --model '$MODEL' --provider '$MODEL_PROVIDER'" && record real_model ok || record real_model FAIL
fi
if want 11; then
  step "11. Whisper：安装前导入是否被预检拦住 → 走应用自己的安装路由 → 下载模型"
  "${SCP[@]}" "$HERE/py/winqa_real.py" "$USER_@$HOST:C:/winqa/py/winqa_real.py"; "${SCP[@]}" "$HERE/ps/hf_mirror.ps1" "$HERE/ps/clean.ps1" "$USER_@$HOST:C:/winqa/ps/"
  if remote "$RP whisper"; then record real_whisper ok; else
    record real_whisper FAIL
    if [ "$HF_MIRROR" = 1 ]; then
      step "11b. 绕过：HF_ENDPOINT=https://hf-mirror.com（用户级）→ 重启应用 → 再下载 Whisper 模型"
      remote "$PS C:\\winqa\\ps\\hf_mirror.ps1 -On"
      remote "$PS C:\\winqa\\ps\\stop.ps1 -Label real-before-hf" >/dev/null
      remote "$PS C:\\winqa\\ps\\launch.ps1 -Label real-hf" && record launch_real_hf ok || record launch_real_hf FAIL
      remote "$RP whisper --label whisper-hfmirror" && record real_whisper_hfmirror ok || record real_whisper_hfmirror FAIL
    fi
  fi
fi
if want 12; then
  step "12. 本地视频（无字幕，${LOCAL_SECONDS}s）→ Whisper 转写 → 真实模型出片 → 导出 + ffprobe"
  "${SCP[@]}" "$HERE/py/winqa_real.py" "$USER_@$HOST:C:/winqa/py/winqa_real.py"
  remote "$RP local --seconds $LOCAL_SECONDS" && record real_local ok || record real_local FAIL
fi
if want 13 && [ -n "$BILI_URL" ]; then
  step "13. B 站链接导入 → 进度 → 出片  $BILI_URL"
  remote "$RP link --url '$BILI_URL'" && record real_link ok || record real_link FAIL
fi
if want 14; then
  step "14. 首页/项目列表无卡住的 processing；截图；停止应用"
  remote "$RP final" && record real_final ok || record real_final FAIL
  remote "$PS C:\\winqa\\ps\\ui_probe.ps1 -Label real" >/dev/null
  remote "$PS C:\\winqa\\ps\\stop.ps1 -Label real" >/dev/null
  remote "$PS C:\\winqa\\ps\\hf_mirror.ps1 -Off" >/dev/null
fi
fi

step "8. 收集日志（脱敏）"
remote "powershell -NoProfile -Command \"Remove-Item -Recurse -Force C:\\winqa\\out\\media,C:\\winqa\\out\\real\\media -ErrorAction SilentlyContinue\""
rps <<'PS'
$d = Join-Path $env:APPDATA 'AutoClip\logs'
if (Test-Path $d) { $t = Join-Path $env:TEMP 'winqa-logs'; Remove-Item -Recurse -Force $t -ErrorAction SilentlyContinue; New-Item -ItemType Directory $t | Out-Null
  Get-ChildItem $d -File | ForEach-Object { try { $i = [IO.File]::Open($_.FullName, 'Open', 'Read', 'ReadWrite,Delete'); $o = [IO.File]::Create((Join-Path $t $_.Name)); $i.CopyTo($o); $o.Close(); $i.Close() } catch { } }
  Compress-Archive -Force -Path "$t\*" -DestinationPath C:\winqa\out\app-logs.zip }  # 应用运行中日志被占用：先以共享读方式复制再打包
PS
pull_all
mkdir -p "$OUT/app-logs" && (cd "$OUT/app-logs" && unzip -oq ../app-logs.zip 2>/dev/null; rm -f ../app-logs.zip)
# 脱敏：密钥、Bearer、用户目录
find "$OUT" -type f \( -name '*.log' -o -name '*.json' -o -name '*.err' -o -name '*.txt' \) -print0 | xargs -0 -r sed -i -E \
  -e 's/(^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{6,}/\1sk-***/g' -e 's/(Bearer )[A-Za-z0-9._-]+/\1***/g'
rm -rf "$OUT/media" "$OUT/real/media"
WINQA_MODEL_API_KEY="$MODEL_API_KEY" python3 "$HERE/redact.py" "$OUT"  # 按环境变量里的真实 key 精确替换，并抹掉应用的打码形式

step "9. 汇总"
sort -t= -k1,1 -u "$OUT/steps.txt" -o "$OUT/steps.txt" 2>/dev/null || true
python3 "$HERE/summarize.py" "$OUT" | tee "$OUT/summary.md"
grep -q FAIL "$OUT/steps.txt" && exit 1 || exit 0
