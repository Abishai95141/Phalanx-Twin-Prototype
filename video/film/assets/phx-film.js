/* PHX film helpers for HyperFrames director compositions (deterministic; no clocks, no rAF). */
(function () {
  const $ = (s, r = document) => r.querySelector(s);
  // measure an element's centre in stage coordinates (call BEFORE any camera tween is applied)
  function box(el) {
    if (typeof el === 'string') el = $(el);
    const r = el.getBoundingClientRect();
    return { x: r.left, y: r.top, w: r.width, h: r.height, cx: r.left + r.width / 2, cy: r.top + r.height / 2 };
  }
  // camera transform that centres box b at scale s (wrapper uses transform-origin 0 0), clamped to the stage
  function camTo(b, s, opts = {}) {
    const fx = opts.fx ?? 960, fy = opts.fy ?? 540;
    let x = fx - b.cx * s, y = fy - b.cy * s;
    if (opts.clamp !== false) { x = Math.min(0, Math.max(1920 - 1920 * s, x)); y = Math.min(0, Math.max(1080 - 1080 * s, y)); }
    return { scale: s, x, y };
  }
  // count-up text on a timeline
  function count(tl, el, from, to, at, dur, fmt = v => v.toFixed(0), ease = 'power2.out') {
    if (typeof el === 'string') el = $(el);
    const o = { v: from };
    tl.fromTo(o, { v: from }, { v: to, duration: dur, ease, onUpdate: () => { el.textContent = fmt(o.v); } }, at);
  }
  // typewriter into an element (textContent) or input (value)
  function type(tl, el, text, at, dur) {
    if (typeof el === 'string') el = $(el);
    const o = { n: 0 }, isInput = 'value' in el && el.tagName !== 'DIV';
    tl.fromTo(o, { n: 0 }, { n: text.length, duration: dur, ease: 'none', onUpdate: () => {
      const s = text.slice(0, Math.round(o.n)); if (isInput) el.value = s; else el.textContent = s; } }, at);
  }
  // SVG stroke draw-on for every path/line/polyline in a node list
  function draw(tl, sel, at, dur, stagger = 0, ease = 'power2.inOut') {
    const els = typeof sel === 'string' ? document.querySelectorAll(sel) : sel;
    els.forEach((p, i) => {
      const L = p.getTotalLength ? p.getTotalLength() : 1000;
      p.style.strokeDasharray = L; p.style.strokeDashoffset = L;
      tl.fromTo(p, { strokeDashoffset: L }, { strokeDashoffset: 0, duration: dur, ease }, at + i * stagger);
    });
  }
  // live 3D twin inside a frozen screen's viewport
  // slot: element to host the canvas; labels: [{id, dx, dy, color, anchor:'#..', label:'#..'}]; leaders: svg element
  function mountTwin(slot, opts = {}, labels = [], leaders = null) {
    if (typeof slot === 'string') slot = $(slot);
    const twin = window.PHX_TWIN.createTwin(slot, Object.assign({ dpr: 2 }, opts, {
      onFrame(screenOf) {
        let svg = '';
        labels.forEach(l => {
          const [x, y] = screenOf(l.id), a = $(l.anchor), b = $(l.label);
          if (a) { a.style.left = x + 'px'; a.style.top = y + 'px'; }
          if (b) { b.style.left = (x + l.dx) + 'px'; b.style.top = (y + l.dy) + 'px'; }
          svg += `<path d="M${x} ${y} L${x + l.dx * .55} ${y + l.dy} L${x + l.dx} ${y + l.dy}" fill="none" stroke="${l.color}" stroke-width="1.4" opacity=".9"/>`;
        });
        if (leaders) { (typeof leaders === 'string' ? $(leaders) : leaders).innerHTML = svg; }
      }
    }));
    const c = slot.querySelector('canvas'); if (c) c.style.zIndex = 1;
    return twin;
  }
  // drive a twin from the timeline: renderAt(local time) on every seek
  function driveTwin(tl, twin, at, dur, extra) {
    const o = { t: 0 };
    tl.fromTo(o, { t: 0 }, { t: dur, duration: dur, ease: 'none', onUpdate: () => { if (extra) extra(o.t); twin.renderAt(o.t); } }, at);
    twin.renderAt(0);
  }
  // macOS-style cursor
  const CURSOR = '<svg viewBox="0 0 28 28" width="34" height="34"><path d="M5 3.5l15.5 13.2-7.2.6 4.3 8.4-3.3 1.6-4.3-8.5-5 5.2z" fill="#0B0D10" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  window.PHXF = { $, box, camTo, count, type, draw, mountTwin, driveTwin, CURSOR };
})();
