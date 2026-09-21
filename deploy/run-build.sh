#!/usr/bin/env bash
# Cron entry point: load secrets, run the daily build, append to the log.
set -uo pipefail

APP_DIR="${APP_DIR:-/srv/todays-darling}"
ENV_FILE="${ENV_FILE:-/etc/todays-darling.env}"
LOG_FILE="${LOG_FILE:-/var/log/todays-darling/build.log}"
# cron's PATH is minimal; uv's installer puts it in ~/.local/bin.
UV="${UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

mkdir -p "$(dirname "$LOG_FILE")"
cd "$APP_DIR/builder" || exit 1

# flock: if a run hangs past the next scheduled one, don't start a second copy.
exec 9>"/tmp/todays-darling.lock"
if ! flock -n 9; then
  echo "$(date -Is) previous run still going; skipping" >>"$LOG_FILE"
  exit 0
fi

"$UV" run --frozen --no-dev build.py "$@" >>"$LOG_FILE" 2>&1
status=$?
[[ $status -ne 0 ]] && echo "$(date -Is) build FAILED with exit $status (previous today.json kept)" >>"$LOG_FILE"
exit $status
