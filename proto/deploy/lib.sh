# Shared helpers for the deploy scripts (sourced). Picks whichever address of the server is reachable.
DEPLOY="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
REPO="$(cd "$DEPLOY/../.." && pwd)"
SSHCFG="$DEPLOY/ssh_config"
REMOTE_HOME=/home/linux1/phalanx
REMOTE_REPO=$REMOTE_HOME/Phalanx-Solution
if [ ! -f "$SSHCFG" ]; then
  echo "missing $SSHCFG — copy ssh_config.example to ssh_config and fill in the server address, user and key path" >&2
fi
phx_host() {
  for h in phx phx6; do
    if ssh -F "$SSHCFG" -o ConnectTimeout=6 -o BatchMode=yes "$h" true 2>/dev/null; then echo "$h"; return 0; fi
  done
  echo "server unreachable (tried IPv4 and NAT64)" >&2; return 1
}
