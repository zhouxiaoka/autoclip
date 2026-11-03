#!/bin/bash
# shellcheck shell=bash
# Pinned-ffmpeg helpers shared by the desktop build scripts. bash 3.2 safe
# (macOS /bin/bash): no associative arrays, no namerefs.
#
# read_ffmpeg_pin <file> <KEY>...
#   Same rule as scripts/lib/ffmpeg_pin.ps1 (scripts/tests/test_ffmpeg_pin_reader.py
#   runs one sample set through both):
#   - the file must not start with a UTF-8 BOM (rejected, not stripped);
#   - one trailing CR per line is dropped (CRLF checkouts);
#   - empty lines and lines whose first character is '#' are skipped;
#   - every other line must match ^(KEY1|KEY2|...)=[!-~]+$ (case-sensitive,
#     value = printable ASCII without spaces);
#   - each KEY must appear exactly once.
#   On success sets each KEY as a shell variable. On any violation prints
#   "ERROR: ..." to stderr, sets nothing and returns 1.
read_ffmpeg_pin() {
    local LC_ALL=C
    local file="$1"
    shift
    if [ ! -f "$file" ]; then
        echo "ERROR: $file: not found" >&2; return 1
    fi
    if [ "$(head -c 3 "$file" | od -An -tx1 | tr -d ' \n')" = "efbbbf" ]; then
        echo "ERROR: $file: starts with a UTF-8 BOM; save it without BOM" >&2; return 1
    fi
    local alt="" key
    for key in "$@"; do alt="${alt:+$alt|}$key"; done
    local re="^(${alt})=([!-~]+)\$"
    local seen=" " vals="" line n=0
    while IFS= read -r line || [ -n "$line" ]; do
        n=$((n + 1))
        line="${line%$'\r'}"
        case "$line" in ''|'#'*) continue ;; esac
        if ! [[ "$line" =~ $re ]]; then
            echo "ERROR: $file:$n: not KEY=value with a known key and no spaces" >&2; return 1
        fi
        key="${BASH_REMATCH[1]}"
        case "$seen" in *" $key "*)
            echo "ERROR: $file:$n: $key set more than once" >&2; return 1 ;;
        esac
        seen="$seen$key "
        vals="$vals$key=${BASH_REMATCH[2]}"$'\n'
    done < "$file"
    for key in "$@"; do
        case "$seen" in *" $key "*) ;; *)
            echo "ERROR: $file: $key missing" >&2; return 1 ;;
        esac
    done
    while IFS= read -r line; do
        [ -n "$line" ] && printf -v "${line%%=*}" '%s' "${line#*=}"
    done <<< "$vals"
    return 0
}

# fetch_pinned <dest> <url> <sha256>
#   Uses <dest> if present, otherwise downloads <url> once (no mirrors), then
#   verifies sha256 either way. A failed download or a mismatch deletes the
#   file and returns 1. curl: 180s per attempt, 2 retries, none after 300s.
#   Needs $PORTABLE_PY (hashing works the same on macOS and Git Bash).
fetch_pinned() {
    local dest="$1" url="$2" want="$3" got
    if [ -f "$dest" ]; then
        echo "  Cached: $dest"
    else
        mkdir -p "$(dirname "$dest")"
        rm -f "$dest.tmp"
        echo "  Downloading: $url"
        if ! curl -L --fail --http1.1 --retry 2 --retry-all-errors --retry-delay 2 \
            --retry-max-time 300 --connect-timeout 15 --max-time 180 -o "$dest.tmp" "$url"; then
            rm -f "$dest.tmp"
            echo "ERROR: download failed: $url"; return 1
        fi
        mv "$dest.tmp" "$dest"
    fi
    got="$("$PORTABLE_PY" -c 'import hashlib, sys
h = hashlib.sha256()
with open(sys.argv[1], "rb") as f:
    for chunk in iter(lambda: f.read(1 << 20), b""):
        h.update(chunk)
print(h.hexdigest())' "$dest")"
    if [ "$got" != "$want" ]; then
        rm -f "$dest"
        echo "ERROR: sha256 mismatch for $dest"
        echo "       expected $want"
        echo "       got      $got"
        return 1
    fi
    echo "  sha256 OK: $want"
}
