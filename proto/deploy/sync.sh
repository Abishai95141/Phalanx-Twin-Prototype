#!/bin/bash
# Push the local repo (source of truth for code and docs) to the server. Never deletes server files, and never
# replaces a server file that is newer than the local copy (rsync -u), so outputs generated there (proto/runs,
# eval reports) survive. Usage: proto/deploy/sync.sh [--with-data] [--restart]
# --restart reloads the ground API afterwards: a running API imports modules lazily, so new and old code can
# mix after a sync (an ImportError on the first request). Decisions survive: they are restored from the log.
set -euo pipefail
. "$(dirname "$0")/lib.sh"
H=$(phx_host)
ssh -F "$SSHCFG" "$H" "mkdir -p $REMOTE_REPO"
rsync -azu -e "ssh -F $SSHCFG" \
  --exclude '.venv/' --exclude '__pycache__/' --exclude '.numba_cache/' --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' --exclude 'proto/runs/' --exclude 'video/tools/cache/' --exclude '.DS_Store' \
  "$REPO/" "$H:$REMOTE_REPO/"
if [[ " $* " == *" --with-data "* ]]; then
  rsync -az -e "ssh -F $SSHCFG" /Users/abishaikc/Downloads/phalanx_data_layer_preview/ "$H:$REMOTE_HOME/phalanx_data_layer_preview/"
fi
echo "synced to $H:$REMOTE_REPO"
if [[ " $* " == *" --restart "* ]]; then
  ssh -F "$SSHCFG" "$H" "sudo systemctl restart phx-ground && until curl -s http://127.0.0.1:8700/api/health >/dev/null; do sleep 2; done; echo ground API restarted"
fi
