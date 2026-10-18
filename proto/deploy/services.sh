#!/bin/bash
# Prototype services ON THE SERVER (run via proto/deploy/remote.sh). systemd units start them at boot.
#   proto/deploy/services.sh install          install/refresh the systemd units and enable them
#   proto/deploy/services.sh start|stop|restart ground|runner
#   proto/deploy/services.sh status
#   proto/deploy/services.sh reset            archive the live run and rebuild it at 22 Jun 06:00 (~4 min)
set -uo pipefail
source "$(dirname "$0")/server.env"
mkdir -p "$PHX_HOME/logs"
case ${1:-status} in
  install)
    sudo cp "$PHX_REPO"/proto/deploy/systemd/phx-*.service /etc/systemd/system/
    sudo systemctl daemon-reload && sudo systemctl enable phx-runner phx-ground nginx >/dev/null 2>&1 && echo "units installed and enabled" ;;
  start|stop|restart)
    sudo systemctl "$1" "phx-${2:?service}" && echo "$1 phx-$2" ;;
  status)
    for n in runner ground; do echo "$n: $(systemctl is-active phx-$n)"; done
    curl -s http://127.0.0.1:8710/status; echo ;;
  reset)
    # a fresh runner process (picks up new code; no journal replay), the live run archived — never deleted —
    # and rebuilt at 22 Jun 06:00; then the API opens the epoch, which starts the paired simulations
    sudo systemctl stop phx-ground phx-runner
    if [ -d "$PHX_REPO/proto/runs/live" ]; then
      mkdir -p "$PHX_REPO/proto/runs/archive"
      mv "$PHX_REPO/proto/runs/live" "$PHX_REPO/proto/runs/archive/live-$(date +%Y%m%dT%H%M%S)"
    fi
    sudo systemctl start phx-runner
    until curl -s http://127.0.0.1:8710/status >/dev/null 2>&1; do sleep 2; done
    curl -s -X POST http://127.0.0.1:8710/init -H 'content-type: application/json' -d '{"run_id":"live"}' | head -c 160; echo
    sudo systemctl start phx-ground
    until curl -s http://127.0.0.1:8700/api/health >/dev/null 2>&1; do sleep 2; done
    curl -s http://127.0.0.1:8700/api/epoch >/dev/null && echo "fresh live run at Mon 22 Jun 06:00; paired simulations started (~25 min)" ;;
esac
