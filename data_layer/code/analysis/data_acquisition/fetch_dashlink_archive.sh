#!/usr/bin/env bash
# Fetch one NASA DASHlink "Sample Flight Data" archive, retrying until the server is reachable.
# Usage: fetch_dashlink_archive.sh <archive-name e.g. Tail_687_2.zip> <dest-dir> [max-hours]
# Integrity checks only (size vs Content-Length, SHA-256, zip listing). The archive is extracted, but
# no flight data is analysed: archive 2 is the untouched holdout for settling-experiment round 2.
set -euo pipefail
NAME="$1"; DEST="$2"; MAX_H="${3:-24}"
URL="https://c3.ndc.nasa.gov/dashlink/static/media/dataset/${NAME}"
mkdir -p "$DEST"; LOG="$DEST/fetch.log"
deadline=$(( $(date +%s) + MAX_H*3600 ))
echo "$(date '+%F %T') start $URL" >> "$LOG"
while :; do
  hdr=$(curl -sSIL --max-time 30 "$URL" 2>&1 || true)
  len=$(printf '%s\n' "$hdr" | tr -d '\r' | awk 'tolower($1)=="content-length:"{v=$2} END{print v}')
  if [[ -n "${len:-}" && "$len" -gt 1000000 ]]; then
    echo "$(date '+%F %T') reachable, Content-Length=$len" >> "$LOG"
    if (( len > 2*1024*1024*1024 )); then echo "$(date '+%F %T') ABORT: larger than 2 GB" >> "$LOG"; exit 3; fi
    if curl -sSL --fail --retry 5 --retry-delay 30 -C - --max-time 7200 -o "$DEST/$NAME" "$URL" 2>>"$LOG"; then
      got=$(stat -f %z "$DEST/$NAME")
      if [[ "$got" == "$len" ]]; then
        sha=$(shasum -a 256 "$DEST/$NAME" | awk '{print $1}')
        echo "$(date '+%F %T') downloaded $got bytes sha256=$sha" >> "$LOG"
        mkdir -p "$DEST/mat"
        unzip -q -o "$DEST/$NAME" -d "$DEST/mat"
        n=$(find "$DEST/mat" -name '*.mat' | wc -l | tr -d ' ')
        first=$(find "$DEST/mat" -name '*.mat' -exec basename {} \; | sort | head -1)
        last=$(find "$DEST/mat" -name '*.mat' -exec basename {} \; | sort | tail -1)
        echo "$(date '+%F %T') extracted n_mat=$n first=$first last=$last" >> "$LOG"
        echo "DONE $NAME bytes=$got sha256=$sha n_mat=$n first=$first last=$last"
        exit 0
      fi
      echo "$(date '+%F %T') size mismatch got=$got want=$len; retrying" >> "$LOG"
    fi
  else
    echo "$(date '+%F %T') unreachable; retry in 300 s" >> "$LOG"
  fi
  (( $(date +%s) > deadline )) && { echo "$(date '+%F %T') GAVE UP after ${MAX_H} h" >> "$LOG"; echo "GAVE UP"; exit 2; }
  sleep 300
done
