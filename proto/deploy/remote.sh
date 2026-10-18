#!/bin/bash
# Run a command on the server inside the repo with the server environment. Usage: proto/deploy/remote.sh '<cmd>'
set -euo pipefail
. "$(dirname "$0")/lib.sh"
H=$(phx_host)
ssh -F "$SSHCFG" "$H" "source $REMOTE_REPO/proto/deploy/server.env && cd $REMOTE_REPO && $*"
