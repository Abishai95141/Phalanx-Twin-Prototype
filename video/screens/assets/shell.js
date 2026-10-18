/* PHALANX TWIN — shared shell: icon sprite, window chrome, sidebar, page head.
   Pages declare <body data-page="…"> and call PHX.mount({...}) with their head config. */
(function () {
  const I = {
    readiness: '<path d="M4.5 16.5a7.5 7.5 0 1 1 15 0"/><path d="M12 16.5l3.6-4.4"/><circle cx="12" cy="16.5" r="1.3"/><path d="M4 19.5h16"/>',
    decisions: '<rect x="4" y="3.5" width="16" height="17" rx="3"/><path d="M8 9.2l1.7 1.7 3.1-3.3"/><path d="M8 15.5h8"/><path d="M15 9.5h1"/>',
    twin: '<path d="M12 2.6l1.25 4.3 6.95 7.9v1.7l-6.7-2.1-.35 4.1 2.3 1.75v1.35L12 20.7l-3.45.9v-1.35l2.3-1.75-.35-4.1-6.7 2.1v-1.7l6.95-7.9z"/>',
    plan: '<rect x="3.5" y="4.5" width="17" height="16" rx="3"/><path d="M3.5 9h17"/><path d="M8 3v3M16 3v3"/><path d="M7 12.6h5M10 16h7"/>',
    spares: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5"/><path d="M12 12v9"/><path d="M8 5.3l8 4.4"/>',
    insights: '<path d="M4 20h16"/><rect x="5.5" y="11" width="3" height="6" rx="1"/><rect x="10.5" y="6" width="3" height="11" rx="1"/><rect x="15.5" y="9" width="3" height="8" rx="1"/>',
    assurance: '<path d="M12 3l7 3v5.4c0 4.3-2.9 7.7-7 9.1-4.1-1.4-7-4.8-7-9.1V6z"/><path d="M9 11.8l2.1 2.1 4-4.2"/>',
    assistant: '<path d="M5 18.5l-1.2 2.3 3.6-1.2A8 8 0 1 0 5 18.5z"/><path d="M12 8.3v1.6M12 14.1v1.6M8.3 12h1.6M14.1 12h1.6"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.3-4.3"/>',
    chevDown: '<path d="M6 9.5l6 6 6-6"/>', chevRight: '<path d="M9.5 6l6 6-6 6"/>', chevLeft: '<path d="M14.5 6l-6 6 6 6"/>',
    arrowRight: '<path d="M4.5 12h15M13.5 6l6 6-6 6"/>', arrowUpRight: '<path d="M7 17L17 7M8.5 7H17v8.5"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="3"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>',
    lock: '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/>',
    shield: '<path d="M12 3l7 3v5.4c0 4.3-2.9 7.7-7 9.1-4.1-1.4-7-4.8-7-9.1V6z"/>',
    server: '<rect x="4" y="4" width="16" height="7" rx="2"/><rect x="4" y="13" width="16" height="7" rx="2"/><path d="M8 7.5h.01M8 16.5h.01"/>',
    cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 3v3M15 3v3M9 18v3M15 18v3M3 9h3M3 15h3M18 9h3M18 15h3"/>',
    check: '<path d="M5 12.5l4.2 4.2L19 7"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
    alert: '<path d="M12 4l9 15.5H3z"/><path d="M12 10v4M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8h.01"/>',
    wrench: '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.1L4 16.7 7.3 20l5.3-5.3a4 4 0 0 0 5.1-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>',
    fork: '<circle cx="6.5" cy="5.5" r="2"/><circle cx="6.5" cy="18.5" r="2"/><circle cx="17.5" cy="8.5" r="2"/><path d="M6.5 7.5v9M17.5 10.5c0 4-4 4-11 6"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    hash: '<path d="M5 9h15M4 15h15M10 4L8 20M16 4l-2 16"/>',
    pen: '<path d="M4 20l1-4.2L16.3 4.5a2 2 0 0 1 2.9 0l.3.3a2 2 0 0 1 0 2.9L8.2 19z"/><path d="M14 7l3 3"/>',
    signature: '<path d="M3 18c3-1 4-9 6-9s-1 8 1 8 3-5 4.5-5 .5 4 2 4 2-1 4.5-1"/><path d="M3 21h18"/>',
    user: '<circle cx="12" cy="8.5" r="3.7"/><path d="M4.5 20.5c1-4 4-5.8 7.5-5.8s6.5 1.8 7.5 5.8"/>',
    layers: '<path d="M12 3.5l9 4.8-9 4.8-9-4.8z"/><path d="M3 12.6l9 4.8 9-4.8"/><path d="M3 16.7l9 4.8 9-4.8"/>',
    eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    cube: '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>',
    sliders: '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    table: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="M3.5 9.5h17M3.5 14.5h17M9.5 9.5v10"/>',
    wave: '<path d="M3 13c2.2 0 2.2-5 4.5-5s2.3 8 4.5 8 2.3-10 4.5-10S18.8 13 21 13"/>',
    flag: '<path d="M5 21V4M5 4.5c5-2 7 2 12 0V13c-5 2-7-2-12 0"/>',
    tyre: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3.5"/><path d="M12 3.5v5M12 15.5v5M3.5 12h5M15.5 12h5"/>',
    drop: '<path d="M12 3.5s6 6.6 6 10.6a6 6 0 0 1-12 0c0-4 6-10.6 6-10.6z"/>',
    bolt: '<path d="M13 2.8L5.5 13.5H12l-1 7.7 7.5-10.7H12z"/>',
    engine: '<path d="M3 9.5h12l5 1.5v2l-5 1.5H3z"/><path d="M7 9.5v5M11 9.5v5"/><path d="M3 12h-.01"/>',
    radar: '<path d="M4.5 19.5a10.6 10.6 0 0 1 0-15"/><path d="M8 16a5.7 5.7 0 0 1 0-8"/><circle cx="12" cy="12" r="1.5"/><path d="M12 12l7.5-7.5"/>',
    play: '<path d="M7 4.5v15l12-7.5z"/>', pause: '<path d="M8 5v14M16 5v14"/>',
    rewind: '<path d="M11 6l-7 6 7 6zM20 6l-7 6 7 6z"/>',
    download: '<path d="M12 4v11M7 10.5l5 5 5-5M4.5 20h15"/>',
    filter: '<path d="M4 5h16l-6.2 7.5V19l-3.6 1.5v-8z"/>',
    refresh: '<path d="M20 11.5A8 8 0 0 0 5.6 7M4 4v4h4M4 12.5A8 8 0 0 0 18.4 17M20 20v-4h-4"/>',
    sparkle: '<path d="M12 3.5l1.8 5 5 1.8-5 1.8-1.8 5-1.8-5-5-1.8 5-1.8zM18.5 15.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/>',
    book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5"/>',
    history: '<path d="M4 12a8 8 0 1 0 2.4-5.7L4 8.5"/><path d="M4 4v4.5h4.5M12 8v4l3 2"/>',
    scale: '<path d="M12 4v16M6 20h12M5 8h14M5 8l-2.5 6a2.8 2.8 0 0 0 5 0zM19 8l-2.5 6a2.8 2.8 0 0 0 5 0z"/>',
    grid: '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    list: '<path d="M9 6h11M9 12h11M9 18h11M4.5 6h.01M4.5 12h.01M4.5 18h.01"/>',
    target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r=".9"/>',
    xray: '<rect x="3.5" y="3.5" width="17" height="17" rx="3" stroke-dasharray="2.5 2.5"/><path d="M12 6.5l1 3.4 4.5 5v1.2l-4.3-1.3-.2 2.7 1.5 1v1L12 18.8l-2.5.7v-1l1.5-1-.2-2.7-4.3 1.3v-1.2l4.5-5z"/>',
    explode: '<rect x="9" y="9" width="6" height="6" rx="1"/><path d="M4 4l3 3M20 4l-3 3M4 20l3-3M20 20l-3-3"/>',
    section: '<path d="M4 19L19 4"/><rect x="3.5" y="3.5" width="17" height="17" rx="3"/>',
    inbox: '<path d="M3.5 13.5l2.5-8h12l2.5 8V19a1.5 1.5 0 0 1-1.5 1.5h-14A1.5 1.5 0 0 1 3.5 19z"/><path d="M3.5 13.5H8l1.5 2.5h5l1.5-2.5h4.5"/>',
    snooze: '<path d="M10 4h6l-6 7h6"/><path d="M4 13h5l-5 6h5"/>',
    tag: '<path d="M3.5 12.3V4.5a1 1 0 0 1 1-1h7.8l8.2 8.2a1.4 1.4 0 0 1 0 2l-6.6 6.6a1.4 1.4 0 0 1-2 0z"/><circle cx="8" cy="8" r="1.4"/>',
    gauge: '<path d="M4.5 16.5a7.5 7.5 0 1 1 15 0"/><path d="M12 16.5l3.6-4.4"/>',
    route: '<circle cx="6" cy="18" r="2"/><circle cx="18" cy="6" r="2"/><path d="M8 18h7.5a3.5 3.5 0 0 0 0-7h-7a3.5 3.5 0 0 1 0-7H16"/>',
    dot: '<circle cx="12" cy="12" r="3" fill="currentColor"/>',
    minus: '<path d="M5 12h14"/>', plus: '<path d="M12 5v14M5 12h14"/>',
    more: '<circle cx="5.5" cy="12" r="1.2"/><circle cx="12" cy="12" r="1.2"/><circle cx="18.5" cy="12" r="1.2"/>',
    paperclip: '<path d="M20 11.5l-8 8a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7l-8.5 8.5a1.7 1.7 0 0 1-2.4-2.4l7.8-7.8"/>',
    send: '<path d="M12 19V5M5.5 11.5L12 5l6.5 6.5"/>',
    command: '<path d="M9 6.5A2.5 2.5 0 1 0 6.5 9H9zM15 6.5A2.5 2.5 0 1 1 17.5 9H15zM9 17.5A2.5 2.5 0 1 1 6.5 15H9zM15 17.5a2.5 2.5 0 1 0 2.5-2.5H15zM9 9h6v6H9z"/>'
  };
  const sprite = '<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs>' +
    Object.entries(I).map(([k, v]) => `<symbol id="i-${k}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">${v}</symbol>`).join('') +
    '</defs></svg>';
  const icon = (n, cls = 'ico') => `<svg class="${cls}"><use href="#i-${n}"/></svg>`;

  const LOGO = window.PHX_LOGO || '';

  const NAV = [
    ['readiness', 'Readiness', 'readiness.html', ''],
    ['decisions', 'Decisions', 'decisions.html', '<span class="meta">7 due</span>'],
    ['twin', 'Aircraft twin', 'twin.html', ''],
    ['plan', 'Plan & what-if', 'plan.html', ''],
    ['spares', 'Spares', 'spares.html', '<span class="meta">1 AOG</span>'],
    ['insights', 'Fleet insights', 'insights.html', ''],
    ['assurance', 'Assurance', 'assurance.html', '']
  ];

  function sidebar(active) {
    return `
    <aside class="sidebar">
      <div class="brand">
        <div class="logo">${LOGO}</div>
        <div class="org">Station Sulur</div>
        <div class="dept">Maintenance control · Tejas flight line</div>
      </div>
      <div class="side-cta"><button class="btn-block">${icon('decisions')}Open decision board<span class="count">7</span></button></div>
      <div class="side-sec">
        <div class="side-label">Workspaces</div>
        <nav class="nav">${NAV.map(([k, label, href, meta]) =>
          `<a class="${k === active ? 'active' : ''}" href="${href}">${icon(k)}${label}${meta}</a>`).join('')}
        </nav>
      </div>
      <div class="side-sec epoch">
        <div class="side-label">Epoch · Mon 22 Jun</div>
        <div class="epoch-line">
          <div class="ep done"><i></i><span class="t mono">06:00</span><span>Snapshot sealed</span></div>
          <div class="ep now"><i></i><span class="t mono">07:45</span><span>Board freezes</span><em>1 h 33 m</em></div>
          <div class="ep"><i></i><span class="t mono">08:00</span><span>Orders issued</span></div>
        </div>
      </div>
      <div class="side-fill"></div>
      <div class="station">
        <div class="side-label" style="padding:0 0 12px">Station server · GB10</div>
        <div class="meter-row"><div class="mr-top"><span>Unified memory</span><b class="num">15.3 / 128 GB</b></div><div class="meter"><i style="width:12%"></i></div></div>
        <div class="meter-row"><div class="mr-top"><span>Assistant · gpt-oss-20b</span><b class="num">resident</b></div><div class="meter"><i style="width:100%;opacity:.35"></i></div></div>
        <div class="meter-row"><div class="mr-top"><span>Engines · epoch run</span><b class="num">sealed 06:04</b></div><div class="meter ink"><i style="width:100%"></i></div></div>
        <div class="live"><i></i>Air-gapped · all services local</div>
      </div>
    </aside>`;
  }

  function head(cfg) {
    const chips = (cfg.chips || []).map(c => `<span class="chip ${c.k || ''}">${c.i ? icon(c.i, 'ico-sm') : ''}${c.t}</span>`).join('');
    return `
    <header class="page-head">
      <div><h1>${cfg.title}</h1>${cfg.sub ? `<div class="sub">${cfg.sub}</div>` : ''}</div>
      <div class="spacer"></div>
      ${cfg.headExtra || ''}
      <div class="chips">${chips}</div>
    </header>`;
  }

  window.PHX = {
    icon,
    mount(cfg) {
      document.body.insertAdjacentHTML('afterbegin', sprite);
      const content = document.getElementById('content');
      const html = content.innerHTML;
      const win = `
      <div class="stage"><div class="window">
        <div class="titlebar"><div class="lights"><i></i><i></i><i></i></div>
          <span><b>Phalanx Twin</b> — sulur-mx-01</span>
          <div class="tb-right">${icon('lock', 'ico-sm')}<span>Air-gapped</span><span class="mono">v1.4.2</span></div>
        </div>
        <div class="app">
          ${sidebar(cfg.page)}
          <main class="main">
            ${head(cfg)}
            <section class="content" id="content-mount">${html}</section>
          </main>
        </div>
        ${cfg.overlay || ''}
      </div></div>`;
      content.remove();
      document.body.insertAdjacentHTML('beforeend', win);
      // resolve inline icon placeholders <i data-i="name" class="..."></i>
      document.querySelectorAll('i[data-i]').forEach(el => {
        const cls = el.className || 'ico';
        el.outerHTML = icon(el.dataset.i, cls);
      });
      if (cfg.after) cfg.after();
    }
  };
})();
