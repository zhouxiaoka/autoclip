#!/usr/bin/env bash
# AutoClip Windows 安装包自动验收（命令行部分）。从一台 Linux/macOS 机器通过 SSH 驱动专用 Windows 验收机。
# 用法见同目录 README.md；主机、账号、SSH 身份、模型地址和 key 只从环境变量/参数读，仓库里不放任何默认值：
#   ./run_winqa.sh --prev <上一正式版 setup.exe> --candidate <候选 setup.exe> --version X.Y.Z [选项]
set -uo pipefail
# R29 #320: first pure bash only - read the key, unset it from the environment, THEN start any child process
MODEL_API_KEY="${WINQA_MODEL_API_KEY:-${AUTOCLIP_QA_DASHSCOPE_KEY:-}}"
unset WINQA_MODEL_API_KEY AUTOCLIP_QA_DASHSCOPE_KEY
export -n MODEL_API_KEY 2>/dev/null || true
HERE="$(cd "$(dirname "$0")" && pwd)"
HOST="${WINQA_HOST:-}"
USER_="${WINQA_USER:-}"
IDENTITY="${WINQA_SSH_IDENTITY:-}"   # 可选：SSH 私钥文件路径；不设则用 ssh-agent / ~/.ssh/config
REPO="${WINQA_REPO:-$(cd "$HERE/../.." && pwd)}"
MODEL_BASE_URL="${WINQA_MODEL_BASE_URL:-}"; MODEL="${WINQA_MODEL:-}"; MODEL_PROVIDER="${WINQA_MODEL_PROVIDER:-dashscope}"
# R27 #308: the key stays in this shell only. It is never exported to ssh/scp/sftp or any other child; the log
# channel gets it on a private pipe (--keys-fd) and the remote Python on stdin after the request line.
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
umask 077
mkdir -p "$OUT"; chmod 700 "$OUT"   # R27 #259: the evidence dir is private too (asserted by the tests)
LOG="$OUT/run.log"
RUN_ID="r$TS-$$"; EXPORT_SEQ=0
PLAN_PY="$HERE/py/winqa_plan.py"
FLAGS=""; [ "$SMOKE" = 1 ] && FLAGS="$FLAGS,smoke"; [ "$WITH_ASR" = 1 ] && FLAGS="$FLAGS,asr"; [ "$FAILURE" = 1 ] && FLAGS="$FLAGS,failure"
[ "$REAL" = 1 ] && FLAGS="$FLAGS,real"; [ -n "$BILI_URL" ] && FLAGS="$FLAGS,bili"; [ "$HF_MIRROR" = 1 ] && FLAGS="$FLAGS,hf"
# R29 #317 log channel. FD topology: 3/4 = the original stdout/stderr; logpipe.py (scrubber + run.log + terminal,
# one process) reads a pipe that becomes this script's stdout AND stderr only after its READY handshake, so no
# business output exists before scrubbing is live. Children never get a spare write end (the pipe is only 1/2).
LP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/winqa-lp.XXXXXX")" || { echo "WINQA_E_LOGPIPE 70" >&2; exit 70; }
LP_STATUS="$LP_DIR/status"; : > "$LP_STATUS" || { echo "WINQA_E_LOGPIPE 70" >&2; exit 70; }
exec 3>&1 4>&2
# #414 v5 M3/#395: the process substitution is a bash subshell that WAITS for logpipe and appends "RC <real exit
# status>" (137 after SIGKILL). The exit code comes only from that line, never from logpipe's own "EXIT" claim.
exec 5> >(python3 -u "$HERE/logpipe.py" --log "$LOG" --status "$LP_STATUS" --keys-fd 6 6< <(printf '%s\n' "$MODEL_API_KEY") 1>&3 2>&4; echo "RC $?" >> "$LP_STATUS")
LP_SPAWN="${!:-}"   # pid of the process substitution where bash reports it; READY carries logpipe's own pid
# handshake bound (hardening, #389 not reproduced): WINQA_LOGPIPE_HANDSHAKE_S, default 30 s, 1..600
HS="${WINQA_LOGPIPE_HANDSHAKE_S:-30}"
case "$HS" in ''|*[!0-9]*) echo "WINQA_E_LOGPIPE 70 bad WINQA_LOGPIPE_HANDSHAKE_S" >&4; exit 70;; esac
{ [ "$HS" -ge 1 ] && [ "$HS" -le 600 ]; } || { echo "WINQA_E_LOGPIPE 70 bad WINQA_LOGPIPE_HANDSHAKE_S" >&4; exit 70; }
LP_PID=""; i=0
while [ $i -lt $((HS * 10)) ]; do
  LP_PID="$(sed -n 's/^READY \([0-9][0-9]*\)$/\1/p' "$LP_STATUS" 2>/dev/null)"
  [ -n "$LP_PID" ] && break
  grep -q '^RC ' "$LP_STATUS" 2>/dev/null && break
  sleep 0.1; i=$((i + 1))
