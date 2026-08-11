/* ============================================================
   NEXT GEN / CRM LITE DEMO SHIM

   This folder is a byte-faithful copy of the real Next Gen CRM front end.
   Nothing in the app's own code was rewritten, so the demo looks and behaves
   exactly like the product and stays cheap to re-sync when the real app moves.

   This shim is what makes the copy safe to publish:

     - every network call is intercepted; the real API is never reached
     - reads return invented records
     - writes are accepted so the UI responds, but go nowhere
     - localStorage / sessionStorage are stubbed, so a refresh empties the board
     - a persistent DEMO badge makes the status unmistakable

   It must load BEFORE the application script. Nothing here should ever be
   pointed at a live host.
   ============================================================ */
(function () {
  'use strict';

  // ---------- invented records ----------
  // No real company, person, contact detail, address or money value.
  var COMPANIES = [
    ['Blue Harbour Villas', 'Hospitality', 'Paros'],
    ['Northgate Dental Studio', 'Medical', 'Athens'],
    ['Marlow & Finch Interiors', 'Established service', 'Thessaloniki'],
    ['Olive Lane Bakery', 'Retail', 'Corfu'],
    ['Sunset Ridge Rentals', 'Hospitality', 'Rhodes'],
    ['Carter Physio Rooms', 'Medical', 'Athens'],
    ['Hollow Pine Studios', 'Creative', 'Athens'],
    ['Vantage Legal Partners', 'Established service', 'Piraeus'],
    ['Wildwater Boat Tours', 'Hospitality', 'Zakynthos'],
    ['Ember Skin Clinic', 'Medical', 'Glyfada'],
    ['Tidewell Apartments', 'Hospitality', 'Naxos'],
    ['Copperleaf Accountancy', 'Established service', 'Athens']
  ];
  // A realistic funnel shape, not one lead per status. Spreading evenly makes
  // the derived response rate read 400%, which instantly looks fake.
  // Wide at the top, narrow at the bottom, sent > responded.
  var STATUSES = ['new', 'new', 'new',
                  'researching', 'researching',
                  'draft_ready', 'draft_ready',
                  'outreach_sent', 'outreach_sent', 'outreach_sent',
                  'responded',
                  'meeting_booked'];
  var GRADES = ['A', 'B', 'C'];

  function makeLead(i) {
    var c = COMPANIES[i % COMPANIES.length];
    return {
      id: i + 1,
      name: c[0],
      company: c[0],
      business_name: c[0],
      category: c[1],
      industry: c[1],
      city: c[2],
      location: c[2],
      status: STATUSES[i % STATUSES.length],
      grade: GRADES[i % GRADES.length],
      score: 55 + ((i * 7) % 45),
      website: '',
      email: '',
      phone: '',
      notes: 'Invented record for demonstration. No client data.',
      created_at: new Date(Date.now() - i * 86400000).toISOString(),
      updated_at: new Date().toISOString()
    };
  }
  var LEADS = [];
  for (var i = 0; i < 12; i++) LEADS.push(makeLead(i));

  var TASKS = [
    { id: 'dt-1', title: 'Map the current enquiry form', description: 'Trace where submissions land today.', kind: 'discovery', priority: 'normal', deadline: null },
    { id: 'dt-2', title: 'Confirm workflow owner',        description: 'Who picks up an enquiry after hours?', kind: 'discovery', priority: 'normal', deadline: null },
    { id: 'dt-3', title: 'Draft booking handoff',          description: 'Website to CRM to confirmation.',     kind: 'build',     priority: 'high',   deadline: null }
  ];

  // ---------- route table ----------
  // Shapes mirror the real API exactly: /api/leads and /api/tasks/pending
  // return bare arrays, not envelopes. Getting this wrong renders an empty
  // board that looks like a bug rather than a demo.
  function payloadFor(url) {
    var path = url.split('?')[0];

    if (/\/api\/tasks\/pending$/.test(path)) return TASKS;
    if (/\/api\/leads\/?$/.test(path))       return LEADS;

    // Per-lead sub-resources: /api/leads/<id>/facts | /photos | /samples ...
    var sub = path.match(/\/api\/leads\/[^/]+\/(\w[\w-]*)$/);
    if (sub) {
      if (sub[1] === 'photos')  return { photos: [] };
      if (sub[1] === 'facts')   return { checks: [], summary: 'Demo record — no audit run.' };
      if (sub[1] === 'samples') return { samples: [] };
      return { ok: true, demo: true };
    }
    if (/\/api\/leads\/[^/]+$/.test(path)) return LEADS[0];

    if (/\/api\/me$/.test(path)) return { username: 'demo', role: 'admin' };

    // Field names match renderStats() exactly. Pipeline and revenue stay at
    // zero on purpose: the proof rules forbid showing money in a public demo.
    if (/\/api\/stats$/.test(path)) {
      return {
        total: LEADS.length,
        won_count: LEADS.filter(function (l) { return l.status === 'won'; }).length,
        pipeline_value: 0,
        revenue: 0
      };
    }

    if (/\/api\/cron\/status$/.test(path)) {
      return {
        enriched_last_1h: 0,
        enriched_last_24h: 0,
        pending_count: 0,
        recent_fills: [],
        interval_seconds: 180,
        batch_size: 10
      };
    }
    if (/\/api\/campaigns\/active$/.test(path))return [];
    if (/\/api\/meetings$/.test(path))         return [];
    if (/\/api\/maps\/usage$/.test(path))      return { used: 0, limit: 0, remaining: 0 };
    if (/\/api\/gmail\/inbox/.test(path))      return { messages: [] };

    // Unknown endpoint: an empty-but-valid array keeps list views in their
    // normal empty state rather than throwing.
    return [];
  }

  var realFetch = window.fetch ? window.fetch.bind(window) : null;

  window.fetch = function (input, init) {
    var url = String((input && input.url) || input || '');
    var method = ((init && init.method) || (input && input.method) || 'GET').toUpperCase();

    // Writes are acknowledged so buttons feel alive, but never leave the page.
    if (method !== 'GET' && method !== 'HEAD') {
      console.info('[demo] write suppressed:', method, url);
      return Promise.resolve(new Response(
        JSON.stringify({ ok: true, demo: true, saved: false }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      ));
    }

    // Same-origin static assets (icons, images) load normally.
    var isAsset = /\.(png|jpe?g|svg|webp|gif|ico|css|js|webmanifest)(\?|$)/i.test(url);
    if (isAsset && realFetch) return realFetch(input, init);

    return Promise.resolve(new Response(
      JSON.stringify(payloadFor(url)),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    ));
  };

  // XHR path, in case any part of the app predates fetch.
  if (window.XMLHttpRequest) {
    var RealXHR = window.XMLHttpRequest;
    window.XMLHttpRequest = function () {
      var x = new RealXHR();
      var open = x.open, url = '';
      x.open = function (m, u) { url = String(u || ''); return open.apply(x, arguments); };
      x.send = function () {
        Object.defineProperty(x, 'readyState',   { get: function () { return 4; } });
        Object.defineProperty(x, 'status',       { get: function () { return 200; } });
        Object.defineProperty(x, 'responseText', { get: function () { return JSON.stringify(payloadFor(url)); } });
        setTimeout(function () {
          if (typeof x.onreadystatechange === 'function') x.onreadystatechange();
          if (typeof x.onload === 'function') x.onload();
        }, 0);
      };
      return x;
    };
  }

  // Storage is stubbed rather than merely cleared: anything the app writes is
  // dropped immediately, so a refresh always returns to the same empty state.
  try {
    var noStore = {
      getItem: function () { return null; },
      setItem: function () {},
      removeItem: function () {},
      clear: function () {},
      key: function () { return null; },
      length: 0
    };
    Object.defineProperty(window, 'localStorage',   { value: noStore, configurable: true });
    Object.defineProperty(window, 'sessionStorage', { value: noStore, configurable: true });
  } catch (e) { /* some browsers refuse redefinition; harmless either way */ }

  // ---------- visible status ----------
  function badge() {
    if (document.getElementById('ng-demo-badge')) return;
    var b = document.createElement('div');
    b.id = 'ng-demo-badge';
    b.textContent = 'DEMO — INVENTED RECORDS, NOTHING SAVES';
    b.setAttribute('role', 'status');
    b.style.cssText = [
      'position:fixed', 'z-index:99999', 'left:50%', 'bottom:14px',
      'transform:translateX(-50%)', 'padding:7px 14px',
      'font:600 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace',
      'letter-spacing:.14em', 'color:#fff',
      'background:rgba(10,10,14,.92)', 'border:1px solid #8115ff',
      'border-radius:2px', 'pointer-events:none', 'white-space:nowrap'
    ].join(';');
    document.body.appendChild(b);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', badge, { once: true });
  } else {
    badge();
  }

  console.info('[demo] Next Gen CRM lite — no backend, no persistence.');
}());
