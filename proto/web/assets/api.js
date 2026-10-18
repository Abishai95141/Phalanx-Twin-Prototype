/* PHALANX TWIN — data loader for the loop pages.
   Fills the window.PHX_* globals the pages read, from the ground API (/api, DEVELOPMENT.md §2.11) or, with
   ?source=film, from the film data files (assets/data*.js + assets/data-film.js). Both paths return the same
   shapes — assets/SHAPES.md is the contract. Pages render only after the loader resolves.

   URL parameters:  ?source=film   use the film data (22 Jun 2026 epoch) instead of /api
                    ?asof=<ISO>    read readiness and twin as of this time
                    ?tail=TJ10x    twin tail;  ?issue=<issue id>;  ?order=<order id>
                    ?by= / ?signer= names recorded on decisions and signatures (default SEO / ENGG-OFFICER) */
(function () {
  const Q = new URLSearchParams(location.search);
  const FILM = Q.get('source') === 'film';
  const ASOF = Q.get('asof') || null;
  const CARRY = ['source', 'asof'];          // kept on every internal link
  const FILM_FILES = ['data.js', 'data-decisions.js', 'data-epoch.js', 'data-workbench.js', 'data-provenance.js', 'data-film.js'];

  const enc = encodeURIComponent;
  const qs = o => {
    const p = new URLSearchParams();
    Object.entries(o).forEach(([k, v]) => { if (v != null && v !== '') p.set(k, v); });
    const s = p.toString(); return s ? '?' + s : '';
  };

  // GET endpoints → global each one fills
  const ROUTES = {
    epoch: () => '/api/epoch',
    readiness: () => '/api/readiness' + qs({ asof: ASOF }),
    board: () => '/api/board',
    issue: id => `/api/issues/${enc(id)}`,
    workbench: id => `/api/workbench/${enc(id)}`,
    twin: tail => `/api/twin/${enc(tail)}` + qs({ asof: ASOF }),
    serial: (tail, serial) => `/api/serial/${enc(tail)}/${enc(serial)}`,
    search: q => '/api/search' + qs({ q }),
    provenance: oid => `/api/provenance/${enc(oid)}`,
    policies: issue => '/api/policies' + qs({ issue }),
    assurance: () => '/api/assurance'
  };
  const GLOBAL = { epoch: 'PHX_EP', readiness: 'PHX_DATA', board: 'PHX_DEC', issue: 'PHX_ISSUE', workbench: 'PHX_WB', twin: 'PHX_TWIN', provenance: 'PHX_PROV' };

  const apiErr = (status, path, detail) => Object.assign(new Error(`${path} → ${status || 'no answer'}`), { status, path, detail: detail || '' });

  let filmP = null;
  function film() {
    if (!filmP) filmP = FILM_FILES.reduce((p, f) => p.then(() => new Promise((ok, no) => {
      const s = document.createElement('script'); s.src = 'assets/' + f; s.onload = ok;
      s.onerror = () => no(apiErr(0, 'assets/' + f, 'film data file missing')); document.head.appendChild(s);
    })), Promise.resolve());
    return filmP;
  }

  async function getJSON(path) {
    let r;
    try { r = await fetch(path, { headers: { Accept: 'application/json' }, cache: 'no-store' }); }   /* live state: never from the HTTP cache */ catch (e) { throw apiErr(0, path, 'not reachable'); }
    if (!r.ok) { let d = ''; try { const j = await r.json(); d = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail || ''); } catch (e) { /* not JSON */ } throw apiErr(r.status, path, d); }
    return r.json();
  }

  async function get(name, ...args) {
    if (FILM) {
      await film();
      const v = window.PHX_FILM[name] ? window.PHX_FILM[name](...args) : null;
      if (v == null) throw apiErr(404, ROUTES[name](...args), 'not in the film data');
      return JSON.parse(JSON.stringify(v));
    }
    return getJSON(ROUTES[name](...args));
  }

  // GET and store in the page's global (PHX_EP, PHX_DATA, …)
  async function need(name, ...args) {
    const v = norm(name, await get(name, ...args));
    if (GLOBAL[name]) window[GLOBAL[name]] = v;
    return v;
  }

  // like need(), for data a page can do without (sidebar epoch, board focus): null when it does not answer
  async function want(name, ...args) {
    try { return await need(name, ...args); } catch (e) { console.info(`[phx] optional ${e.path} → ${e.status || 'no answer'}`); return null; }
  }

  // ---- normalizers: fill the optional fields of SHAPES.md from the required ones, so pages read one shape
  const pct = v => (v == null ? null : +(v * 100).toFixed(1));
  const NORM = {
    readiness(j) {
      const c = (window.PHX_EP && PHX_EP.clock) || {}, d30 = (j.kpis && j.kpis.d30) || {};
      j.kpi = j.kpi || {
        mc_now: j.now ? j.now.mc : j.fleet.filter(f => !/^NMC/.test(f.state)).length, of: j.now ? j.now.of : j.fleet.length,
        mc30: pct(d30.mc), fmc30: pct(d30.fmc), norm: pct(j.kpis && j.kpis.norm_mc) ?? 75, parts30: pct(d30.tnmcs),
        due: c.due ?? (window.PHX_DEC ? PHX_DEC.board.length : null), freeze: c.freeze || null, alert_rows: j.triage ? j.triage.alert_rows : null
      };
      const WHY = { NMCS: 'Waiting for parts', NMCD: 'At depot', NMCM_S: 'In scheduled maintenance', NMCM_U: 'In unscheduled maintenance', PMCM: 'Partly mission capable', FMC: 'Flying normally' };
      j.fleet.forEach(f => { f.card = f.card || { zones: [], tone: { NMCS: 'nmcs', NMCD: 'nmcd' }[f.state], headline: WHY[f.state] || f.state, detail: `${f.open_jobs} open job${f.open_jobs === 1 ? '' : 's'} · ${f.deferred} deferred` }; });
      return j;
    },
    twin(j) { return window.PHX_TWINVIEW ? PHX_TWINVIEW(j) : j; }
  };
  const norm = (name, v) => (NORM[name] && v ? NORM[name](v) : v);

  // POST never throws: { ok, status, data, detail, path }
  async function post(path, body) {
    let r;
    try { r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' }, body: JSON.stringify(body || {}) }); }
    catch (e) { return { ok: false, status: 0, path, detail: 'not reachable' }; }
    let data = null; try { data = await r.json(); } catch (e) { /* empty body */ }
    const detail = data && data.detail ? (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)) : '';
    return { ok: r.ok, status: r.status, data, detail, path };
  }

  // one line for PHX.notice when a POST did not go through
  function explain(res) {
    if (res.status === 0) return `Ground API not reachable · ${res.path}`;
    if (res.status === 404 || res.status === 405) return `Not recorded · the ground API has no ${res.path} yet`;
    if (res.status === 409) return `Refused · ${res.detail || 'conflicts with the epoch state'}`;
    return `Ground API error ${res.status}${res.detail ? ' · ' + res.detail : ''}`;
  }

  function href(page, params = {}) {
    const p = {};
    CARRY.forEach(k => { if (Q.get(k)) p[k] = Q.get(k); });
    Object.assign(p, params);
    return page + qs(p);
  }

  const by = Q.get('by') || 'SEO', signer = Q.get('signer') || 'ENGG-OFFICER';
  const actions = {
    decide: (issueId, action, extra = {}) => post(`/api/issues/${enc(issueId)}/decision`, { action, by, ...extra }),
    sign: orderId => post(`/api/orders/${enc(orderId)}/sign`, { by: signer }),
    draft: (issueId, testId) => post(`/api/workbench/${enc(issueId)}/draft`, { test_id: testId }),
    advance: () => post('/api/epoch/advance', {}),
    autoplay: n => post('/api/epoch/autoplay', { n }),
    verify: orderId => post('/api/provenance/verify', { order_id: orderId }),
    replay: orderId => post('/api/provenance/replay', { order_id: orderId })
  };

  // A page throws empty({...}) when there is honestly nothing to show yet (no board item, no order).
  const empty = spec => Object.assign(new Error('empty'), { empty: spec });
  const panel = (kick, title, text, link) => `<div class="v2"><div class="panel2 c12">
        <span class="kick">${kick}</span>
        <div class="t2">${title}</div>
        <div class="sub2" style="max-width:820px">${text}</div>${link ? `
        <a class="lnk" style="margin-top:22px;text-decoration:none" href="${PHX.esc(link.href)}">${PHX.esc(link.label)} <i data-i="arrowRight"></i></a>` : ''}</div></div>`;

  // the board item a decision page opens: ?issue=, else the board's focus, else its first row
  async function boardItem(A) {
    if (Q.get('issue')) { await A.want('board'); return Q.get('issue'); }
    const B = await A.want('board');
    const id = B && (B.focus || (B.board[0] || {}).id);
    if (id) return id;
    if (!B) await A.need('board');          // the board did not answer: say so
    const day = (window.PHX_EP && PHX_EP.clock && PHX_EP.clock.day) || 'today';
    throw empty({ kick: `Board · ${day}`, title: 'Nothing on today\u2019s board', text: 'Triage found no issue that needs a decision in the 06:00 snapshot. Recommendations, evidence and tests appear here when it does.', link: { label: 'Open board', href: href('decisions.html') } });
  }
  const notOnBoard = e => !/\/issues\//.test(e.path || '') ? null : ({ kick: 'Board', title: `${PHX.esc(Q.get('issue') || 'This item')} is not on today\u2019s board`, text: 'It may have been closed, grouped or snoozed since the snapshot.', link: { label: 'Open board', href: href('decisions.html') } });

  // Load, then render; empty and failed loads keep the page's own frame and say what is missing.
  async function boot(cfg) {
    let stage = 'load';
    const c0 = document.getElementById('content'); if (c0) c0.style.visibility = 'hidden';   // no unstyled template while loading
    const slow = setTimeout(() => document.body.insertAdjacentHTML('beforeend', `<div id="phx-loading" style="position:fixed;inset:0;display:grid;place-items:center;font:600 15px var(--font);color:var(--ink-4);background:var(--stage)">Reading the twin as of the snapshot…</div>`), 400);
    const done = () => { clearTimeout(slow); document.getElementById('phx-loading')?.remove(); };
    try {
      await cfg.load({ need, want, get, q: Q, empty });
      stage = 'render';
      done(); PHX.mount(cfg.render());
      return;
    } catch (e) {
      done();
      const mount = (html, chips) => {
        const c = document.getElementById('content');
        if (c) { c.innerHTML = html; PHX.mount({ page: cfg.page, title: cfg.title || 'Phalanx Twin', sub: cfg.sub || '', chips }); }
        else { const m = document.getElementById('content-mount'); if (m) { m.innerHTML = html; PHX.icons(m); } }   // failed after mounting: keep the frame
      };
      const E = e.empty || (e.status === 404 && cfg.notFound && cfg.notFound(e));
      if (E) { mount(panel(E.kick, E.title, E.text, E.link), window.PHX_EP ? PHX.clockChips() : []); return; }
      if (stage === 'render') {
        console.warn('[phx] render failed', e);
        mount(panel(FILM ? 'Film data' : 'Ground API', 'This screen could not read the response', `${PHX.esc(e.message)} · the fields it needs are listed in <span class="mono">assets/SHAPES.md</span>.`), [{ k: 'warn', i: 'alert', t: 'Shape mismatch' }]);
        return;
      }
      console.warn('[phx] load failed', e);
      const status = e.status ?? '';
      const what = status === 404 ? 'has nothing at' : status ? `answered ${status} for` : 'did not answer';
      const hint = FILM ? 'The film data has no record for this request.'
        : status >= 500 ? 'The ground API failed on this request; the error is in its server log. Other pages still work.'
        : status ? 'The request reached the ground API but was not accepted.'
        : 'Start the ground service (launch configuration “ground”, port 8700), or add <span class="mono">?source=film</span> to the address to read the film data for Mon 22 Jun.';
      mount(panel(FILM ? 'Film data' : 'Ground API', `The ${FILM ? 'film data' : 'ground API'} ${what} <span class="mono" style="font-size:18px">${PHX.esc(e.path || '')}</span>`,
        `${e.detail ? PHX.esc(e.detail) + ' · ' : ''}${hint}`), [{ k: 'warn', i: 'alert', t: status ? `HTTP ${status}` : 'No answer' }]);
    }
  }

  window.PHX_API = { film: FILM, asof: ASOF, q: Q, by, signer, routes: ROUTES, get, need, want, post, explain, href, boot, empty, boardItem, notOnBoard, ...actions };
})();