done
if [ -z "$LP_PID" ]; then
  # the reason is decided BEFORE stopping it (stopping it writes an RC line of its own)
  if grep -q '^RC ' "$LP_STATUS" 2>/dev/null; then why="died before READY ($(sed -n 's/^RC //p' "$LP_STATUS"))"; else why="handshake_timeout after ${HS}s"; fi
  exec 5>&-
  # no handshake: stop logpipe (a child of the waiting subshell) and the subshell; never wait on them
  case "$LP_SPAWN" in ''|*[!0-9]*) ;; *) pkill -TERM -P "$LP_SPAWN" 2>/dev/null; kill -TERM "$LP_SPAWN" 2>/dev/null;; esac
  echo "WINQA_E_LOGPIPE 70 $why" >&4; rm -rf "$LP_DIR"; exit 70
fi
exec 1>&5 2>&5 5>&-
logpipe_alive() { kill -0 "$LP_PID" 2>/dev/null && ! grep -q '^RC ' "$LP_STATUS" 2>/dev/null; }
# close order: give the terminal back, close the only write end, bounded wait (10 s) for the "RC" line written by the
# waiting subshell. Not there -> TERM, KILL, wait 1 s more. The external exit code then follows that real status, and
# a verdict already written is downgraded through winqa_chain so the two always agree (I-C1).
LP_REASON=""
logpipe_close() {
  local rc="$1" n=0 lp
  exec 1>&3 2>&4
  while ! grep -q '^RC ' "$LP_STATUS" 2>/dev/null && [ $n -lt 100 ]; do sleep 0.1; n=$((n + 1)); done
  if ! grep -q '^RC ' "$LP_STATUS" 2>/dev/null; then
    LP_REASON=drain_timeout; kill -TERM "$LP_PID" 2>/dev/null; sleep 0.2; kill -KILL "$LP_PID" 2>/dev/null
    n=0; while ! grep -q '^RC ' "$LP_STATUS" 2>/dev/null && [ $n -lt 10 ]; do sleep 0.1; n=$((n + 1)); done
  fi
  lp="$(sed -n 's/^RC \([0-9][0-9]*\)$/\1/p' "$LP_STATUS" 2>/dev/null | tail -1)"
  if [ -z "$LP_REASON" ] && [ "${lp:-x}" != 0 ]; then
    case "$lp" in '') LP_REASON=died;; 1[2-9][0-9]) LP_REASON=died;; *) LP_REASON="exit=$lp";; esac
  fi
  if [ -n "$LP_REASON" ]; then
    # #414 test_a2: a channel that died mid-run (the script then stops on SIGPIPE, rc 141) is announced once
    echo "WINQA_E_LOGPIPE 70 $LP_REASON" >&4
    [ "$rc" = 0 ] && rc=70
    if [ -n "${VERDICT:-}" ] && [ -f "$VERDICT" ]; then
      python3 "$CHAIN_PY" downgrade --dest "$VERDICT" --reason "logpipe_${LP_REASON%%=*}" >/dev/null 2>&1 \
        || rm -f "$VERDICT"
    fi
  fi
  rm -rf "$LP_DIR"
  return "$rc"
}
python3 "$PLAN_PY" migrate --out "$OUT" || { echo "FAIL: 旧证据迁移失败"; exit 71; }
PREV_SHA=$(sha256sum "$PREV" | cut -d' ' -f1); CAND_SHA=$(sha256sum "$CAND" | cut -d' ' -f1)
# v5 #385: the plan names the candidate installer; a resume for another candidate is refused (exit 71)
PLAN_SHA="$(python3 "$PLAN_PY" create --out "$OUT" --run-id "$RUN_ID" --from "$FROM" --to "$TO" --flags "${FLAGS#,}" \
  --inputs "{\"candidate_sha256\":\"$CAND_SHA\",\"prev_sha256\":\"$PREV_SHA\"}")"; PLAN_RC=$?
