#!/bin/zsh
# Build the film master: timeline → assemble (video, overlays, narration, ducked music, burned captions) → two-pass loudnorm.
#   cd video && zsh edit/master.sh        → renders/phalanx_twin_film.mp4
set -e
cd "${0:A:h}/.."
FF=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg
python3 edit/make_timeline.py
.venv/bin/python -I tools/assembly/assemble.py edit/master_timeline.json
J=$($FF -hide_banner -nostats -i renders/master_pre.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
MI=$(echo "$J" | .venv/bin/python -I -c "import json,sys; d=json.load(sys.stdin); print(f\"measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}:measured_thresh={d['input_thresh']}:offset={d['target_offset']}\")")
$FF -y -hide_banner -loglevel error -i renders/master_pre.mp4 -c:v copy -af "loudnorm=I=-16:TP=-1.5:LRA=11:${MI}:linear=true,aresample=48000,alimiter=limit=0.82:attack=3:release=60:level=0" -c:a aac -b:a 192k -movflags +faststart renders/phalanx_twin_film.mp4
$FF -hide_banner -nostats -i renders/phalanx_twin_film.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|Peak:)" | tail -2
echo renders/phalanx_twin_film.mp4
