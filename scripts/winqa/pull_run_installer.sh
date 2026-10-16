#!/usr/bin/env bash
# E9：验收机直接从 GitHub Actions 拉指定 run 的 Windows 安装包到 C:\winqa\inst，并校验 sha256。
# 用法: WINQA_HOST=<验收机地址> pull_run_installer.sh <run_id>
# 环境变量：WINQA_HOST（必填）、WINQA_USER、WINQA_IDENTITY（ssh 私钥路径）、WINQA_REPO、WINQA_PARTS。
# 不含任何凭据：GitHub 令牌只在运行时由 `gh auth token` 取得，经 curl -K - 走 stdin。
# 校验两层：① artifact zip 对 GitHub 记录的 digest；② 解出的 exe 对 CI internal-desktop-provenance 里记录的 sha256（有则必须一致）。
# 成功后 C:\winqa\inst\candidate-setup.exe 即为新包，旧 candidate 和历史下载残留（url-*.txt、dl*/pf* 日志）清掉；prev-setup.exe 不动。
# 签名下载 URL 只经 ssh stdin 传到远端，用完即删，不落 box 日志、不打印。
set -euo pipefail
RUN="${1:?run_id}"; REPO="${WINQA_REPO:-zhouxiaoka/autoclip}"
HOST="${WINQA_HOST:?set WINQA_HOST to the acceptance machine}"; USER_="${WINQA_USER:-Administrator}"; ID="${WINQA_IDENTITY:-$HOME/.ssh/autoclip_winqa}"
ART="autoclip-desktop-windows-x64"; PARTS="${WINQA_PARTS:-16}"
SSH=(ssh -i "$ID" -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 "$USER_@$HOST")
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

read -r AID ASIZE ADIGEST < <(gh api "repos/$REPO/actions/runs/$RUN/artifacts" --jq ".artifacts[]|select(.name==\"$ART\" and (.expired|not))|\"\(.id) \(.size_in_bytes) \(.digest // \"\")\"")
[ -n "${AID:-}" ] || { echo "run $RUN 没有可用的 $ART artifact"; exit 2; }
ADIGEST="${ADIGEST#sha256:}"
# R15/E9: 没有 digest 就无法证明下载到的就是 CI 产出的包，直接失败，不再只是打印「无」。
if ! [[ "${ADIGEST:-}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "错误：artifact $ART（run $RUN）没有有效的 sha256 digest，拒绝下载和安装。" >&2
  exit 4
fi
echo "artifact id=$AID size=$ASIZE zip_digest=$ADIGEST"

EXP_EXE=""
PROV=""
for NAME in internal-desktop-provenance internal-desktop-provenance-windows-x64; do
  if gh run download "$RUN" -R "$REPO" -n "$NAME" -D "$TMP/prov-$NAME" >/dev/null 2>&1; then
    PROV=$(ls "$TMP/prov-$NAME"/*.json 2>/dev/null | head -1); [ -n "$PROV" ] && break
  fi
done
if [ -n "$PROV" ]; then
  EXP_EXE=$(python3 - "$PROV" <<'PY'
import json,sys,re
d=json.load(open(sys.argv[1])); hits=[]
def walk(o):
    if isinstance(o,dict):
        n=str(o.get("name") or o.get("file") or o.get("path") or ""); h=o.get("sha256") or o.get("hash")
        if n.endswith("-setup.exe") and h: hits.append(str(h).lower().removeprefix("sha256:"))
        for k,v in o.items():
            if k.endswith("-setup.exe") and isinstance(v,str) and re.fullmatch(r"[0-9a-f]{64}",v.lower()): hits.append(v.lower())
            walk(v)
    elif isinstance(o,list): [walk(x) for x in o]
walk(d); print(hits[0] if hits else "")
PY
)
fi
echo "provenance exe sha256=${EXP_EXE:-无（run 未产出 provenance，只校验 zip digest 并报告 exe 哈希）}"

# 取 302 签名 URL（不打印）
URL=$( { printf 'header = "Authorization: Bearer %s"\n' "$(gh auth token)"; } | curl -sS -K - -o /dev/null -w '%{redirect_url}' -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/$REPO/actions/artifacts/$AID/zip")
[[ "$URL" == https://* ]] || { echo "拿不到 artifact 下载地址"; exit 3; }

SCP=(scp -q -i "$ID" -o BatchMode=yes -o ConnectTimeout=20)
"${SSH[@]}" 'powershell -NoProfile -Command "New-Item -ItemType Directory -Force C:\winqa\ps,C:\winqa\inst | Out-Null"'
"${SCP[@]}" "$(dirname "$0")/ps/pull_run_installer.ps1" "$USER_@$HOST:C:/winqa/ps/"
umask 077; printf '%s' "$URL" > "$TMP/url"; unset URL
"${SCP[@]}" "$TMP/url" "$USER_@$HOST:C:/winqa/inst/.url-$RUN"; rm -f "$TMP/url"
RC=0; "${SSH[@]}" "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\winqa\\ps\\pull_run_installer.ps1 -Run $RUN -Total $ASIZE -N $PARTS -WantZip $ADIGEST${EXP_EXE:+ -WantExe $EXP_EXE}" || RC=$?
"${SSH[@]}" "powershell -NoProfile -Command \"Remove-Item -Force -ErrorAction SilentlyContinue C:\\winqa\\inst\\.url-$RUN\"" || true
exit $RC
