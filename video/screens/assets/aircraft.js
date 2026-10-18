/* Parametric delta-wing fighter drawings (synthetic schematic, metres).
   x = station from nose (0 → 13.2 m), y = buttline (± 4.1 m), z = waterline.
   Used for fleet-card silhouettes, the 2D twin schematic and blueprint plates. */
(function () {
  // right half of the planform, nose → tail, clockwise
  const HALF = [
    [0.00, 0.00], [0.35, 0.05], [0.9, 0.22], [1.6, 0.36], [2.3, 0.45], [3.0, 0.52], [3.7, 0.62],
    [4.05, 0.98], [4.6, 1.02],          // intake lip, wing-root leading edge
    [7.29, 2.40],                        // crank (inner LE sweep 62.5°)
    [9.32, 4.10], [10.72, 4.10],         // tip (outer LE sweep 50°), tip chord
    [11.22, 1.02],                       // trailing edge root
    [11.9, 0.80], [12.55, 0.58], [12.62, 0.50], [13.2, 0.44], [13.2, 0.0]
  ];
  const ELEVON = [[10.72, 4.04], [10.98, 2.45], [11.14, 1.35]];
  const CANOPY = { x0: 2.55, x1: 4.55, w: 0.34 };

  // component zones in plan (x0, x1, y, r) — schematic placement
  const ZONES = {
    RADAR:   { x: 1.05, y: 0, r: 0.42, label: 'Radar' },
    DFCC:    { x: 4.9, y: 0, r: 0.34, label: 'DFCC' },
    BHEEM_EU:{ x: 5.6, y: -0.38, r: 0.26, label: 'BHEEM EU' },
    ADC:     { x: 2.2, y: 0.25, r: 0.22, label: 'ADC' },
    INGPS:   { x: 5.2, y: 0.4, r: 0.24, label: 'INS/GPS' },
    AMAGB:   { x: 7.25, y: 0, r: 0.32, label: 'AMAGB' },
    HYD_PUMP:{ x: 7.55, y: 0.42, r: 0.24, label: 'Hyd pump 1' },
    HYD_PUMP2:{ x: 7.55, y: -0.42, r: 0.24, label: 'Hyd pump 2' },
    MLG_L:   { x: 8.25, y: -1.42, r: 0.36, label: 'MLG tyre L' },
    MLG_R:   { x: 8.25, y: 1.42, r: 0.36, label: 'MLG tyre R' },
    NLG:     { x: 3.55, y: 0, r: 0.26, label: 'NLG' },
    ENGINE:  { x: 10.1, y: 0, r: 0.5, label: 'F404 engine' },
    FADEC:   { x: 9.0, y: -0.3, r: 0.22, label: 'FADEC' },
    CHUTE:   { x: 12.75, y: 0, r: 0.24, label: 'Brake chute' },
    JFS:     { x: 8.6, y: 0.36, r: 0.22, label: 'JFS' },
    AHRS:    { x: 4.35, y: -0.36, r: 0.2, label: 'AHRS' }
  };

  const ring = () => HALF.concat(HALF.slice(1, -1).reverse().map(([x, y]) => [x, -y]));

  // nose up: screen X = buttline, screen Y = station
  function planform(opts = {}) {
    const s = opts.scale || 10, pad = opts.pad || 4;
    const W = 8.2 * s + pad * 2, H = 13.2 * s + pad * 2;
    const P = ([x, y]) => `${(pad + (4.1 + y) * s).toFixed(1)},${(pad + x * s).toFixed(1)}`;
    const outline = 'M' + ring().map(P).join('L') + 'Z';
    const elevR = 'M' + ELEVON.map(P).join('L');
    const elevL = 'M' + ELEVON.map(([x, y]) => P([x, -y])).join('L');
    const c = CANOPY, cx = pad + 4.1 * s, cy = pad + (c.x0 + c.x1) / 2 * s;
    const fill = opts.fill || 'var(--bg-2)', stroke = opts.stroke || 'var(--ink-4)', sw = opts.sw || 1.1;
    const marks = (opts.highlight || []).map(h => {
      const z = ZONES[h.zone]; if (!z) return '';
      const zx = pad + (4.1 + z.y) * s, zy = pad + z.x * s, r = (h.r || Math.max(z.r, .36)) * s;
      return `<circle cx="${zx}" cy="${zy}" r="${r * 1.9}" fill="${h.color}" opacity=".14"/>
              <circle cx="${zx}" cy="${zy}" r="${r}" fill="${h.color}" stroke="#fff" stroke-width="${Math.max(1, s / 10)}"/>`;
    }).join('');
    const spine = opts.detail ? `<path d="M${cx},${pad + 0.4 * s}V${pad + 13.1 * s}" stroke="${stroke}" stroke-width=".6" stroke-dasharray="2 3" opacity=".6"/>
      <path d="${elevR}" fill="none" stroke="${stroke}" stroke-width=".7" opacity=".8"/><path d="${elevL}" fill="none" stroke="${stroke}" stroke-width=".7" opacity=".8"/>` : '';
    return `<svg viewBox="0 0 ${W} ${H}" width="${opts.w || W}" height="${opts.h || H}" class="${opts.cls || ''}" aria-hidden="true">
      <path d="${outline}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" stroke-linejoin="round"/>
      ${spine}
      <ellipse cx="${cx}" cy="${cy}" rx="${c.w * s}" ry="${(c.x1 - c.x0) / 2 * s}" fill="${opts.canopy || 'var(--line)'}" stroke="${stroke}" stroke-width="${sw * .7}"/>
      ${marks}
    </svg>`;
  }

  // side profile (nose left), z up — for the schematic and blueprint plates
  const SIDE_TOP = [[0, 0.95], [0.6, 1.02], [1.6, 1.28], [2.4, 1.48], [2.7, 1.62], [3.3, 2.05], [4.2, 2.12], [4.8, 1.9],
    [6.0, 1.82], [8.6, 1.84], [9.4, 2.4], [11.25, 4.35], [12.2, 4.38], [12.7, 2.15], [13.2, 1.86]];
  const SIDE_BOT = [[13.2, 1.18], [12.6, 1.08], [11.4, 0.92], [9.0, 0.78], [6.0, 0.70], [4.4, 0.62], [3.9, 0.74], [2.4, 0.82], [1.2, 0.86], [0, 0.95]];
  function side(opts = {}) {
    const s = opts.scale || 10, pad = opts.pad || 6, H = 4.6 * s + pad * 2, W = 13.2 * s + pad * 2;
    const P = ([x, z]) => `${(pad + x * s).toFixed(1)},${(pad + (4.6 - z) * s).toFixed(1)}`;
    const d = 'M' + SIDE_TOP.concat(SIDE_BOT).map(P).join('L') + 'Z';
    const stroke = opts.stroke || 'var(--ink-4)', fill = opts.fill || 'var(--bg-2)';
    const can = `M${P([2.62, 1.6])}C${P([3.0, 2.38])} ${P([3.9, 2.4])} ${P([4.75, 1.92])}`;
    const intake = `M${P([4.05, 0.72])}L${P([4.05, 1.32])}L${P([4.7, 1.36])}L${P([5.8, 0.98])}Z`;
    const wing = `M${P([4.6, 1.18])}L${P([11.22, 1.12])}`;
    return `<svg viewBox="0 0 ${W} ${H}" width="${opts.w || W}" height="${opts.h || H}" aria-hidden="true">
      <path d="${d}" fill="${fill}" stroke="${stroke}" stroke-width="${opts.sw || 1.1}" stroke-linejoin="round"/>
      <path d="${can}" fill="none" stroke="${stroke}" stroke-width="${(opts.sw || 1.1) * .8}"/>
      <path d="${intake}" fill="none" stroke="${stroke}" stroke-width=".8" opacity=".8"/>
      <path d="${wing}" stroke="${stroke}" stroke-width=".7" stroke-dasharray="3 3" opacity=".7"/>
    </svg>`;
  }

  window.PHX_AC = { planform, side, ZONES, HALF, SIDE_TOP, SIDE_BOT, CANOPY, ring };
})();
