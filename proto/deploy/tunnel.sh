#!/bin/bash
# Forward the server's ground API and screens (127.0.0.1:8700 there) to http://localhost:${1:-8701} here.
# Local port 8701 by default, so it never clashes with a local `ground` dev server on 8700. Reconnects by itself
# when the network changes (IPv4 ↔ IPv6-only/NAT64) or the connection drops; stop it with Ctrl-C.
set -uo pipefail
. "$(dirname "$0")/lib.sh"
while true; do
  H=$(phx_host) || { sleep 5; continue; }
  ssh -F "$SSHCFG" -N -o ExitOnForwardFailure=yes -L "${1:-8701}:127.0.0.1:8700" "$H"
  echo "tunnel to $H closed ($?); reconnecting in 3 s" >&2
  sleep 3
done
