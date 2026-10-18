#!/bin/zsh
# usage: ./shoot.sh page [out-name]  → full-res 1920x1080 PNG of http://127.0.0.1:8137/<page>
P=${1}; N=${2:-${P%%.html}}
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars \
  --force-device-scale-factor=1 --window-size=1920,1080 --virtual-time-budget=6000 --use-angle=swiftshader --enable-unsafe-swiftshader \
  --screenshot=/Users/abishaikc/Phalanx-Solution/video/stills/$N.png "http://127.0.0.1:8137/$P" >/dev/null 2>&1
echo /Users/abishaikc/Phalanx-Solution/video/stills/$N.png
