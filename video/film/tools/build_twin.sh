#!/bin/zsh
# Bundle the screens' twin3d.js (import-map paths) into an IIFE for HyperFrames compositions.
cd "$(dirname $0)/.."
sed "s#three/addons/#three/addons/lines/#g" ../screens/assets/twin3d.js > tools/twin3d.film.js
cat > tools/twin-entry.js <<'EOT'
import { createTwin } from './twin3d.film.js';
window.PHX_TWIN = { createTwin };
EOT
npx esbuild tools/twin-entry.js --bundle --format=iife --minify --outfile=assets/twin3d.bundle.js --log-level=warning
