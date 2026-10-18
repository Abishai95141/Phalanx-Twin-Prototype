#!/bin/zsh
# Build the v2 cut (3:40): timing → captions → music → timeline → assemble → two-pass loudnorm.
#   cd video && zsh edit/master_v2.sh        → renders/phalanx_twin_film_v2.mp4   (v1 master is left untouched)
# Needs renders/act01_v2, act2_v2, act4_v2, linuxone (film/*.html), act3a, act3b, ins_hyd and manim/M5.
set -e
cd "${0:A:h}/.."
FF=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg
python3 edit/build_timing_v2.py > /dev/null
.venv/bin/python -I edit/make_captions.py timing_v2.json captions_v2.ass
.venv/bin/python -I edit/make_music.py timing_v2.json music/bed_v2.wav
python3 edit/make_timeline_v2.py
.venv/bin/python -I tools/assembly/assemble.py edit/master_timeline_v2.json
J=$($FF -hide_banner -nostats -i renders/master_pre_v2.mp4 -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
MI=$(echo "$J" | .venv/bin/python -I -c "import json,sys; d=json.load(sys.stdin); print(f\"measured_I={d['input_i']}:measured_TP={d['input_tp']}:measured_LRA={d['input_lra']}:measured_thresh={d['input_thresh']}:offset={d['target_offset']}\")")
$FF -y -hide_banner -loglevel error -i renders/master_pre_v2.mp4 -c:v copy -af "loudnorm=I=-16:TP=-1.5:LRA=11:${MI}:linear=true,aresample=48000,alimiter=limit=0.82:attack=3:release=60:level=0" -c:a aac -b:a 192k -movflags +faststart -metadata title="Phalanx Twin — Dilijens · IBM Z Datathon" renders/phalanx_twin_film_v2.mp4
$FF -hide_banner -nostats -i renders/phalanx_twin_film_v2.mp4 -af ebur128=peak=true -f null - 2>&1 | grep -E "^\s+(I:|Peak:)" | tail -2
echo renders/phalanx_twin_film_v2.mp4
