// PHALANX TWIN — 3D twin viewport (three.js r186).
// A stylised, segmented delta-wing airframe (schematic placement) with named component nodes.
// Every colour/line is driven by a lens state object; renderAt(t) is a pure function of time
// so the same scene can be rendered frame-exactly for film.
import * as THREE from 'three';
import { LineSegments2 } from 'three/addons/LineSegments2.js';
import { LineSegmentsGeometry } from 'three/addons/LineSegmentsGeometry.js';
import { LineMaterial } from 'three/addons/LineMaterial.js';
import { Line2 } from 'three/addons/Line2.js';
import { LineGeometry } from 'three/addons/LineGeometry.js';

const ST = s => 6.6 - s;          // station (m from nose) → world x
const WL = w => w - 1.3;          // waterline → world y

// fuselage tables (station → half-width / top / bottom), synthetic schematic
const HW = [[0, .02], [.35, .06], [.9, .22], [1.6, .36], [2.3, .45], [3.0, .52], [3.7, .62], [4.05, .9], [4.6, .98], [6.0, 1.0], [7.6, .95], [9.0, .86], [11.2, .76], [11.9, .7], [12.55, .58], [13.2, .45]];
const TOP = [[0, .95], [.6, 1.02], [1.6, 1.26], [2.4, 1.46], [3.3, 1.6], [4.6, 1.74], [6.0, 1.8], [8.6, 1.83], [11.0, 1.8], [12.2, 1.7], [13.2, 1.6]];
const BOT = [[0, .95], [1.2, .86], [2.4, .8], [3.9, .72], [4.4, .62], [6.0, .66], [9.0, .76], [11.4, .9], [12.6, 1.06], [13.2, 1.14]];
const lerpT = (tab, s) => { for (let i = 1; i < tab.length; i++) if (s <= tab[i][0]) { const [a, va] = tab[i - 1], [b, vb] = tab[i]; const k = (s - a) / (b - a); return va + (vb - va) * k; } return tab[tab.length - 1][1]; };

