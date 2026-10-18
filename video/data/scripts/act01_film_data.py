"""Build film/assets/act01/act01-data.js for the Act 0-1 film composition.
Sources: data/telemetry_TJ212_1hz.csv (real sortie trace), data/daily_state.csv (TJ108 ribbon,
06 Jan - 22 Jun 2026 = 168 days), screens/assets/data.js PHX_DATA.tj107 (sorties, removals)."""
import csv, json, os, re
V = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
rows = list(csv.DictReader(open(os.path.join(V, 'data/telemetry_TJ212_1hz.csv'))))
def series(col, step=12):
    v = [float(r[col]) for r in rows]
    lo, hi = min(v), max(v)
    return {'lo': lo, 'hi': hi, 'v': [round((v[i] - lo) / (hi - lo) * 1000) for i in range(0, len(v), step)]}
tel = {'n': len(rows), 'N2': series('ENG.N2'), 'T5': series('ENG.T5'), 'HYD': series('HYD.SYS1.P')}
ds = list(csv.DictReader(open(os.path.join(V, 'data/daily_state.csv'))))
ds = [r for r in ds if r['day'] <= '2026-06-22']
code = {'FMC': 'F', 'NMCM_U': 'M', 'NMCM_S': 'M', 'NMCS': 'S', 'PMCM': 'P', 'NMCD': 'D'}
tj108 = {'d0': ds[0]['day'], 'd1': ds[-1]['day'], 's': ''.join(code[r['TJ108']] for r in ds)}
src = open(os.path.join(V, 'screens/assets/data.js')).read()
m = re.search(r'tj107 = (\{.*?\});', src, re.S)
t7 = json.loads(m.group(1))
tj107 = {'t0': t7['t0'], 'T': t7['T'], 'sorties': t7['sorties'], 'removals': t7['removals']}
tm = json.load(open(os.path.join(V, 'edit/timing.json')))
act = [a for a in tm['acts'] if a['id'] == 'act01'][0]
shots, vo = {}, {}
for k in act['shots']:
    sh = tm['shots'][k]
    shots[k] = {'start': sh['act_start'], 'dur': sh['dur'], 'vo': sh['vo_at_in_act']}
    toks = json.load(open(os.path.join(V, f'edit/vo/{k}.tokens.json')))
    vo[k] = [[t['text'], round(t['start'], 3), round(t['end'], 3)] for t in toks if t['text'].strip(',.:;—')]
out = 'window.ACT01 = ' + json.dumps({'dur': act['dur'], 'shots': shots, 'vo': vo, 'tel': tel, 'tj108': tj108, 'tj107': tj107}, separators=(',', ':')) + ';\n'
open(os.path.join(V, 'film/assets/act01/act01-data.js'), 'w').write(out)
print(len(tel['N2']['v']), len(tj108['s']), tj108, len(tj107['sorties']), len(tj107['removals']))