[ "$PLAN_RC" = 0 ] || { echo "FAIL: 写不了执行计划（plan.json，rc=${PLAN_RC}；续跑必须是同一个候选安装包）"; exit 71; }
PLAN="$OUT/runs/$RUN_ID/plan.json"
# A run killed with -9 cannot clean up. R25 #248: staging dirs live under one fixed private root (not $TMPDIR, which
# can change between runs); a leftover is deleted when its run is gone, its pid now belongs to another program, or
# it is older than 24 h. Legacy winqa-stage.* dirs under $TMPDIR and /tmp get the same check.
STAGE_ROOT="${WINQA_STAGE_ROOT:-${XDG_CACHE_HOME:-$HOME/.cache}/autoclip-winqa-stage}"
mkdir -p "$STAGE_ROOT"; chmod 700 "$STAGE_ROOT"
stage_is_live() {   # $1 = dir named winqa-stage.<pid>.<rand>
  local p="${1##*/winqa-stage.}"; p="${p%%.*}"
  case "$p" in ''|*[!0-9]*) return 1;; esac
  [ -n "$(find "$1" -maxdepth 0 -mmin +1440 2>/dev/null)" ] && return 1
  kill -0 "$p" 2>/dev/null || return 1
  ps -o args= -p "$p" 2>/dev/null | grep -q run_winqa
}
for d in "$STAGE_ROOT"/winqa-stage.* "${TMPDIR:-/tmp}"/winqa-stage.* /tmp/winqa-stage.*; do
  [ -d "$d" ] || continue
  stage_is_live "$d" || rm -rf "$d"
done
STAGE="$(mktemp -d "$STAGE_ROOT/winqa-stage.$$.XXXXXX")"; chmod 700 "$STAGE"
cleanup() { local rc=$?; trap - EXIT; rm -rf "$STAGE"; logpipe_close "$rc"; exit $?; }
trap cleanup EXIT
trap 'exit 130' INT; trap 'exit 143' TERM; trap 'exit 129' HUP; trap 'exit 141' PIPE   # #311: the log channel died -> stop, clean up