function loft() {
  const N = 48, stations = []; for (let s = 0; s <= 13.2001; s += 0.12) stations.push(Math.min(s, 13.2));
  const pos = [], idx = [], ex = 2.5;
  stations.forEach(s => {
    const w = lerpT(HW, s), t = lerpT(TOP, s), b = lerpT(BOT, s), yc = (t + b) / 2, a = (t - b) / 2;
    for (let j = 0; j < N; j++) {
      const th = j / N * Math.PI * 2, sn = Math.sin(th), cs = Math.cos(th);
      const py = yc + a * Math.sign(sn) * Math.pow(Math.abs(sn), 2 / ex);
      const pz = w * Math.sign(cs) * Math.pow(Math.abs(cs), 2 / ex);
      pos.push(ST(s), WL(py), pz);
    }
  });
  for (let i = 0; i < stations.length - 1; i++) for (let j = 0; j < N; j++) {
    const a = i * N + j, b = i * N + (j + 1) % N, c = (i + 1) * N + j, d = (i + 1) * N + (j + 1) % N;
    idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setIndex(idx); g.computeVertexNormals();
  return g;
}
function frameRing(s, N = 72) {
  const w = lerpT(HW, s), t = lerpT(TOP, s), b = lerpT(BOT, s), yc = (t + b) / 2, a = (t - b) / 2, ex = 2.5, pts = [];
  for (let j = 0; j <= N; j++) { const th = j / N * Math.PI * 2, sn = Math.sin(th), cs = Math.cos(th);
    pts.push(ST(s), WL(yc + a * Math.sign(sn) * Math.pow(Math.abs(sn), 2 / ex)), w * 1.002 * Math.sign(cs) * Math.pow(Math.abs(cs), 2 / ex)); }
  return pts;
}
function plate(points, depth, bevel = 0.02) {
  const sh = new THREE.Shape(points.map(([u, v]) => new THREE.Vector2(u, v)));
  return new THREE.ExtrudeGeometry(sh, { depth, bevelEnabled: true, bevelThickness: bevel, bevelSize: bevel, bevelSegments: 2, curveSegments: 4 });
}

// component registry: id → geometry builder, station/waterline/buttline, explode vector
const COMPONENTS = {
  RADAR:    { label: 'Radar', g: () => new THREE.CylinderGeometry(.3, .3, .08, 40), rot: [0, 0, Math.PI / 2], at: [1.0, 1.08, 0], ex: [1.2, 0, 0] },
  ADC:      { label: 'ADC', g: () => new THREE.BoxGeometry(.28, .16, .2), at: [2.15, 1.0, .22], ex: [.4, .2, .6] },
  NLG:      { label: 'NLG', g: () => new THREE.CylinderGeometry(.2, .2, .12, 32), rot: [Math.PI / 2, 0, 0], at: [3.55, .78, 0], ex: [0, -.7, 0] },
  AHRS:     { label: 'AHRS', g: () => new THREE.BoxGeometry(.22, .14, .18), at: [4.35, 1.5, -.3], ex: [0, .6, -.6] },
  DFCC:     { label: 'DFCC', g: () => new THREE.BoxGeometry(.42, .22, .3), at: [4.95, 1.52, .05], ex: [0, .9, 0] },
  INGPS:    { label: 'INS/GPS', g: () => new THREE.BoxGeometry(.3, .18, .22), at: [5.25, 1.45, .4], ex: [0, .7, .7] },
  BHEEM_EU: { label: 'BHEEM EU', g: () => new THREE.BoxGeometry(.36, .2, .26), at: [5.65, 1.4, -.42], ex: [0, .6, -1.0] },
  AMAGB:    { label: 'AMAGB', g: () => new THREE.BoxGeometry(.46, .3, .44), at: [7.25, .92, 0], ex: [0, -.9, 0] },
  HYD_PUMP: { label: 'Hyd pump 1 · SYS1', g: () => new THREE.CylinderGeometry(.13, .13, .34, 32), rot: [0, 0, Math.PI / 2], at: [7.62, .9, .36], ex: [0, -.9, .9] },
  HYD_PUMP2:{ label: 'Hyd pump 2 · SYS2', g: () => new THREE.CylinderGeometry(.13, .13, .34, 32), rot: [0, 0, Math.PI / 2], at: [7.62, .9, -.36], ex: [0, -.9, -.9] },
  JFS:      { label: 'JFS', g: () => new THREE.CylinderGeometry(.14, .14, .4, 28), rot: [0, 0, Math.PI / 2], at: [8.55, .95, .42], ex: [0, -.5, 1.0] },
  ENGINE:   { label: 'F404 engine', g: () => new THREE.CylinderGeometry(.46, .42, 4.7, 48, 1), rot: [0, 0, Math.PI / 2], at: [10.1, 1.32, 0], ex: [-.9, 0, 0] },
  FADEC:    { label: 'FADEC', g: () => new THREE.BoxGeometry(.32, .14, .2), at: [9.2, 1.0, -.48], ex: [0, -.5, -.9] },
  MLG_L:    { label: 'MLG L', g: () => new THREE.CylinderGeometry(.3, .3, .2, 36), rot: [Math.PI / 2, 0, 0], at: [8.3, .62, -1.38], ex: [0, -.6, -.5] },
  MLG_R:    { label: 'MLG R', g: () => new THREE.CylinderGeometry(.3, .3, .2, 36), rot: [Math.PI / 2, 0, 0], at: [8.3, .62, 1.38], ex: [0, -.6, .5] },
  CHUTE:    { label: 'Brake chute', g: () => new THREE.CylinderGeometry(.17, .17, .5, 28), rot: [0, 0, Math.PI / 2], at: [12.85, 1.98, 0], ex: [.0, .5, 0] },
  FUEL_F1:  { label: 'Fuel F1', g: () => new THREE.BoxGeometry(1.2, .42, .8), at: [6.2, 1.38, 0], ex: [0, 1.1, 0], ghost: true },
  FUEL_WL:  { label: 'Wing tank L', g: () => new THREE.BoxGeometry(1.8, .08, 1.5), at: [9.2, 1.18, -2.4], ex: [0, .3, -.6], ghost: true },
  FUEL_WR:  { label: 'Wing tank R', g: () => new THREE.BoxGeometry(1.8, .08, 1.5), at: [9.2, 1.18, 2.4], ex: [0, .3, .6], ghost: true }
};

export function createTwin(host, opts = {}) {
  const W = host.clientWidth, H = host.clientHeight, DPR = opts.dpr || 2;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(DPR); renderer.setSize(W, H); renderer.setClearColor(0xffffff, 0);
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(opts.fov || 28, W / H, .1, 200);
  scene.add(new THREE.HemisphereLight(0xffffff, 0xdfe2e6, 2.2));
  const key = new THREE.DirectionalLight(0xffffff, 1.4); key.position.set(4, 9, 6); scene.add(key);

  const res = new THREE.Vector2(W * DPR, H * DPR);
  const lineMat = (color, width, opacity = 1, dashed = false) => {
    const m = new LineMaterial({ color, linewidth: width, transparent: opacity < 1, opacity, dashed, dashSize: .18, gapSize: .12, worldUnits: false });
    m.resolution.copy(res); return m;
  };
  const edgesOf = (geom, color, width, opacity, thr = 22) => {
    const e = new THREE.EdgesGeometry(geom, thr); const g = new LineSegmentsGeometry().fromEdgesGeometry(e);
    return new LineSegments2(g, lineMat(color, width, opacity));
  };

  const root = new THREE.Group(); scene.add(root);
  // ---- airframe (ghost shell) ----
  const shellMat = new THREE.MeshLambertMaterial({ color: 0xeef0f3, transparent: true, opacity: .5, depthWrite: false, side: THREE.DoubleSide });
  const airframe = new THREE.Group(); root.add(airframe);
  const fus = loft(); airframe.add(new THREE.Mesh(fus, shellMat));
  // outline silhouette edges (crease) + frames + stringers for the blueprint look
  airframe.add(edgesOf(fus, 0x6b7078, 1.1, .65, 30));
  const frames = [1.0, 1.6, 2.6, 3.4, 4.05, 5.0, 6.0, 7.2, 8.4, 9.6, 10.8, 12.0, 12.55];
  frames.forEach(s => { const lg = new LineGeometry(); lg.setPositions(frameRing(s)); airframe.add(new Line2(lg, lineMat(0x8e939a, .9, .55))); });
  [0, Math.PI / 2, Math.PI, Math.PI * 1.5, Math.PI / 4, Math.PI * 1.75].forEach(th => {
    const pts = []; for (let s = .1; s <= 13.2; s += .2) { const w = lerpT(HW, s), t = lerpT(TOP, s), b = lerpT(BOT, s), yc = (t + b) / 2, a = (t - b) / 2, sn = Math.sin(th), cs = Math.cos(th);
      pts.push(ST(s), WL(yc + a * Math.sign(sn) * Math.pow(Math.abs(sn), .8)), w * Math.sign(cs) * Math.pow(Math.abs(cs), .8)); }
    const lg = new LineGeometry(); lg.setPositions(pts); airframe.add(new Line2(lg, lineMat(0xa9adb3, .7, .4)));
  });
  // wing
  const wingPts = [[4.6, 0], [4.6, 1.02], [7.29, 2.4], [9.32, 4.1], [10.72, 4.1], [11.22, 1.02], [11.22, -1.02], [10.72, -4.1], [9.32, -4.1], [7.29, -2.4], [4.6, -1.02]].map(([s, b]) => [ST(s), b]);
  const wing = plate(wingPts, .07, .025); wing.rotateX(-Math.PI / 2); wing.translate(0, WL(1.13), 0);
  airframe.add(new THREE.Mesh(wing, shellMat)); airframe.add(edgesOf(wing, 0x5f656d, 1.3, .85, 30));
  // elevon hinge lines
  [[[10.72, 4.0], [10.98, 2.45], [11.14, 1.1]], [[10.72, -4.0], [10.98, -2.45], [11.14, -1.1]]].forEach(l => { const lg = new LineGeometry(); lg.setPositions(l.flatMap(([s, b]) => [ST(s) + .22, WL(1.2), b])); airframe.add(new Line2(lg, lineMat(0x8e939a, .9, .7, false))); });
  // fin
  const fin = plate([[9.0, 1.82], [11.25, 4.35], [12.2, 4.38], [12.78, 1.95]].map(([s, w]) => [ST(s), WL(w)]), .07, .02); fin.translate(0, 0, -.035);
  airframe.add(new THREE.Mesh(fin, shellMat)); airframe.add(edgesOf(fin, 0x5f656d, 1.3, .85, 30));
  // canopy
  const can = new THREE.SphereGeometry(1, 40, 20, 0, Math.PI * 2, 0, Math.PI / 2); can.scale(1.02, .5, .36); can.translate(ST(3.62), WL(1.56), 0);
  airframe.add(new THREE.Mesh(can, new THREE.MeshLambertMaterial({ color: 0xdfe6ee, transparent: true, opacity: .55, depthWrite: false })));
  airframe.add(edgesOf(can, 0x6b7078, 1.0, .65, 40));
  // nozzle + intakes
  const noz = new THREE.CylinderGeometry(.41, .45, .62, 40, 1, true); noz.rotateZ(Math.PI / 2); noz.translate(ST(12.95), WL(1.36), 0);
  airframe.add(new THREE.Mesh(noz, new THREE.MeshLambertMaterial({ color: 0xc9ccd1, side: THREE.DoubleSide, transparent: true, opacity: .7 })));
  airframe.add(edgesOf(noz, 0x6b7078, 1.0, .7, 30));
  [-1, 1].forEach(sd => { const lip = new THREE.TorusGeometry(.3, .025, 10, 40); lip.scale(1, 1.25, .62); lip.rotateY(Math.PI / 2); lip.translate(ST(4.12), WL(.98), sd * .86);
    airframe.add(new THREE.Mesh(lip, new THREE.MeshLambertMaterial({ color: 0x9aa0a8 }))); });
  // nose probe
  const probe = new THREE.CylinderGeometry(.012, .02, .7, 8); probe.rotateZ(Math.PI / 2); probe.translate(ST(-.3), WL(.95), 0); airframe.add(new THREE.Mesh(probe, new THREE.MeshLambertMaterial({ color: 0x6b7078 })));

  // ---- components ----
  const nodes = {};
  Object.entries(COMPONENTS).forEach(([id, c]) => {
    const g = c.g(); if (c.rot) { g.rotateX(c.rot[0]); g.rotateY(c.rot[1]); g.rotateZ(c.rot[2]); }
    const mat = new THREE.MeshLambertMaterial({ color: 0xd8dbdf, transparent: !!c.ghost, opacity: c.ghost ? .22 : 1, depthWrite: !c.ghost });
    const mesh = new THREE.Mesh(g, mat);
    const grp = new THREE.Group(); grp.add(mesh);
    const edge = edgesOf(g, 0x62676f, 1.0, c.ghost ? .35 : .8, 25); grp.add(edge);
    grp.position.set(ST(c.at[0]), WL(c.at[1]), c.at[2]);
    root.add(grp); nodes[id] = { grp, mesh, edge, def: c, base: grp.position.clone() };
  });

  // ---- systems networks (hydraulics) ----
  const sysLines = new THREE.Group(); root.add(sysLines);
  const route = (pts, color, w = 2, op = .9) => { const lg = new LineGeometry(); lg.setPositions(pts.flatMap(([s, wl, b]) => [ST(s), WL(wl), b])); const l = new Line2(lg, lineMat(color, w, op)); sysLines.add(l); return l; };
  const SYS1 = 0x2563c9, SYS2 = 0x0e9f8f;
  const sys1 = [route([[7.62, .9, .36], [8.4, 1.0, .62], [10.6, 1.12, 1.2], [10.98, 1.18, 2.5]], SYS1), route([[8.4, 1.0, .62], [11.6, 1.6, .2], [12.1, 2.9, 0]], SYS1), route([[7.62, .9, .36], [8.3, .75, 1.3]], SYS1)];
  const sys2 = [route([[7.62, .9, -.36], [8.4, 1.0, -.62], [10.6, 1.12, -1.2], [10.98, 1.18, -2.5]], SYS2), route([[8.4, 1.0, -.62], [11.6, 1.6, -.2], [12.1, 2.9, 0]], SYS2), route([[7.62, .9, -.36], [3.6, .8, 0]], SYS2)];
  sysLines.visible = false;

  // ---- evidence arcs (reporter → suspects) ----
  const evid = new THREE.Group(); root.add(evid);
  const arc = (a, b, lift, color, width) => {
    const A = nodes[a].base, B = nodes[b].base, M = A.clone().add(B).multiplyScalar(.5); M.y += lift;
    const curve = new THREE.QuadraticBezierCurve3(A, M, B), pts = curve.getPoints(48).flatMap(p => [p.x, p.y, p.z]);
    const lg = new LineGeometry(); lg.setPositions(pts); const l = new Line2(lg, lineMat(color, width, 1, true)); l.computeLineDistances(); evid.add(l); return l;
  };
  let arcs = [arc('BHEEM_EU', 'HYD_PUMP', .9, 0xe8743b, 4.2), arc('BHEEM_EU', 'AMAGB', .55, 0xc98512, 1.6)];
  // data-driven arcs: weight 0.8 → the film's thick suspect arc, 0.2 → the thin one
  function setArcs(list) {
    arcs.forEach(l => { evid.remove(l); l.geometry.dispose(); l.material.dispose(); });
    arcs = (list || []).filter(a => nodes[a.from] && nodes[a.to]).map(a => { const w = Math.max(0, Math.min(1, a.weight ?? .5));
      return arc(a.from, a.to, .55 + .35 * (w - .2) / .6, w >= .5 ? 0xe8743b : 0xc98512, .733 + 4.333 * w); });
  }
  // pulse halos
  const halo = (color) => { const m = new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: .16, depthWrite: false })); root.add(m); return m; };
  const haloRep = halo(0x2563c9), haloSel = halo(0xe8743b);

  // ground: shadow + blueprint grid
  const cv = document.createElement('canvas'); cv.width = cv.height = 256; const cx = cv.getContext('2d');
  const gr = cx.createRadialGradient(128, 128, 10, 128, 128, 128); gr.addColorStop(0, 'rgba(20,24,30,.16)'); gr.addColorStop(1, 'rgba(20,24,30,0)'); cx.fillStyle = gr; cx.fillRect(0, 0, 256, 256);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(15, 9), new THREE.MeshBasicMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, depthWrite: false }));
  shadow.rotation.x = -Math.PI / 2; shadow.position.y = -1.25; root.add(shadow);
  const grid = new THREE.GridHelper(40, 40, 0xd6d6d1, 0xe9e9e6); grid.position.y = -1.26; grid.material.transparent = true; grid.material.opacity = .7; scene.add(grid); if (opts.grid === false) grid.visible = false;

  const state = { spec: opts.spec || null, lens: opts.lens || 'evidence', selected: opts.selected || 'HYD_PUMP', explode: 0, az: opts.az ?? 0.62, el: opts.el ?? 0.36, dist: opts.dist ?? 21, target: new THREE.Vector3(.2, -.1, 0), spin: opts.spin ?? true };

  const COL = { neutral: 0xdcdfe3, reporter: 0x2563c9, suspect: 0xe8743b, suspect2: 0xd9a03a, ok: 0x1f8a4c, warn: 0xc98512, bad: 0xd4492a, none: 0xe4e5e8 };
  const hex = v => (typeof v === 'string' && v[0] === '#' ? parseInt(v.slice(1), 16) : COL[v]);
  // a lens from the data: { paint: {node: tone | '#hex'}, dim, arcs: [{from, to, weight}], reporter }
  function paintSpec(sp) {
    Object.entries(nodes).forEach(([id, n]) => {
      const v = sp.paint && sp.paint[id], c = v != null && hex(v) != null ? hex(v) : sp.dim ? COL.neutral : COL.none;
      n.mesh.material.color.setHex(c); n.edge.material.opacity = n.def.ghost ? .3 : (v == null && sp.dim ? .45 : .8);
      n.edge.material.color.setHex(id === state.selected ? 0xb4511f : 0x62676f); n.edge.material.linewidth = id === state.selected ? 2.4 : 1.0;
    });
    evid.visible = arcs.length > 0; sysLines.visible = false;
    haloRep.visible = !!(sp.reporter && nodes[sp.reporter]); haloSel.visible = !!state.selected;
  }
  function paint() {
    if (state.spec) return paintSpec(state.spec);
    const L = state.lens;
    Object.entries(nodes).forEach(([id, n]) => {
      let c = COL.neutral, eo = .8;
      if (L === 'evidence') { if (id === 'BHEEM_EU') c = COL.reporter; else if (id === 'HYD_PUMP') c = COL.suspect; else if (id === 'AMAGB') c = COL.suspect2; else { c = COL.neutral; eo = .45; } }
      if (L === 'health') { const h = { HYD_PUMP: COL.warn, MLG_L: 0xe8a17c, MLG_R: 0xe8a17c, INGPS: 0xc7c9cc, RADAR: 0xc7c9cc, ENGINE: 0xb9d9c6 }[id]; c = h || COL.none; }
      if (L === 'maintenance') { const h = { HYD_PUMP: COL.warn, INGPS: 0xe7c27a, RADAR: 0xe7c27a, ADC: 0xe7c27a, MLG_L: 0xf0d6a6, MLG_R: 0xf0d6a6 }[id]; c = h || COL.neutral; }
      if (L === 'systems') { const h = { HYD_PUMP: 0x2563c9, HYD_PUMP2: 0x0e9f8f, AMAGB: 0x8aa6d8 }[id]; c = h || COL.neutral; eo = h ? .9 : .4; }
      n.mesh.material.color.setHex(c); n.edge.material.opacity = n.def.ghost ? .3 : eo;
      n.edge.material.color.setHex(id === state.selected ? 0xb4511f : 0x62676f); n.edge.material.linewidth = id === state.selected ? 2.4 : 1.0;
    });
    evid.visible = L === 'evidence'; sysLines.visible = L === 'systems';
    haloRep.visible = L === 'evidence'; haloSel.visible = !!state.selected;
  }

  const proj = new THREE.Vector3();
  function screenOf(id) { const n = nodes[id]; proj.copy(n.grp.position); proj.project(camera); return [(proj.x * .5 + .5) * W, (-proj.y * .5 + .5) * H]; }

  function renderAt(t) {
    const az = state.az + (state.spin ? Math.sin(t * .18) * .16 : 0), el = state.el;
    camera.position.set(state.target.x + state.dist * Math.cos(el) * Math.cos(az), state.target.y + state.dist * Math.sin(el), state.target.z + state.dist * Math.cos(el) * Math.sin(az));
    camera.lookAt(state.target);
    Object.values(nodes).forEach(n => { const e = n.def.ex; n.grp.position.set(n.base.x + e[0] * state.explode * -1, n.base.y + e[1] * state.explode, n.base.z + e[2] * state.explode); });
    airframe.children.forEach(ch => { if (ch.material) ch.material.opacity = ch.material.userData.op0 ?? (ch.material.userData.op0 = ch.material.opacity); });
    const pr = (t * .9) % 1, ps = .34 + pr * .42;
    const rep = nodes[(state.spec && state.spec.reporter) || 'BHEEM_EU'] || nodes.BHEEM_EU;
    haloRep.position.copy(rep.grp.position); haloRep.scale.setScalar(ps); haloRep.material.opacity = .22 * (1 - pr);
    if (state.selected) { haloSel.position.copy(nodes[state.selected].grp.position); haloSel.scale.setScalar(.36 + Math.sin(t * 2.4) * .03); haloSel.material.opacity = .18; }
    arcs.forEach(l => { l.material.dashOffset = -t * .9; });
    renderer.render(scene, camera);
    if (opts.onFrame) opts.onFrame(screenOf, t);
  }
  // which component is under a client point (for clicks in the viewport)
  const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
  function pick(clientX, clientY) {
    const r = renderer.domElement.getBoundingClientRect(); ndc.set((clientX - r.left) / r.width * 2 - 1, -((clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(ndc, camera);
    const hit = ray.intersectObjects(Object.values(nodes).filter(n => !n.def.ghost).map(n => n.mesh), false)[0];
    return hit ? Object.keys(nodes).find(k => nodes[k].mesh === hit.object) : null;
  }
  if (state.spec) setArcs(state.spec.arcs);
  paint();
  return { renderAt, state, nodes, paint, screenOf, camera, renderer, pick,
    setLens(l) { state.spec = null; state.lens = l; paint(); },
    setLensSpec(sp) { state.spec = sp; setArcs(sp.arcs); paint(); },
    select(id) { state.selected = id; paint(); } };
}
