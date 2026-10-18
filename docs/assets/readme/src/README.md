# README pictures — how they are made

Every picture on the root README is generated from the running system, so the numbers match what the live app at
https://148.100.99.205 reports. Brand: white, ink `#0B0D10`, accent `#E8743B`, IBM blue `#0F62FE` for the platform,
Manrope and JetBrains Mono (subset and embedded by `fonts.py`).

| Output (in `..`) | Made by | From |
|---|---|---|
| `logo-*.svg`, `hero.svg`, `problem.svg`, `impact.svg`, `linuxone-stack.svg`, `linuxone-terminal.svg`, `live-metrics.svg`, `ibmz-deployment.svg` | `build_svgs.py` | `live/*.json` (API responses), `live/latency.json`, `live/terminal.txt` (a real session on the guest) |
| `tour.gif`, `screens/*.png` | `make_tour.py` | `shots/*.png` captured by `shoot_screens.sh` |
| `triage.gif`, `loop.gif` | `render_anim.py <name> <seconds>` | `anim/<name>.html` — pages that draw any time `?t=` exactly, captured frame by frame with headless Chrome |
| `linuxone-console.png` | by hand | a screenshot of the LinuxONE Community Cloud console, account email masked |

Refresh everything (needs `proto/deploy/ssh_config`, Google Chrome, ffmpeg, Pillow and fontTools):

```bash
docs/assets/readme/src/fetch_live.sh
```

```bash
cd docs/assets/readme/src && ./shoot_screens.sh && python3 build_svgs.py && python3 make_tour.py && python3 render_anim.py triage 7 && python3 render_anim.py loop 9
```

`build/` and `shots/` are scratch and are not committed.
