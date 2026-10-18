/* PHALANX TWIN — builds the twin page's view (systems tree, lenses, strip) from the ground API's tail state
   (/api/twin/{tail}: installed, alarms, sorties, usage) when the response does not carry those fields itself.
   Optional fields of SHAPES.md §twin: whatever the backend sends wins; this only fills what is missing. */
(function () {
  // contract position (part number + index) → system, 3D node, label
  const POS = {
    'SYN-PN-ENG-F404#1': ['ENG', 'ENGINE', 'F404 engine'], 'SYN-PN-FADEC#1': ['ENG', 'FADEC', 'FADEC'], 'SYN-PN-JFS#1': ['ENG', 'JFS', 'JFS starter'],
    'SYN-PN-HYDP#1': ['HYD', 'HYD_PUMP', 'Pump 1 · SYS1'], 'SYN-PN-HYDP#2': ['HYD', 'HYD_PUMP2', 'Pump 2 · SYS2'], 'SYN-PN-AMAGB#1': ['HYD', 'AMAGB', 'AMAGB'],
    'SYN-PN-INGPS#1': ['AVI', 'INGPS', 'INS/GPS'], 'SYN-PN-RADAR#1': ['AVI', 'RADAR', 'Radar'], 'SYN-PN-ADC#1': ['ADC', 'ADC', 'ADC'],
    'SYN-PN-TYRE#1': ['LG', 'MLG_L', 'Tyre L'], 'SYN-PN-TYRE#2': ['LG', 'MLG_R', 'Tyre R'], 'SYN-PN-BRAKE#1': ['LG', 'MLG_L', 'Brake L'], 'SYN-PN-BRAKE#2': ['LG', 'MLG_R', 'Brake R'],
    'SYN-PN-BCU#1': ['LG', null, 'Brake control unit'], 'SYN-PN-CHUTE#1': ['LG', 'CHUTE', 'Brake chute'],
    'SYN-PN-GEN#1': ['ELE', null, 'Generator'], 'SYN-PN-FQGS#1': ['FUE', 'FUEL_F1', 'Fuel gauging'], 'SYN-PN-DFCC#1': ['FCS', 'DFCC', 'DFCC'], 'SYN-PN-OBOGS#1': ['ECS', null, 'OBOGS']
  };
  const SYS = [['ENG', 'Engine & FADEC'], ['HYD', 'Hydraulics'], ['AVI', 'Avionics'], ['ADC', 'Air data'], ['LG', 'Landing gear'], ['ELE', 'Electrical'], ['FUE', 'Fuel'], ['FCS', 'Flight controls'], ['ECS', 'Environmental']];
  // alarm code → the component it points at (dictionary source LRU / system of the code)
  const CODE = c => ({ HYD: 'HYD_PUMP', LGB: 'MLG_L', SPS: 'JFS', ENG: 'FADEC', ADC: 'ADC', FCS: 'DFCC', FUE: 'FUEL_F1' }[c.slice(0, 3)]
    || { 'AVI-201': 'RADAR', 'AVI-203': 'INGPS', 'AVI-204': 'AHRS' }[c] || null);
  const SRC = { FLEET: 'Simulated fleet', TRAIN: 'Simulated fleet history', OVERLAY: 'Generated engine trend (overlay v0.1)' };
  const MO = { Jan: 0, Feb: 1, Mar: 2, Apr: 3, May: 4, Jun: 5, Jul: 6, Aug: 7, Sep: 8, Oct: 9, Nov: 10, Dec: 11 };

  window.PHX_TWINVIEW = function (j) {
    const year = +String(j.asof).slice(0, 4), asofMs = Date.parse(String(j.asof).slice(0, 10) + 'T00:00:00Z');
    j.asof_label = j.asof_label || PHX.asofLabel(j.asof);
    j.snapshot = j.snapshot || { at: `${String(j.asof).slice(11, 16)} IST`, id: j.snapshot_id || '' };
    const alarms = (j.alarms || []).slice().sort((a, b) => b.consecutive_sorties - a.consecutive_sorties || b.count - a.count);
    const active = alarms.filter(a => a.consecutive_sorties > 0);
    if (!j.systems) {
      const by = {};
      (j.installed || []).forEach(i => { const m = POS[i.position] || ['ECS', null, i.position]; (by[m[0]] = by[m[0]] || []).push({ node: m[1], label: m[2], serial: i.serial, part_no: i.part_no, since: i.since, inferred: i.inferred }); });
      j.systems = SYS.filter(([id]) => by[id]).map(([id, name]) => ({ id, name, items: by[id], tone: by[id].some(i => active.some(a => CODE(a.code) === i.node)) ? 'accent' : null }));
    }
    const fleet = window.PHX_DATA && PHX_DATA.fleet.find(f => f.tail === j.tail);
    if (!j.lenses) {
      const paint = {}, arcs = [], tags = [];
      active.forEach(a => { const n = CODE(a.code); if (!n) return; paint[n] = 'suspect'; arcs.push({ from: 'BHEEM_EU', to: n, weight: 0.8 });
        tags.push({ node: n, kind: 'sus', k: `${a.severity} · ${a.code}`, v: `${a.consecutive_sorties} consecutive sortie${a.consecutive_sorties === 1 ? '' : 's'}`, s: `${a.count} reports · last ${a.last_seen}` }); });
      const life = fleet ? fleet.tyre_ldg / 8 : null, lc = life == null ? null : life >= 0.85 ? '#D4492A' : life >= 0.6 ? '#C98512' : '#1F8A4C';
      const todo = t => [{ kind: 'text', text: t }];
      j.lenses = [
        { id: 'status', label: 'Status', icon: 'target', source: j.source || SRC.FLEET, paint: Object.fromEntries(alarms.filter(a => CODE(a.code)).map(a => [CODE(a.code), a.consecutive_sorties > 0 ? '#E8743B' : '#C7C9CC'])),
          legend: [{ kind: 'dot', color: '#E8743B', text: 'Alarm on the last sortie' }, { kind: 'dot', color: '#C7C9CC', text: 'Alarm earlier' }] },
        { id: 'evidence', label: 'Evidence', icon: 'link', source: j.source || SRC.FLEET, reporter: active.length ? 'BHEEM_EU' : null, paint: active.length ? { BHEEM_EU: 'reporter', ...paint } : {}, dim: true, arcs, tags,
          legend: active.length ? [{ kind: 'dot', color: 'var(--wire)', text: 'Reporter' }, { kind: 'bar', color: 'var(--accent)', text: 'Code still firing' }] : todo('No alarm on the last sortie') },
        { id: 'false_alarm', label: 'False alarm', icon: 'scale', source: SRC.FLEET, paint: {}, legend: todo('Not produced by the ground API yet') },
        { id: 'life', label: 'Life left', icon: 'tyre', source: SRC.FLEET, paint: lc ? { MLG_L: lc, MLG_R: lc } : {},
          tags: fleet ? [{ node: 'MLG_R', kind: 'rep', k: 'Life · tyres', v: `${fleet.tyre_ldg} of 8 landings`, s: `${8 - fleet.tyre_ldg} landings left` }] : [],
          legend: [{ kind: 'dot', color: '#1F8A4C', text: '< 60 % used' }, { kind: 'dot', color: '#C98512', text: '60–85 %' }, { kind: 'dot', color: '#D4492A', text: '> 85 %' }] },
        { id: 'removal_risk', label: 'Removal risk', icon: 'wrench', source: SRC.TRAIN, paint: {}, legend: todo('Not produced by the ground API yet') },
        { id: 'engine_margin', label: 'Engine margin', icon: 'engine', source: SRC.OVERLAY, paint: {}, legend: todo('Not produced by the ground API yet') }
      ];
      j.lens = j.lens || (active.length ? 'evidence' : 'status');
    }
    j.selected = j.selected || (active.map(a => CODE(a.code)).find(Boolean)) || ((j.systems[0] || { items: [] }).items[0] || {}).node || 'ENGINE';
    if (j.strip === undefined && j.sorties && j.sorties.length) {
      const code = (active[0] || alarms[0] || {}).code, day = t => { const [d, m, hm] = t.split(' '), [h, mi] = hm.split(':'); return { ms: Date.UTC(year, MO[m], +d, +h, +mi) }; };
      const t0ms = Date.UTC(year, MO[j.sorties[0].t.split(' ')[1]], +j.sorties[0].t.split(' ')[0]);
      j.strip = { t0: new Date(t0ms).toISOString().slice(0, 10), T: (asofMs + 6 * 36e5 - t0ms) / 864e5, state: [], removals: [], marks: [],
        sorties: j.sorties.map(s => [(day(s.t).ms - t0ms) / 864e5, code && s.codes.includes(code) ? 1 : 0]),
        asof_label: PHX.asofShort(j.asof), labels: { sorties: code ? `Sorties · ${code}` : 'Sorties', removals: 'Removals' } };
    }
    j.panels = j.panels || {}; j.insight = j.insight || null;
    j.foot = j.foot || [`snapshot ${j.snapshot.at} · ${String(j.snapshot.id).slice(0, 8)}…`, `${j.source || SRC.FLEET} · contract a4396f1d`];
    // generic panel for any installed item without one
    j.systems.forEach(s => s.items.forEach(i => { if (!i.node || j.panels[i.node]) return;
      const al = alarms.filter(a => CODE(a.code) === i.node);
      j.panels[i.node] = { title: i.label, serial: i.serial, inferred: !!i.inferred, note: i.inferred ? 'Install record not yet ingested — position taken from a job' : (i.since ? `Installed ${i.since}` : ''),
        tiers: ['DESC'], status: { pill: j.status, kv: al.length ? al.map(a => ({ k: `${a.severity} · ${a.count} reports`, code: a.code, v: a.consecutive_sorties ? `standing · ${a.consecutive_sorties} flight${a.consecutive_sorties === 1 ? '' : 's'}` : `last ${a.last_seen}` })) : [{ k: 'Open issue', v: 'none on this component' }] },
        foot: j.foot };
    }));
    return j;
  };
})();
