#!/usr/bin/env bash
# Cursor afterFileEdit hook: upload changed project files via sftp_upload.py
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="${PYTHON:-python3}"
UPLOAD="$ROOT/sftp_upload.py"

input="$(cat)"
file_path=""

if command -v jq >/dev/null 2>&1; then
  file_path="$(printf '%s' "$input" | jq -r '.file_path // .path // .filePath // empty' 2>/dev/null || true)"
fi

if [[ -z "$file_path" ]]; then
  file_path="$(printf '%s' "$input" | "$PYTHON" -c "
import json, sys
try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    sys.exit(0)
for key in ('file_path', 'path', 'filePath', 'editedFile'):
    value = data.get(key)
    if isinstance(value, str) and value:
        print(value)
        break
" 2>/dev/null || true)"
fi

if [[ -z "$file_path" ]]; then
  exit 0
fi

case "$file_path" in
  "$ROOT"/*) ;;
  *) exit 0 ;;
esac

rel="${file_path#"$ROOT"/}"
rel="${rel#/}"

if [[ -z "$rel" ]]; then
  exit 0
fi

"$PYTHON" "$UPLOAD" "$rel" >/tmp/relsib-sftp-upload.log 2>&1 || {
  tail -n 5 /tmp/relsib-sftp-upload.log >&2 || true
  exit 0
}

exit 0