ID_OPT=(); [ -n "$IDENTITY" ] && ID_OPT=(-i "$IDENTITY")
SSH=(ssh ${ID_OPT[@]+"${ID_OPT[@]}"} -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 "$USER_@$HOST")
SCP=(scp -q ${ID_OPT[@]+"${ID_OPT[@]}"} -o BatchMode=yes -o ConnectTimeout=20)
# R29 #323: every remote call with a variable part goes through ONE fixed command line; the values travel as a JSON
# line on stdin (py/winqa_req.py builds it from separate argv entries), the key as the next line when needed.
ENTRY='powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File C:\winqa\ps\entry.ps1'
CHAIN_PY="$HERE/py/winqa_chain.py"
# v5 B2: before every step the one verification point re-checks plan, resume chain and receipt chain (exit 73)
step() { logpipe_alive || exit 70; python3 "$CHAIN_PY" check --out "$OUT" --run-id "$RUN_ID" --mode stage || { echo "FAIL: 证据链校验失败"; exit 73; }; echo; echo "==== [$(date +%H:%M:%S)] $*"; }
remote() { "${SSH[@]}" "$@"; }                 # fixed strings only (hostname, fixed mkdir)
rcall() {                                      # rcall OP ARGS...   (see py/winqa_req.py)
  local req; req="$(python3 "$HERE/py/winqa_req.py" "$@")" || return 64
  printf '%s\n' "$req" | "${SSH[@]}" "$ENTRY"
}
rcall_key() {                                  # rcall_key SCRIPT ARGS...: a py op that reads the key from stdin
  local s="$1" req; shift; req="$(python3 "$HERE/py/winqa_req.py" py "$s" --key "$@")" || return 64
  { printf '%s\n' "$req"; printf '%s\n' "$MODEL_API_KEY"; } | "${SSH[@]}" "$ENTRY"
}
# R29 point 1/2: one receipt per result, written by winqa_plan.py (never printf'd JSON). exit_code is the
# producer's real return code: `cmd; rec step $?`. A receipt that cannot be written stops the run (exit 72).
rec() {   # rec STEP RC  (RC 0 -> ok, else FAIL with that code)
  local st=ok; [ "$2" = 0 ] || st=FAIL
  python3 "$PLAN_PY" record --out "$OUT" --run-id "$RUN_ID" --step "$1" --status "$st" --exit-code "$2" \
    || { echo "FAIL: 回执写入失败（$1）"; exit 72; }
  echo "-> $1: $st (rc=${2})"
}
record() { local rc=$?; local c="${3:-$rc}"; [ "$2" = ok ] && c=0; [ "$2" != ok ] && [ "$c" = 0 ] && c=1; rec "$1" "$c"; }
want() { [ "$FROM" -le "$1" ] && [ "$1" -le "$TO" ]; }
# R27 export boundary. C:\winqa\out is never modified. export_evidence.py (bundled Python on the VM) reads the exact
# key from stdin, builds C:\winqa\export\<run>-<n>.zip and commits it only after scrubbing and verifying; it prints
# "EXPORT <complete|incomplete> <file> <sha256>". Here: download exactly that file (scp failure = FAIL #253), check
# the hash, re-check every member with the same policy, and only then copy into $OUT. Any failure leaves $OUT as it
# was and records FAIL.
fail_export() { rm -rf "$STAGE/b"; echo "FAIL: $2"; record "$1" FAIL "${3:-1}"; return 1; }
export_bundle() {   # $1 = label for the step record, $2 = step number the export is due for (99 = final)
  local res line status file digest rc req
  EXPORT_SEQ=$((EXPORT_SEQ + 1))
  # #306: the receipts so far go into the bundle as steps.json (from C:\winqa\ctl, never into C:\winqa\out)
  python3 "$PLAN_PY" steps --out "$OUT" --dest "$STAGE/steps.json" || { fail_export "$1" "写不了 steps.json"; return 1; }
  req="$(python3 "$PLAN_PY" due --out "$OUT" --run-id "$RUN_ID" --upto "$2")" || { fail_export "$1" "读不了执行计划"; return 1; }
  [ "$2" -ge 99 ] && req="$(python3 -c 'import json,sys; print(",".join(json.load(open(sys.argv[1]))["required"]))' "$PLAN")"
  remote 'powershell -NoProfile -Command "New-Item -ItemType Directory -Force C:\winqa\ctl | Out-Null"' >/dev/null \
    && "${SCP[@]}" "$STAGE/steps.json" "$USER_@$HOST:C:/winqa/ctl/" || { fail_export "$1" "steps.json 上传失败（scp）"; return 1; }
  res=$(rcall_key export_evidence export --src 'C:\winqa\out' --dest 'C:\winqa\export' --bundle "$RUN_ID-$EXPORT_SEQ" \
        --require "$req" --plan-sha256 "$PLAN_SHA" --steps 'C:\winqa\ctl\steps.json' --keys-stdin); rc=$?
  line=$(printf '%s\n' "$res" | tr -d '\r' | grep '^EXPORT ' | tail -1)
  read -r _ status file digest <<<"$line"
  # #305: ${rc} - Bash 3.2 in a UTF-8 locale reads "$rc）" as one (unset) variable name and set -u exits
  case "$rc:$status" in 0:complete|3:incomplete) ;; *) fail_export "$1" "验收机上导出失败（rc=${rc}），没有可传的证据包" "$rc"; return 1;; esac
  case "$file" in "$RUN_ID-$EXPORT_SEQ.zip") ;; *) fail_export "$1" "导出结果不认识"; return 1;; esac
  # #309: every local mkdir/mv/cp is checked; a failure records FAIL instead of a silent "ok"
  rm -rf "$STAGE/b" && mkdir -p "$STAGE/b" || { fail_export "$1" "建不了临时目录"; return 1; }
  "${SCP[@]}" "$USER_@$HOST:C:/winqa/export/$file" "$STAGE/b/$file" || { fail_export "$1" "证据包下载失败（scp）"; return 1; }
  printf '%s\n' "$MODEL_API_KEY" | python3 "$HERE/py/export_evidence.py" verify --bundle "$STAGE/b/$file" --sha256 "$digest" \
    --into "$STAGE/b/x" --plan "$PLAN" --upto "$2" --keys-stdin; rc=$?
  if [ "$rc" != 0 ] && [ "$rc" != 3 ]; then fail_export "$1" "证据包本地校验失败（rc=${rc}），未写入证据目录" "$rc"; return 1; fi
  mkdir -p "$OUT/bundles" || { fail_export "$1" "建不了 bundles 目录"; return 1; }
  # v5 #384/#386/M8/M9: the receipt binds the bundle. record keeps the ZIP in bundles/, moves the verified members
  # to runs/<id>/a<n>/<step>/ and hashes them; the evidence view in $OUT is a copy that render re-checks.
  local st=ok code=0 adir; [ "$status" = complete ] || { st=FAIL; code=3; }
  adir="$(python3 "$PLAN_PY" record --out "$OUT" --run-id "$RUN_ID" --step "$1" --status "$st" --exit-code "$code" \
          --bundle-zip "$STAGE/b/$file" --bundle-dir "$STAGE/b/x" --print-attempt-dir)" || { echo "FAIL: 回执写入失败（$1）"; exit 72; }
  echo "-> $1: $st (rc=${code})"
  rm -rf "$STAGE/b"
  cp "$adir/manifest.json" "$OUT/bundles/$RUN_ID-$EXPORT_SEQ.manifest.json" || { fail_export "$1" "manifest 落盘失败"; return 1; }
  cp -R "$adir/." "$OUT/" && rm -f "$OUT/manifest.json" || { fail_export "$1" "证据落盘失败（cp），证据目录可能不完整"; return 1; }
  if [ "$st" != ok ]; then echo "FAIL: 必需证据缺失、为空或被扣留，见 bundles/$RUN_ID-$EXPORT_SEQ.manifest.json"; return 1; fi
}

