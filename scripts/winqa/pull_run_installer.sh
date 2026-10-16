#!/usr/bin/env bash
# E9：验收机直接从 GitHub Actions 拉指定 run 的 Windows 安装包到 C:\winqa\inst，并校验 sha256。
# 用法: WINQA_HOST=<验收机地址> pull_run_installer.sh <run_id>
# 环境变量：WINQA_HOST（必填）、WINQA_USER、WINQA_IDENTITY（ssh 私钥路径）、WINQA_REPO、WINQA_PARTS。
# 不含任何凭据：GitHub 令牌只在运行时由 `gh auth token` 取得，经 curl -K - 走 stdin。
# 校验两层：① artifact zip 对 GitHub 记录的 digest（缺失即退出 4）；
#           ② 解出的 exe 对 provenance 里记录的 sha256。run 里列出了 provenance 但下载或解析失败即退出 5；
#              run 确实没有 provenance 时只校验 zip，并明确打印出来。
# 退出码：2 无 artifact；3 拿不到下载地址；4 无有效 digest；5 provenance 下载/解析失败；其它为远端脚本退出码。
# 兼容 macOS 自带 bash 3.2：所有变量都写成 ${VAR}（R16 #50：不加花括号的变量紧挨中文全角字符会被误解析）。
set -euo pipefail
RUN="${1:?run_id}"; REPO="${WINQA_REPO:-zhouxiaoka/autoclip}"
HOST="${WINQA_HOST:?set WINQA_HOST to the acceptance machine}"; USER_="${WINQA_USER:-Administrator}"; ID="${WINQA_IDENTITY:-${HOME}/.ssh/autoclip_winqa}"
ART="autoclip-desktop-windows-x64"; PARTS="${WINQA_PARTS:-16}"
PROV_NAMES="internal-desktop-provenance internal-desktop-provenance-windows-x64"
SSH=(ssh -i "${ID}" -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 "${USER_}@${HOST}")
TMP=$(mktemp -d); trap 'rm -rf "${TMP}"' EXIT

redact() { sed -E -e 's#(/Users|/home)/[^/[:space:]]+#\1/<user>#g' -e 's#[A-Za-z]:\\\\Users\\\\[^\\[:space:]]+#C:\\Users\\<user>#g' -e 's#https?://[^[:space:]]+#<url>#g'; }

LISTING=$(gh api "repos/${REPO}/actions/runs/${RUN}/artifacts" --jq '.artifacts[]|select(.expired|not)|"\(.name) \(.id) \(.size_in_bytes) \(.digest // "")"')
LINE=$(printf '%s\n' "${LISTING}" | awk -v a="${ART}" '$1==a{print; exit}')
read -r _N AID ASIZE ADIGEST <<<"${LINE:-}" || true
[ -n "${AID:-}" ] || { echo "run ${RUN} 没有可用的 ${ART} artifact" >&2; exit 2; }
ADIGEST="${ADIGEST:-}"; ADIGEST="${ADIGEST#sha256:}"
# R15/E9: 没有 digest 就无法证明下载到的就是 CI 产出的包，直接失败。
if ! [[ "${ADIGEST}" =~ ^[0-9a-f]{64}$ ]]; then
  echo "错误：artifact ${ART}（run ${RUN}）没有有效的 sha256 digest，拒绝下载和安装。" >&2
  exit 4
fi
echo "artifact id=${AID} size=${ASIZE} zip_digest=${ADIGEST}"

# R16 #49: 只有 run 里确实没有 provenance 才允许跳过第二层；列出了却下载/解析失败必须终止。
EXP_EXE=""; PROV_NAME=""
for NAME in ${PROV_NAMES}; do
  if printf '%s\n' "${LISTING}" | awk -v a="${NAME}" '$1==a{f=1} END{exit !f}'; then PROV_NAME="${NAME}"; break; fi
