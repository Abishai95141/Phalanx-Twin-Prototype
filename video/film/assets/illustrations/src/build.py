"""Rebuild every plate:  cd video/film/assets/illustrations/src && python3 build.py
Writes the SVGs to video/film/assets/illustrations/ and mirrors them to video/screens/assets/illus/
(the contact sheet video/screens/illustrations.html reads the mirror)."""
import importlib
import re
import sys

PLATES = ['plate01_aircraft', 'plate02_hydraulics', 'plate03_pump', 'plate04_engine', 'plate05_gear', 'plate06_chute',
          'plate07_lru', 'plate08_server', 'plate09_download', 'plate10_gate', 'plate11_chain', 'plate12_loop',
          'plate13_tools', 'plate00_key']
NAMES = ['aircraft-3view', 'hydraulic-system', 'hyd-pump', 'f404-engine', 'main-gear-tyre', 'brake-chute',
         'avionics-lru', 'station-server', 'sortie-download', 'contract-gate', 'hash-chain', 'mapek-loop',
         'assistant-tools', 'style-key']

if __name__ == '__main__':
    seen = {}
    for mod, name in zip(PLATES, NAMES):
        d = importlib.import_module(mod).build()
        size = d.save(name + '.svg')
        svg = d.render()
        for i in re.findall(r'\sid="([^"]+)"', svg):
            if i in seen and seen[i] != name:
                sys.exit('id collision %s in %s and %s' % (i, name, seen[i]))
            seen[i] = name
        bad = [c for c in ('<linearGradient', '<radialGradient', '<image', '<filter', 'feGaussianBlur', 'box-shadow') if c in svg]
        print('%-22s %7d bytes  %4d ids  %s' % (name + '.svg', size, len(re.findall(r'\sid="', svg)),
                                                 ('FORBIDDEN: ' + ','.join(bad)) if bad else 'ok'))