step "0. 本地准备  prev=$PREV ($PREV_VERSION)  candidate=$CAND ($VERSION)"
want 0 && printf '{"prev":{"file":"%s","version":"%s","sha256":"%s"},"candidate":{"file":"%s","version":"%s","sha256":"%s"},"repo_commit":"%s","started_at":"%s"}\n' \
  "$(basename "$PREV")" "$PREV_VERSION" "$PREV_SHA" "$(basename "$CAND")" "$VERSION" "$CAND_SHA" \
  "$(git -C "$REPO" rev-parse HEAD 2>/dev/null)" "$(date -Iseconds)" > "$OUT/inputs.json"
cat "$OUT/inputs.json"
remote 'hostname' >/dev/null || { echo "SSH 不通（检查 WINQA_HOST / WINQA_USER / WINQA_SSH_IDENTITY）"; exit 3; }

if want 1; then
step "1. 上传脚本、安装包和 CI 冒烟用到的仓库文件"
remote 'powershell -NoProfile -Command "New-Item -ItemType Directory -Force C:\winqa\ps,C:\winqa\py,C:\winqa\inst,C:\winqa\out,C:\winqa\repo | Out-Null"'
# R27 #253: an upload that fails stops the run (the exporter and redact.py must be the repo's versions)
"${SCP[@]}" "$HERE"/ps/*.ps1 "$USER_@$HOST:C:/winqa/ps/" &&
"${SCP[@]}" "$HERE"/py/*.py "$USER_@$HOST:C:/winqa/py/" &&
"${SCP[@]}" "$HERE/redact.py" "$USER_@$HOST:C:/winqa/py/" || { echo "上传脚本失败（scp）"; exit 4; }   # export_evidence.py + winqa_probe.py import it
remote_hash() { rcall hash "$1" | tr -d '\r'; }
# 分片：C:\winqa\inst\parts-<dst>\p00...，拼接在验收机上按名字顺序做（entry.ps1 merge_parts，不经 cmd copy /b）
upload_installer() { # 已在机器上且哈希一致就不重传；否则分 12 片、3 路并发、sftp reput 可续传，再在验收机上拼接
  local src="$1" dst="$2" sha="$3"
  if [ "$(remote_hash "$dst")" = "$sha" ]; then echo "$dst already on VM (hash ok)"; return 0; fi
  local tmp="/tmp/winqa-chunks/$dst"; rm -rf "$tmp"; mkdir -p "$tmp"
  split -n 12 -d -a 2 "$src" "$tmp/p"
  local names; names=$(ls "$tmp")
  # 先在验收机上建空分片，reput 就总能从已传字节处续传
  # shellcheck disable=SC2086  # names are p00..p11
  rcall make_parts "$dst" $names || { echo "建分片失败"; exit 4; }
  export IDENTITY USER_ HOST dst
  ls "$tmp" | xargs -P 3 -I{} bash -c 'for t in 1 2 3 4 5 6; do echo "reput '"$tmp"'/{} /C:/winqa/inst/parts-$dst/{}" | sftp -q ${IDENTITY:+-i "$IDENTITY"} -o BatchMode=yes -o ServerAliveInterval=15 -b - "$USER_@$HOST" >/dev/null && exit 0; sleep 5; done; exit 1'
  # shellcheck disable=SC2086
  rcall merge_parts "$dst" $names || { echo "拼接 $dst 失败"; exit 4; }
  [ "$(remote_hash "$dst")" = "$sha" ] || { echo "upload of $dst failed hash check"; exit 4; }
  rcall remove_parts "$dst"
  rm -rf "$tmp"
}
upload_installer "$PREV" prev-setup.exe "$PREV_SHA"
upload_installer "$CAND" candidate-setup.exe "$CAND_SHA"
tar --sort=name --mtime=@0 --owner=0 --group=0 -C "$REPO" -cf /tmp/winqa-repo.tar scripts/verify_windows_install.py scripts/installed_video_acceptance.py \
  scripts/windows_python_crt.py scripts/windows_desktop_crt.py scripts/verify_sensevoice.py scripts/verify_whisper_recovery.py \
  backend/assets/example/source.mp4 backend/assets/example/source.srt
"${SCP[@]}" /tmp/winqa-repo.tar "$USER_@$HOST:C:/winqa/repo.tar" || { echo "上传 repo.tar 失败"; exit 4; }
remote 'tar -xf C:\winqa\repo.tar -C C:\winqa\repo'
fi

if want 2; then
step "2. 清理旧安装与用户数据（幂等）"
rcall ps clean; rec clean $?
rcall ps env PrevInstaller='C:\winqa\inst\prev-setup.exe' CandInstaller='C:\winqa\inst\candidate-setup.exe'; rec env $?   # v5 #388
fi

if want 3; then
step "3. 干净安装上一正式版 $PREV_VERSION 并在交互桌面启动"
rcall ps seed_privacy
rcall ps install Installer='C:\winqa\inst\prev-setup.exe' Label=prev ExpectVersion="$PREV_VERSION"; rec install_prev $?
rcall ps launch Label=prev; rec launch_prev $?
rcall ps ui_probe Label=prev >/dev/null
rcall py winqa_probe seed; rec seed_prev $?
export_bundle export_after_3 3
fi

if want 4; then
step "4. 旧版仍在运行 + 模拟残留 python 占住 _asyncio.pyd，静默覆盖安装候选 $VERSION"
rcall ps install Installer='C:\winqa\inst\candidate-setup.exe' Label=upgrade ExpectVersion="$VERSION" Marker="$MARKER" LockLeftover Interactive; rec upgrade $?
fi

if want 5; then
step "5. 启动候选版并检查版本/健康/Celery/设置/预检/更新清单/项目列表"
rcall ps launch Label=candidate; rec launch_candidate $?
rcall ps ui_probe Label=candidate >/dev/null
rcall py winqa_probe check --label candidate --expect-version "$VERSION" --updater-url "$UPDATER_URL"; rec check_candidate $?
fi
if [ "$FAILURE" = 1 ] && want 6; then
  step "6. 失败事件字段与预检回退（本机 loopback fixture / 关闭端口，零费用）"
  rcall py winqa_probe failure; rec failure_probe $?
fi
if want 6; then
rcall ps ui_probe Label=after-probes >/dev/null
rcall ps stop Label=candidate; rec stop_candidate $?
export_bundle export_after_6 6
fi

if [ "$SMOKE" = 1 ] && want 7; then
  step "7. CI 同款安装后冒烟：自带 Python 跑 verify_windows_install.py --launch-desktop"
  if [ "$WITH_ASR" = 1 ]; then rcall ps smoke LaunchDesktop WithAsr; else rcall ps smoke LaunchDesktop; fi; rec smoke $?
  rcall ps stop Label=smoke >/dev/null
fi

if [ "$REAL" = 1 ]; then
if want 10; then
  step "10. 真实模型：保存模型连接 + 连接测试 + #266 空 key 重存 + 预检（key 只经 stdin）"
  [ -n "$MODEL_API_KEY" ] || { echo "缺少 WINQA_MODEL_API_KEY"; exit 2; }
  [ -n "$MODEL_BASE_URL" ] && [ -n "$MODEL" ] || { echo "第 10 步需要 --model-base-url 和 --model（或 WINQA_MODEL_BASE_URL / WINQA_MODEL）"; exit 2; }
  "${SCP[@]}" "$HERE/py/winqa_real.py" "$USER_@$HOST:C:/winqa/py/winqa_real.py"
  rcall ps launch Label=real; rec launch_real $?
  rcall_key winqa_real model --key-stdin --base-url "$MODEL_BASE_URL" --model "$MODEL" --provider "$MODEL_PROVIDER"; rec real_model $?
fi
if want 11; then
  step "11. Whisper：安装前导入是否被预检拦住 → 走应用自己的安装路由 → 下载模型"
  "${SCP[@]}" "$HERE/py/winqa_real.py" "$USER_@$HOST:C:/winqa/py/winqa_real.py"; "${SCP[@]}" "$HERE/ps/hf_mirror.ps1" "$HERE/ps/clean.ps1" "$USER_@$HOST:C:/winqa/ps/"
  rcall py winqa_real whisper; rc=$?; rec real_whisper "$rc"
  if [ "$rc" != 0 ] && [ "$HF_MIRROR" = 1 ]; then
      step "11b. 绕过：HF_ENDPOINT=https://hf-mirror.com（用户级）→ 重启应用 → 再下载 Whisper 模型"
      rcall ps hf_mirror On
      rcall ps stop Label=real-before-hf >/dev/null
      rcall ps launch Label=real-hf; rec launch_real_hf $?
      rcall py winqa_real whisper --label whisper-hfmirror; rec real_whisper_hfmirror $?
  fi
fi
if want 12; then
  step "12. 本地视频（无字幕，${LOCAL_SECONDS}s）→ Whisper 转写 → 真实模型出片 → 导出 + ffprobe"
  "${SCP[@]}" "$HERE/py/winqa_real.py" "$USER_@$HOST:C:/winqa/py/winqa_real.py"
  rcall py winqa_real local --seconds "$LOCAL_SECONDS"; rec real_local $?
fi
if want 13 && [ -n "$BILI_URL" ]; then
  step "13. B 站链接导入 → 进度 → 出片  $BILI_URL"
  rcall py winqa_real link --url "$BILI_URL"; rec real_link $?
fi
if want 14; then
  step "14. 首页/项目列表无卡住的 processing；截图；停止应用"
  rcall py winqa_real final; rec real_final $?
  rcall ps ui_probe Label=real >/dev/null
  rcall ps stop Label=real >/dev/null
  rcall ps hf_mirror Off >/dev/null
fi
fi

step "8. 收集日志并在验收机上导出证据包"
# collect_logs.ps1 zips the app logs into C:\winqa\out\app-logs.zip; it stays on the test machine (R27 reduced
# scope: raw logs, screenshots and media are withheld and listed in the manifest, handled by hand on the VM).
rcall ps collect_logs Label=final; rec collect_logs $?
export_bundle pull_final 99

step "9. 汇总"
# R29 point 3: ONE function decides (py/winqa_verdict.py); summarize.py only renders that verdict. steps.txt is a
# view the verdict writes. The exit code is the verdict's.
VERDICT="$OUT/runs/$RUN_ID/verdict-final.json"
python3 "$HERE/py/winqa_verdict.py" final --out "$OUT" --run-id "$RUN_ID" --dest "$VERDICT"; V_RC=$?
[ -f "$VERDICT" ] || { echo "FAIL: 没有生成最终裁决"; exit 1; }
python3 "$HERE/summarize.py" "$OUT" --verdict "$VERDICT" > "$OUT/summary.md"; S_RC=$?
cat "$OUT/summary.md" || S_RC=1
[ "$S_RC" = 0 ] || { echo "FAIL: 汇总渲染失败（rc=${S_RC}）"; exit 1; }
[ "$V_RC" = 0 ] && exit 0 || exit 1   # the verdict alone decides (I-C1; logpipe_close may still downgrade both)
