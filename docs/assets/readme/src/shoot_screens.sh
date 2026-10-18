#!/bin/zsh
# Capture the live app's screens (2x) into shots/ for make_tour.py and the README gallery.
cd "${0:A:h}"; mkdir -p shots
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; P=$(mktemp -d)
shoot(){ "$CH" --headless=new --hide-scrollbars --force-device-scale-factor=2 --window-size=1440,900 \
  --virtual-time-budget=10000 --use-angle=swiftshader --enable-unsafe-swiftshader --user-data-dir=$P/$1 \
  --screenshot=shots/$1.png "https://148.100.99.205/$2" >/dev/null 2>&1; }
I=TJ107-HYD-101
shoot readiness readiness.html & shoot decisions decisions.html & shoot decision "decision.html?issue=$I" &
shoot why "decision-why.html?issue=$I" & shoot workbench "workbench.html?issue=$I" &
shoot twin "twin.html?issue=$I&tail=TJ107" & shoot epoch epoch.html & shoot provenance provenance.html &
shoot assurance assurance.html & shoot policies policies.html & wait; ls shots
