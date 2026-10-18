/* Film data → /api response shapes (assets/SHAPES.md). Loaded by api.js only with ?source=film, after the film
   data files data.js, data-decisions.js, data-epoch.js, data-workbench.js and data-provenance.js.
   It holds the values the film typed into its HTML, so the loop pages render the film's Mon 22 Jun epoch.
   Everything here is synthetic (Phalanx data layer v0.9 simulated fleet); nothing is real Tejas / IAF data. */
(function () {
  const D = window.PHX_DATA, DEC = window.PHX_DEC, EP = window.PHX_EP, WB = window.PHX_WB, PR = window.PHX_PROV;
  const Q = new URLSearchParams(location.search);
  const STATE = Q.get('state');                 // film moments: approved · submitted · board · early
  const EARLY = STATE === 'early';              // 06:05, before triage has raised anything: empty board, no orders
  const PAGE = document.body.dataset.page;
  const SRC = { FLEET: 'Simulated fleet', TRAIN: 'Simulated fleet history', OVERLAY: 'Generated engine trend (overlay v0.1)' };
  const TJ107 = 'TJ107-HYD-101';
  const TS107 = 'phx:P-DEC-01:1.4.0:20260622T0800:TJ107:TROUBLESHOOT:748653aa6bcf4544';
  const CMC107 = 'phx:P-DEC-01:1.4.0:20260622T0800:TJ107:CHANGE_MONITORING_CONFIG:6c744e071d8445f0';

  // ---- epoch clock: the film shows the board at 06:12, and the 08:00 orders page at 07:52 (or 08:00 issued)
  const SUBMITTED = PAGE === 'epoch' && STATE === 'submitted';
  const NOW = PAGE === 'epoch' ? (SUBMITTED ? '08:00' : '07:52') : '06:12';
  const clock = {
    epoch: '20260622T0800', day: 'Mon 22 Jun', asof: 'Mon 22 Jun 06:00 IST', now: NOW,
    snapshot: '06:00', engines: '06:04', freeze: '07:45', issue: '08:00',
    phase: SUBMITTED ? 'SUBMITTED' : PAGE === 'epoch' ? 'FROZEN' : 'BOARD_OPEN',
    due: DEC.board.length, snapshot_id: DEC.snapshot.hash
  };
  const mins = hm => { const [h, m] = hm.split(':').map(Number); return h * 60 + m; };
  const STEPS = [
    { key: 'SNAPSHOT', t: '06:00', label: 'Snapshot sealed' },
    { key: 'ENGINES', t: '06:04', label: 'Engines done' },
    { key: 'BOARD_OPEN', t: '06:12', label: 'Board open' },
    { key: 'FREEZE', t: '07:45', label: 'Board freezes', done_label: 'Board frozen' },
    { key: 'SIGN', t: '07:52', label: 'Signatures', done_label: 'Signed', done_t: '07:57' },
    { key: 'SUBMIT', t: '08:00', label: 'Orders issued' }
  ];
  const cur = STEPS.reduce((k, s, i) => (mins(s.t) <= mins(NOW) ? i : k), 0);
  const timeline = STEPS.map((s, i) => ({ ...s, state: i < cur ? 'done' : i === cur ? 'now' : 'next' }));

  // ---- orders for 08:00 (PHX_EP.orders + display fields)
  const WHAT = {
    'TJ103-LGB-501:TROUBLESHOOT': 'Gear unsafe · LGB-501', 'TJ106-LGB-501:TROUBLESHOOT': 'Gear unsafe · LGB-501',
    'TJ107-HYD-101:TROUBLESHOOT': 'Hydraulic alarm · HYD-101', 'TJ107-HYD-101:CHANGE_MONITORING_CONFIG': 'Filter HYD-101',
    'TJ108-AOG-CHUTE:EXPEDITE_SPARES': 'Brake chute · D-sulur-26093-0002', 'TJ105-TYRE:REQUISITION_SPARES': 'Tyres · SYN-PN-TYRE × 2',
    'TJ105-SPS-501:TROUBLESHOOT': 'Starter · SPS-501'
  };
  const orders = EP.orders.map(o => {
    const dropped = o.item === 'TJ105-TYRE' ? { label: 'Tyre requisition', reason: 'no change in 30 paired simulations' } : null;
    const human = o.issuer_kind === 'HUMAN' || (o.dry && o.dry.human_only);
    return {
      ...o, what: WHAT[`${o.item}:${o.action}`] || o.action, authority: human ? 'HUMAN' : 'AGENT', dropped,
      status: dropped ? 'DROPPED' : SUBMITTED ? 'ACCEPTED' : human ? 'NEEDS_SIGNATURE' : 'READY',
      signed_by: human && SUBMITTED ? 'ENGG-OFFICER' : null
    };
  });

  const epoch = () => ({
    ...EP, clock, timeline, orders,
    signatures: [{
      order_id: CMC107, title: 'Filter HYD-101 on TJ107',
      text: 'The code is masked while the indication path is troubleshot. It is still evaluated, only not recorded.',
      rows: [{ k: 'Order', v: 'CHANGE_MONITORING_CONFIG', mono: true }, { k: 'Evidence', v: '63 records · all before 06:00' },
        { k: 'Next 30 days, paired simulations', v: '+21.7 pts mission capable' }, { k: 'In-flight failures', v: '+0.07 · not significant', muted: true }]
    }],
    log_summary: [
      { label: 'Board frozen', hash: 'b73e0c5c' }, { label: 'Signed · CHANGE_MONITORING_CONFIG', hash: '6b4e2e71' },
      { label: 'Orders submitted · 6', hash: '99aabcd8' }, { label: 'Gateway ACCEPTED · 6', hash: 'e2d1e49d' },
      { label: 'Status QUEUED · 6', hash: '649543eb' }, { label: 'Chain head', hash: 'afd2fdab' }
    ]
  });

  // ---- readiness
  const CARDS = {
    TJ101: { zones: [], tone: 'nmcd', headline: 'At depot for overhaul', detail: 'In depot 26 days' },
    TJ102: { zones: [{ zone: 'HYD_PUMP', tone: 'nmcm' }], headline: 'Hydraulic alarm recurring', detail: '24 flights since 9 Apr' },
    TJ103: { zones: [{ zone: 'MLG_L', tone: 'p1' }, { zone: 'MLG_R', tone: 'p1' }], headline: 'Gear unsafe warning', detail: 'Twice in ten days' },
    TJ104: { zones: [], headline: 'Flying normally', detail: 'Two advisory defects deferred' },
    TJ105: { zones: [{ zone: 'MLG_L', tone: 'accent' }, { zone: 'MLG_R', tone: 'accent' }], headline: 'Tyre change due', detail: 'Next landing is 8 of 8' },
    TJ106: { zones: [{ zone: 'MLG_L', tone: 'p1' }, { zone: 'MLG_R', tone: 'p1' }], headline: 'Gear unsafe warning', detail: 'Twice in twelve days' },
    TJ107: { zones: [{ zone: 'HYD_PUMP', tone: 'accent' }], headline: 'Alarm that never clears', detail: '34 flights · 28 removals found nothing' },
    TJ108: { zones: [{ zone: 'CHUTE', tone: 'nmcs' }], tone: 'nmcs', headline: 'Waiting for a brake chute', detail: 'Grounded 80 days' }
  };
  const NMC = ['NMCS', 'NMCD', 'NMCM_S', 'NMCM_U'];
  const readiness = () => ({
    asof: D.asof, asof_label: clock.asof, focus: 'TJ107',
    kpi: {
      mc_now: D.fleet.filter(f => !NMC.includes(f.state)).length, of: D.fleet.length,
      mc30: 54.5, fmc30: +(D.kpis.d30.fmc * 100).toFixed(1), norm: 75, parts30: +(D.kpis.d30.tnmcs * 100).toFixed(1),
      due: DEC.board.length, freeze: clock.freeze, alert_rows: DEC.load.alert_rows
    },
    fleet: D.fleet.map(f => ({ ...f, card: CARDS[f.tail] })),
    mc_daily: D.mc_daily, kpis: D.kpis, downtime: D.downtime
  });

  // ---- board
  const BOARD_TXT = {
    'TJ103-LGB-501': { rank: 1, label: 'Gear unsafe warning', why: 'The same warning twice in ten days', act_label: 'TROUBLESHOOT' },
    'TJ106-LGB-501': { rank: 2, label: 'Gear unsafe warning', why: 'The same warning twice in twelve days', act_label: 'TROUBLESHOOT' },
    [TJ107]: { rank: 3, label: 'Hydraulic alarm that never clears', why: '34 flights in a row · 28 pump removals found nothing', act_label: 'STOP R/R · TROUBLESHOOT', auth_shown: 'HUMAN' },
    'TJ108-AOG-CHUTE': { rank: 4, label: 'Waiting for a brake chute', why: 'Grounded 80 days · oldest open AOG demand', act_label: 'EXPEDITE' },
    'TJ105-SPS-501': { rank: 5, label: 'Starter fails to start', why: 'Four times in ten days', act_label: 'TROUBLESHOOT' },
    'TJ105-TYRE': { rank: 6, label: 'Tyre at 7 of 8 landings', why: 'Ordering early changed nothing in 30 paired simulations', act_label: null, order_state: 'dropped', auth_shown: null },
    'P4-ADVISORY': { rank: 7, label: 'Nine advisory codes, grouped', why: 'Almost always closed as could-not-duplicate', act_label: 'MONITOR', order_state: 'monitor', auth_shown: 'AGENT', tail_label: '6 tails' }
  };
  const rows = DEC.board.map(r => ({ order_state: 'proposed', auth_shown: r.auth, tail_label: r.tail, ...r, ...BOARD_TXT[r.id] }))
    .sort((a, b) => a.rank - b.rank);
  const board = () => ({ snapshot: DEC.snapshot, load: { ...DEC.load, days: 168 }, focus: TJ107, code_outcomes: DEC.code_outcomes, board: rows });

  // ---- issue cards (/api/issues/{id})
  const T = DEC.tj107;
  const evRows = T.evidence.map(e => ({ ...e, before_snapshot: true }));
  const fork = PR.chain.find(e => e.type === 'FORK_EVALUATED').payload;
  const ISSUE107 = {
    id: TJ107, tail: 'TJ107', code: 'HYD-101', band: 'P2', title: 'TJ107 · hydraulic alarm HYD-101', standing: 'Standing for 34 flights',
    state: STATE === 'approved' ? 'APPROVED' : 'PROPOSED',
    decision: STATE === 'approved' ? { action: 'APPROVED', by: 'SEO', at: '06:41' } : null,
    reco: { headline: 'Stop removing the pump. Troubleshoot the indication path.', text: 'The hydraulic alarm on TJ107 has outlived 28 pump removals, and the shop found nothing wrong with any of them.' },
    facts: {
      state: { tier: 'DESC', big: '28', unit: 'pump removals', text: 'Ten different pumps through system 1 since 2 March. The aircraft is mission capable today.' },
      why: { tier: 'DIAG', big: '0', unit: 'of 107 confirmed', text: 'No HYD-101 job in the fleet ever confirmed a pump fault. All 33 pumps sent to the shop came back RTOK.' },
      forecast: { tier: 'PRED', big: '98.5', unit: '% no fault found', text: 'if the pump is removed again. Chance this pump is actually faulty: 0.5 %.', ci: '0.985 [0.93, 1.00] · 33 of 33 pumps RTOK' }
    },
    orders: [
      { order_id: TS107, action: 'TROUBLESHOOT', text: 'Indication path on system 1 — pressure switch, harness, BHEEM EU channel', authority: 'AGENT', mode: 'consent', signed_by: null },
      { order_id: CMC107, action: 'CHANGE_MONITORING_CONFIG', text: 'Filter HYD-101 on TJ107 while it is investigated — drafted, not issued', authority: 'HUMAN', mode: 'sign', signed_by: null }
    ],
    impact: {
      horizon_days: 30, pairs: fork.pairs, d_mc: fork.d_mc.map(v => +(v * 100).toFixed(1)), source: SRC.FLEET,
      rows: [{ k: 'Maintenance man-hours', v: '−116' }, { k: 'Days grounded for parts', v: '−3.7' }, { k: 'In-flight failures', v: '+0.07 · not significant', muted: true }]
    },
    evidence: { cited: 63, rows: evRows, order_id: TS107 },
    rule: {
      steps: [
        { h: 'Safety gates — none tripped', p: 'No warning-level code, no grounding defect, no limit due. The issue is scored, not grounded.', hit: false },
        { h: 'Policy P-DEC-01 · row r3', p: 'A code that keeps returning without a confirmed fix for three or more flights is troubleshot.', hit: true, tag: '34 consecutive flights' },
        { h: 'Triage rule D8 · standing alarm', p: 'Five or more flights with two or more no-fault outcomes goes to a human nuisance review.', hit: true, tag: '33 no-fault outcomes on TJ107' }
      ],
      note: 'P-DEC-01 / 1.4.0 · with 2 flights instead of 34, the same rule would only monitor.'
    },
    whynot: [
      { alt: 'REMOVE_REPLACE pump', text: '98.5 % chance the shop finds nothing. Twenty-eight removals have not changed the symptom.', verdict: 'Blocked by evidence' },
      { alt: 'GROUND aircraft', text: 'No warning-level code, and the aircraft is mission capable.', verdict: 'Not justified' },
      { alt: 'DEFER again', text: 'The alarm is standing. Deferring repeats the last 34 flights.', verdict: 'Repeats the loop' },
      { alt: 'Filter the code only', text: 'Hides the alarm without checking the indication path first.', verdict: 'Needs a test first' }
    ],
    donothing: { tail: 'TJ107', horizon_days: 30, status_quo: 63, with_plan: 85, pairs: 30, note: 'The next HYD-101 report would open job number 65 for the same alarm.' },
    workbench: true
  };

  // other board items: the film typed only TJ107, so these cards are built from the board row itself
  function genericIssue(r) {
    const co = DEC.code_outcomes[r.code], ords = DEC.orders.filter(o => o.item === r.id);
    const auth = (r.auth || 'AGENT');
    return {
      id: r.id, tail: r.tail, code: r.code, band: r.band, title: `${r.tail_label} · ${r.label.toLowerCase()}`, standing: r.reason,
      state: 'PROPOSED', decision: null,
      reco: { headline: r.act_label ? `${r.act_label.charAt(0) + r.act_label.slice(1).toLowerCase().replace(/_/g, ' ')} · ${r.code}.` : 'No order today.', text: `${r.why}. ${r.basis}.` },
      facts: {
        state: { tier: 'DESC', big: `C${r.C} · U${r.U}`, unit: 'consequence · urgency', text: `${r.u_basis}.` },
        why: co ? { tier: 'DIAG', big: String(co.confirmed), unit: `of ${co.n} confirmed`, text: `${co.n} fleet jobs on ${r.code}: ${co.cnd} could not duplicate, ${co.rr} removed, ${co.ts} troubleshot.` }
          : { tier: 'DIAG', big: '—', unit: 'no code history', text: r.basis + '.' },
        forecast: r.p ? { tier: 'PRED', big: (r.p.v * 100).toFixed(1), unit: '% confirmed fault', text: `chance that the next job on ${r.code} confirms a fault.`, ci: `${r.p.v} [${r.p.lo}, ${r.p.hi}] · n = ${r.p_n}` }
          : { tier: 'PRED', big: '—', unit: r.p_note || 'not modelled', text: 'No false-alarm model applies to this item.' }
      },
      orders: ords.map(o => ({ order_id: o.order_id, action: o.action, text: WHAT[`${o.item}:${o.action}`] || JSON.stringify(o.parameters), authority: o.issuer_kind || auth, mode: r.mode, signed_by: null })),
      impact: null,
      evidence: { cited: ords[0] ? ords[0].evidence.length : 0, rows: (ords[0] ? ords[0].evidence : []).map(rid => ({ rid, sortie: '', t_occ: '', t_ingest: ords[0].evidence_latest_ingest, before_snapshot: !!ords[0].evidence_all_ingested })), order_id: ords[0] && ords[0].order_id },
      rule: { steps: [{ h: r.basis, p: `Policy ${r.rule} · row ${r.row} → ${r.action}.`, hit: true, tag: r.reason }], note: `${r.rule} · ${r.mode}` },
      whynot: [], donothing: null, workbench: false
    };
  }
  const issue = id => (id === TJ107 ? ISSUE107 : rows.find(r => r.id === id) ? genericIssue(rows.find(r => r.id === id)) : null);

  // ---- workbench (/api/workbench/{issue_id})
  const P = T.post;
  const workbench = id => id !== TJ107 ? null : ({
    issue_id: TJ107, tail: 'TJ107', code: 'HYD-101', title: 'TJ107 · hydraulic alarm HYD-101',
    sub: 'Workbench · is it the pump, and what should we test next?', manual: 'PHX-FIM-HYD', t0: D.tj107.t0,
    sorties: WB.sorties, removals: WB.removals,
    strip: { title: 'The alarm follows the aircraft, not the pump', ci: 'HYD-101 fired, whichever pump was fitted', note: 'Each band is one pump serial in system 1 · ten serials since January' },
    suspects: [
      { id: 'IND', name: 'Indication path', text: 'Pressure switch · harness · EU channel', p: P.IND },
      { id: 'AMAGB', name: 'AMAGB drive', text: 'Gearbox drive to the pump', p: P.AMAGB },
      { id: 'HYD_PUMP', name: 'Hydraulic pump', text: 'Ruled out in every assumption tested', p: P.HYD_PUMP }
    ],
    suspects_note: 'Central assumptions · 24 assumption settings swept', source: SRC.FLEET,
    tests: [
      { test_id: 'IND_PATH_ISOLATION', name: 'Indication-path isolation', text: 'BHEEM EU channel · pressure switch · harness · PHX-FIM-HYD', man_h: 7.3, value: 1, robust: 'best in 19 of 24' },
      { test_id: 'AMAGB_DRIVE_CHECK', name: 'AMAGB drive check', text: 'Pad spline · oil · drive to the system 1 pump', man_h: 8.3, value: 0.91, robust: 'best in 5 of 24' },
      { test_id: 'PUMP_REMOVE', name: 'Remove the pump again', text: "Today's habit · bench test of the removed unit", man_h: 18.7, value: 0, robust: 'tells us nothing new' }
    ]
  });

  // ---- twin (/api/twin/{tail})
  const LRU_NODE = { BHEEM_EU: 'BHEEM_EU', FADEC: 'FADEC', INGPS: 'INGPS', AHRS: 'AHRS', RADAR: 'RADAR', ADC: 'ADC', DFCC: 'DFCC' };
  const CODE_NODE = { 'HYD-101': 'HYD_PUMP', 'LGB-501': 'MLG_L', 'SPS-501': 'JFS', 'SYN-PN-CHUTE': 'CHUTE', 'SYN-PN-TYRE': 'MLG_L' };
  const TONE_HEX = { p1: '#D4492A', accent: '#E8743B', nmcs: '#D4492A', nmcm: '#C98512', nmcd: '#5B4FCF' };
  const SYSTEMS = (tail, f) => [
    { id: 'ENG', name: 'Engine & FADEC', tone: 'ink-5', items: [{ node: 'ENGINE', label: 'F404 engine', serial: `IN20-${tail}` }, { node: 'FADEC', label: 'FADEC', serial: null }, { node: 'JFS', label: 'JFS starter', serial: null }] },
    { id: 'HYD', name: 'Hydraulics', items: [{ node: 'HYD_PUMP', label: 'Pump 1 · SYS1', serial: null }, { node: 'HYD_PUMP2', label: 'Pump 2 · SYS2', serial: null }, { node: 'AMAGB', label: 'AMAGB', serial: null }, { node: null, label: 'Filter · SYS1', serial: null }] },
    { id: 'AVI', name: 'Avionics', items: [{ node: 'BHEEM_EU', label: 'BHEEM EU', serial: null }, { node: 'DFCC', label: 'DFCC', serial: null }, { node: 'INGPS', label: 'INS/GPS', serial: null }, { node: 'AHRS', label: 'AHRS', serial: null }, { node: 'RADAR', label: 'Radar', serial: null }] },
    { id: 'ADC', name: 'Air data', items: [{ node: 'ADC', label: 'ADC', serial: null }] },
    { id: 'LG', name: 'Landing gear', count: f ? `${f.tyre_ldg}/8` : null, items: [{ node: 'NLG', label: 'Nose gear', serial: null }, { node: 'MLG_L', label: 'Main gear L', serial: null }, { node: 'MLG_R', label: 'Main gear R', serial: null }, { node: 'CHUTE', label: 'Brake chute', serial: null }] },
    { id: 'ELE', name: 'Electrical', items: [] }, { id: 'FUE', name: 'Fuel', items: [{ node: 'FUEL_F1', label: 'Fuel F1', serial: null }] }, { id: 'FCS', name: 'Flight controls', items: [] }
  ];
  const lensCommon = (tail, f, issues) => {
    const life = f ? f.tyre_ldg / 8 : 0;
    return [
      { id: 'status', label: 'Status', icon: 'target', source: SRC.FLEET, model: 'twin state',
        paint: Object.fromEntries((CARDS[tail].zones || []).map(z => [z.zone, TONE_HEX[z.tone]])),
        legend: [{ kind: 'dot', color: '#E8743B', text: 'Open issue' }, { kind: 'dot', color: '#D4492A', text: 'Warning or waiting for part' }, { kind: 'text', text: 'from the latest availability and job records' }] },
      { id: 'false_alarm', label: 'False alarm', icon: 'scale', source: SRC.FLEET, model: 'cnd base rate 2.3.0',
        paint: Object.fromEntries(issues.filter(r => r.p && CODE_NODE[r.code]).map(r => [CODE_NODE[r.code], +r.p.v < 0.05 ? '#9AA0A8' : '#E8743B'])),
        tags: issues.filter(r => r.p && CODE_NODE[r.code]).map(r => ({ node: CODE_NODE[r.code], kind: 'rep', k: `False alarm · ${r.code}`, v: `P(confirmed) ${r.p.v}`, s: `[${r.p.lo}, ${r.p.hi}] · n = ${r.p_n}` })),
        legend: [{ kind: 'dot', color: '#9AA0A8', text: 'P(confirmed) < 0.05 · likely nuisance' }, { kind: 'dot', color: '#E8743B', text: '≥ 0.05' }] },
      { id: 'life', label: 'Life left', icon: 'tyre', source: SRC.FLEET, model: 'life 1.0',
        paint: f ? { MLG_L: life >= 0.85 ? '#D4492A' : life >= 0.6 ? '#C98512' : '#1F8A4C', MLG_R: life >= 0.85 ? '#D4492A' : life >= 0.6 ? '#C98512' : '#1F8A4C' } : {},
        tags: f ? [{ node: 'MLG_R', kind: 'rep', k: 'Life · tyres', v: `${f.tyre_ldg} of 8 landings`, s: `${8 - f.tyre_ldg} landings left` }] : [],
        legend: [{ kind: 'dot', color: '#1F8A4C', text: '< 60 % used' }, { kind: 'dot', color: '#C98512', text: '60–85 %' }, { kind: 'dot', color: '#D4492A', text: '> 85 %' }] },
      { id: 'removal_risk', label: 'Removal risk', icon: 'wrench', source: SRC.TRAIN, model: 'hazard (Weibull)', paint: {}, tags: [],
        legend: [{ kind: 'text', text: 'INSUFFICIENT_EVIDENCE · the film data has no confirmed removals to fit' }] },
      { id: 'engine_margin', label: 'Engine margin', icon: 'engine', source: SRC.OVERLAY, model: 'engine health (Kalman)', paint: {}, tags: [],
        legend: [{ kind: 'text', text: 'No engine trend in the film data' }] }
    ];
  };
  function twin(tail) {
    const f = D.fleet.find(x => x.tail === tail); if (!f) return null;
    const issues = rows.filter(r => r.tail === tail);
    const common = lensCommon(tail, f, issues);
    const evid = {
      id: 'evidence', label: 'Evidence', icon: 'link', source: SRC.FLEET, model: 'isolation 1.0',
      reporter: 'BHEEM_EU', paint: { BHEEM_EU: 'reporter' }, dim: true, arcs: [], tags: [],
      legend: [{ kind: 'dot', color: 'var(--wire)', text: 'Reporter' }, { kind: 'bar', color: 'var(--accent)', text: 'Suspect' }, { kind: 'text', text: 'thickness = isolation confidence' }]
    };
    issues.forEach(r => { const n = CODE_NODE[r.code]; if (n) { evid.paint[n] = 'suspect'; evid.arcs.push({ from: 'BHEEM_EU', to: n, weight: 0.8 }); evid.tags.push({ node: n, kind: 'sus', k: `Suspect · ${r.code}`, v: r.label, s: r.why }); } });
    if (!issues.length) { evid.reporter = null; evid.paint = {}; evid.legend = [{ kind: 'text', text: 'No open issue with alarm evidence on this tail' }]; }
    const systems = SYSTEMS(tail, f);
    issues.forEach(r => { const n = CODE_NODE[r.code]; const s = systems.find(sy => sy.items.some(i => i.node === n)); if (s) s.tone = 'accent'; });
    const sel = issues.map(r => CODE_NODE[r.code]).find(Boolean) || 'ENGINE';
    const base = {
      tail, status: f.state, asof: D.asof, asof_label: clock.asof, last_ingest: f.last_ingest,
      usage: { sorties: null, fh: f.fh_total, landings: null, sorties_30d: f.sorties30, fh_30d: f.fh30 }, snapshot: { at: '06:00 IST', id: DEC.snapshot.hash },
      systems, selected: sel, lens: 'status', lenses: [common[0], evid, ...common.slice(1)], insight: null, panels: {}, strip: null,
      foot: [`snapshot 06:00 · ${DEC.snapshot.hash.slice(0, 8)}…`, 'contract a4396f1d · dictionary tejas 0.1.3']
    };
    if (tail !== 'TJ107') return base;
    // TJ107: the film's twin page
    Object.assign(base, {
      usage: { sorties: 61, fh: 49.6, landings: 116, sorties_30d: f.sorties30, fh_30d: f.fh30 }, selected: 'HYD_PUMP', lens: 'evidence',
      insight: { label: 'Sensor vs component', title: 'The alarm stayed with the aircraft through 28 pump removals.', text: 'HYD-101 fired on 59 of 61 TJ107 sorties while 10 different pump serials rotated through SYS1. The evidence follows the tail, not the pump.', swaps: D.tj107.sorties.map(s => !!s[1]) },
      strip: { t0: D.tj107.t0, T: D.tj107.T, state: D.tj107.state, sorties: D.tj107.sorties, removals: D.tj107.removals, marks: [{ day: D.tj107.T - 32, label: '21 May' }], asof_label: '22 Jun 06:00', labels: { sorties: 'Sorties · HYD-101', removals: 'Pump removals' } }
    });
    const S = base.systems;
    S[0].items = [{ node: 'ENGINE', label: 'F404 engine', serial: 'IN20-TJ107' }, { node: 'FADEC', label: 'FADEC', serial: null }, { node: 'JFS', label: 'JFS starter', serial: null }];
    S[1] = { id: 'HYD', name: 'Hydraulics', tone: 'accent', open: true, items: [{ node: 'HYD_PUMP', label: 'Pump 1 · SYS1', serial: 'HYDP-000010' }, { node: 'HYD_PUMP2', label: 'Pump 2 · SYS2', serial: 'HYDP-000002' }, { node: 'AMAGB', label: 'AMAGB', serial: 'AMAGB-000001' }, { node: null, label: 'Filter · SYS1', serial: null }] };
    S[2].count = '3'; S[3].count = '1'; S[0].tone = 'ink-5';
    base.lenses[0].paint = { HYD_PUMP: '#C98512', MLG_L: '#E8A17C', MLG_R: '#E8A17C', INGPS: '#C7C9CC', RADAR: '#C7C9CC', ENGINE: '#B9D9C6' };
    base.lenses[1] = {
      id: 'evidence', label: 'Evidence', icon: 'link', source: SRC.FLEET, model: 'isolation 1.0', reporter: 'BHEEM_EU', dim: true,
      paint: { BHEEM_EU: 'reporter', HYD_PUMP: 'suspect', AMAGB: 'suspect2' },
      arcs: [{ from: 'BHEEM_EU', to: 'HYD_PUMP', weight: 0.8 }, { from: 'BHEEM_EU', to: 'AMAGB', weight: 0.2 }],
      tags: [
        { node: 'BHEEM_EU', kind: 'rep', k: 'Reporter', v: 'BHEEM EU', s: 'HYD-101 · 59 of 61 sorties', dx: -40, dy: -150 },
        { node: 'HYD_PUMP', kind: 'sus', k: 'Suspect · 0.8', v: 'Hyd pump 1 · HYDP-000010', s: '28 removals · 10 pumps · 0 confirmed', dx: 210, dy: -60 },
        { node: 'AMAGB', kind: 'sus2', k: 'Suspect · 0.2', v: 'AMAGB', s: 'no removals', dx: 170, dy: 110 }
      ],
      legend: [{ kind: 'dot', color: 'var(--wire)', text: 'Reporter' }, { kind: 'bar', color: 'var(--accent)', text: 'Suspect · isolation 0.8' }, { kind: 'line', color: '#C98512', text: '0.2' }, { kind: 'text', text: 'thickness = isolation confidence' }]
    };
    base.panels.HYD_PUMP = {
      title: 'Hydraulic pump 1 · SYS1', serial: 'HYDP-000010', inferred: true, note: 'Install record not yet ingested — position from job sulur-26169-0006 (19 Jun)',
      tiers: ['DIAG', 'PRED', 'PRESC'],
      status: { pill: 'FMC', kv: [{ k: 'Open issue', code: 'HYD-101', v: 'standing · 34 flights' }, { k: 'TJ107 effort on HYD-101', v: '64 jobs · 792 man-h', num: true }] },
      assessment: {
        scope: 'fleet · 107 HYD-101 jobs', confirmed: '0 confirmed',
        bar: [{ n: 71, tone: 'ink-4', label: '71 CND' }, { n: 35, tone: 'accent', label: '35 removed → all RTOK' }, { n: 1, tone: 'ink', label: '1 TS' }],
        kv: [{ k: 'P(confirmed pump fault)', v: '0.005', ci: '[0.000, 0.023]' }],
        verdict: [{ label: 'Component', value: 'Unlikely' }, { label: 'Indication path', value: 'Likely', on: true }, { label: 'Undetermined', value: '—' }]
      },
      projection: { kv: [{ k: 'If removed again · P(RTOK)', v: '0.985', ci: '[0.93, 1.00]' }, { k: 'Shop history, pumps', v: '33 / 33 RTOK', num: true }] },
      recommended: { basis: 'P-DEC-01 r3 · D8 nuisance review', items: [
        { action: 'Stop R/R on HYD-101 alone', authority: 'AGENT', label: 'MONITOR' },
        { action: 'TROUBLESHOOT indication path', authority: 'AGENT', label: 'AGENT', icon: true },
        { action: 'CHANGE_MONITORING_CONFIG', authority: 'HUMAN', label: 'HUMAN', icon: true, note: 'Draft only · engineering officer signs' }] },
      foot: ['snapshot 06:00 · 2c2d0f5b… · nff base rate 2.3.0 @champion', 'policy P-DEC-01/1.4.0+jdm.c9b849a8e719 · contract a4396f1d']
    };
    return base;
  }

  // ---- serial lineage (/api/serial/{tail}/{serial}); the film has the TJ107 system-1 pump swaps
  const day = d => { const t = new Date(Date.parse(D.tj107.t0 + 'T00:00:00Z') + d * 864e5); return t.toUTCString().slice(5, 11); };
  function serial(tail, sn) {
    if (tail !== 'TJ107' || !/^HYDP-/.test(sn)) return null;  // the film has the system-1 pump swaps of TJ107 only
    const hist = [];
    WB.removals.forEach(([d, out, inn]) => {
      if (inn === sn) hist.push({ tail: 'TJ107', position: 'HYD_PUMP · SYS1', installed: day(d), removed: null, job_no: null, finding: null });
      if (out === sn) { const h = hist.filter(x => x.removed === null).pop() || (hist.push({ tail: 'TJ107', position: 'HYD_PUMP · SYS1', installed: null, removed: null, job_no: null, finding: null }), hist[hist.length - 1]); h.removed = day(d); h.finding = 'RTOK'; }
    });
    return {
      tail: 'TJ107', serial: sn, part_no: 'SYN-PN-HYDP', klass: 'Hydraulic pump', asof: D.asof, history: hist,
      hours_since_install: null, cycles_since_install: null,
      beliefs: [{ name: 'p_confirmed', value: 0.005, lo: 0.0, hi: 0.023, n: 107, model_id: 'cnd', model_version: '2.3.0', source: SRC.FLEET },
        { name: 'p_rtok_if_removed', value: 0.985, lo: 0.93, hi: 1.0, n: 33, model_id: 'cnd', model_version: '2.3.0', source: SRC.FLEET },
        { name: 'removal_risk_30d', value: null, model_id: 'hazard', model_version: '', source: SRC.TRAIN, note: 'INSUFFICIENT_EVIDENCE' }]
    };
  }

  // ---- search (/api/search?q=)
  function search(q) {
    const s = String(q || '').trim().toUpperCase(); if (!s) return { q, results: [] };
    const out = [];
    D.fleet.filter(f => f.tail.includes(s)).forEach(f => out.push({ kind: 'tail', id: f.tail, label: f.tail, sub: f.state, tail: f.tail }));
    [...new Set(WB.sorties.map(x => x[2]))].filter(x => x.includes(s)).forEach(x => out.push({ kind: 'serial', id: x, label: x, sub: 'TJ107', tail: 'TJ107' }));
    Object.entries(D.triage.code_desc).filter(([c, v]) => c.includes(s) || v.description.toUpperCase().includes(s))
      .forEach(([c, v]) => { const r = rows.find(x => x.code === c); out.push({ kind: 'code', id: c, label: c, sub: v.description, tail: r ? r.tail : null, issue_id: r ? r.id : null }); });
    rows.filter(r => r.params && r.params.demand_no && r.params.demand_no.toUpperCase().includes(s))
      .forEach(r => out.push({ kind: 'job', id: r.params.demand_no, label: r.params.demand_no, sub: r.label, tail: r.tail, issue_id: r.id }));
    return { q, results: out.slice(0, 12) };
  }

  // ---- provenance (/api/provenance/{order_id}); the film has the chain of the TJ107 troubleshoot order
  function provenance(oid) {
    if (oid !== PR.order_id) return null;
    const E = PR.chain, p = i => E[i].payload, rf = i => E[i].refs, ev6 = rf(3).record_ids;
    const TXT = [
      ['Release adopted', `Release v0.9 · manifest ${rf(0).release_id.slice(0, 8)} · contract 0.2.0 · dictionary 0.1.3`],
      ['Batch admitted', `Checksum, schema and content checks passed · sha256 ${rf(1).file_sha256.slice(0, 8)}`],
      ['Snapshot sealed', `Everything ingested by 06:00 · ${Object.values(p(2).records).reduce((a, b) => a + b, 0).toLocaleString('en-GB')} records · hash ${rf(2).snapshot_hash.slice(0, 8)}`],
      ['Evidence linked', `6 HYD-101 events, all ingested before 06:00 · latest <span class="rid2">${ev6[5].slice(0, 12)}</span>`],
      ['Finding', `HYD-101: ${p(4).nofault.replace('/', ' of ')} jobs no-fault, 0 confirmed · model 2.3.0`],
      ['Issue triaged', `P2 · standing ${p(5).consec_flights} flights → nuisance review for the engineering owner`],
      ['Policy evaluated', `P-DEC-01 row ${p(6).matched} → ${p(6).result.action} · version jdm.${rf(6).policy_version.split('jdm.')[1]}`],
      ['Fork evaluated', `${p(7).pairs} CRN pairs · mission capable +${p(7).d_mc[0].toFixed(2)} [${p(7).d_mc[1].toFixed(2)}, ${p(7).d_mc[2].toFixed(2)}] vs status quo`],
      ['Recommendation proposed', 'TROUBLESHOOT HYD-101 on TJ107 · consent required before 07:45'],
      ['Approved', 'Senior Engineering Officer · approved as recommended'],
      ['Order accepted', 'Issued by the agent at 08:00 · gateway verdict ACCEPTED'],
      ['Status queued', 'Mirrored from orders.status · waiting for the job to open'],
      ['Outcome pending', 'Label waits for the job close and any shop finding']
    ];
    const board = STATE === 'board';
    return {
      ...PR, verified: true,
      chain: E.map((e, i) => ({ ...e, title: TXT[i][0], text: TXT[i][1], scheduled: board && e.t_valid.slice(11, 16) === '08:00' })),
      standards: [
        { std: 'EASA DA-04', text: 'Traceable from origin', events: 'events 1–4' }, { std: 'EASA CM-01', text: 'Versioned by hash', events: 'events 5–7' },
        { std: 'EASA EXP-09', text: 'Explained after the fact', events: 'this chain' }, { std: 'EASA QA-01', text: 'Independent sign-off', events: 'event 10' },
        { std: 'DRDO ETAI', text: 'Transparent and replayable', events: 'replay' }, { std: 'NIST · DoD', text: 'Measured and logged', events: 'drift' }
      ]
    };
  }

  // the early moment: same fleet, nothing triaged yet (tests the empty states of every page)
  if (EARLY) {
    const e0 = epoch, b0 = board, p0 = provenance;
    window.PHX_FILM = {
      epoch: () => ({ ...e0(), clock: { ...clock, now: '06:05', due: 0, phase: 'BOARD_OPEN', engines: null },
        timeline: STEPS.map((x, i) => ({ ...x, state: i === 0 ? 'done' : i === 1 ? 'now' : 'next' })), orders: [], signatures: [], log_summary: [] }),
      readiness: () => ({ ...readiness(), focus: null, kpi: { ...readiness().kpi, due: 0 } }),
      board: () => ({ ...b0(), board: [], focus: null, load: { ...DEC.load, open: 33, items: 0, days: 168 } }),
      issue: () => null, workbench: () => null, twin, serial, search,
      provenance: oid => { const r = p0(oid); return r && { ...r, chain: r.chain.slice(0, 3), replay: [], standards: [], verified: false }; }
    };
    return;
  }
  window.PHX_FILM = { epoch, readiness, board, issue, workbench, twin, serial, search, provenance };
})();