done
if [ -n "${PROV_NAME}" ]; then
  if ! gh run download "${RUN}" -R "${REPO}" -n "${PROV_NAME}" -D "${TMP}/prov" >"${TMP}/prov.log" 2>&1; then
    echo "错误：run ${RUN} 有 ${PROV_NAME}，但下载失败：" >&2; redact <"${TMP}/prov.log" | tail -5 >&2; exit 5
  fi
  PROV_FILE=$(ls "${TMP}/prov"/*.json 2>/dev/null | head -1 || true)
  [ -n "${PROV_FILE}" ] || { echo "错误：${PROV_NAME} 里没有 json 文件。" >&2; exit 5; }
  if ! EXP_EXE=$(python3 - "${PROV_FILE}" 2>"${TMP}/parse.log" <<'PY'
import json, re, sys
d = json.load(open(sys.argv[1], encoding="utf-8")); hits = []
def walk(o):
    if isinstance(o, dict):
        n = str(o.get("name") or o.get("file") or o.get("path") or ""); h = o.get("sha256") or o.get("hash")
        if n.endswith("-setup.exe") and isinstance(h, str): hits.append(h.lower().removeprefix("sha256:"))
        for k, v in o.items():
            if k.endswith("-setup.exe") and isinstance(v, str): hits.append(v.lower().removeprefix("sha256:"))
            walk(v)
    elif isinstance(o, list):
        for x in o: walk(x)
walk(d)
good = sorted({h for h in hits if re.fullmatch(r"[0-9a-f]{64}", h)})
if len(good) != 1 or len(good) != len(set(hits)):
    sys.exit("provenance has %d valid / %d recorded setup.exe hashes; expected exactly one valid" % (len(good), len(set(hits))))
print(good[0])
PY
  ) || ! [[ "${EXP_EXE}" =~ ^[0-9a-f]{64}$ ]]; then
    echo "错误：${PROV_NAME} 解析不出有效的 exe sha256：" >&2; redact <"${TMP}/parse.log" | tail -3 >&2; exit 5
  fi
  echo "provenance (${PROV_NAME}) exe sha256=${EXP_EXE}"
else
  echo "注意：run ${RUN} 没有 provenance artifact，只校验 zip digest 并报告 exe 哈希。"
fi

# 取 302 签名 URL（不打印）
URL=$( { printf 'header = "Authorization: Bearer %s"\n' "$(gh auth token)"; } | curl -sS -K - -o /dev/null -w '%{redirect_url}' -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/${REPO}/actions/artifacts/${AID}/zip")
[[ "${URL}" == https://* ]] || { echo "拿不到 artifact 下载地址" >&2; exit 3; }

SCP=(scp -q -i "${ID}" -o BatchMode=yes -o ConnectTimeout=20)
"${SSH[@]}" 'powershell -NoProfile -Command "New-Item -ItemType Directory -Force C:\winqa\ps,C:\winqa\inst | Out-Null"'
"${SCP[@]}" "$(dirname "$0")/ps/pull_run_installer.ps1" "${USER_}@${HOST}:C:/winqa/ps/"
umask 077; printf '%s' "${URL}" > "${TMP}/url"; unset URL
"${SCP[@]}" "${TMP}/url" "${USER_}@${HOST}:C:/winqa/inst/.url-${RUN}"; rm -f "${TMP}/url"
RC=0; "${SSH[@]}" "powershell -NoProfile -ExecutionPolicy Bypass -File C:\\winqa\\ps\\pull_run_installer.ps1 -Run ${RUN} -Total ${ASIZE} -N ${PARTS} -WantZip ${ADIGEST}${EXP_EXE:+ -WantExe ${EXP_EXE}}" || RC=$?
"${SSH[@]}" "powershell -NoProfile -Command \"Remove-Item -Force -ErrorAction SilentlyContinue C:\\winqa\\inst\\.url-${RUN}\"" || true
exit "${RC}"
