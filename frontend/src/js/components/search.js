(function () {
  'use strict';
  // Site search engine and UI. It loads the first time someone opens search (or on /search/).
  // The index is a static JSON file built with the site and searched inside the browser,
  // so typed words never leave the page.
  var opener = document.querySelector('[data-search-index]');
  if (!opener || !window.fetch || !window.Promise || window.SATSearch) return;
  var indexUrl = opener.getAttribute('data-search-index');
  if (!indexUrl) return;

  var STOP = {};
  ('a an and are at best buy find for from between i in is me my need of on or show some the to want with ' +
   'good cheap cheapest looking get give list please under below within upto less than max maximum budget price ' +
   'rs inr rupee rupees rupaye only around approx about her him ml kg kgs g gm gms cm mm l ltr litre litres mah gb pcs')
    .split(' ').forEach(function (w) { STOP[w] = 1; });
  ('के का की में से और सबसे अच्छा अच्छी अच्छे बेस्ट खरीदें कम तक चाहिए दिखाएं ' +
   'சிறந்த வாங்க மற்றும் உள்ள வேண்டும் காட்டு').split(' ').forEach(function (w) { STOP[w] = 1; });
  var SYN = {
    'घड़ी': 'watch', 'घड़ियाँ': 'watch', 'घडी': 'watch', 'घड़ियां': 'watch', 'கடிகாரம்': 'watch', 'கடிகாரங்கள்': 'watch',
    'पुरुष': 'men', 'पुरुषों': 'men', 'मर्द': 'men', 'आदमी': 'men', 'ஆண்': 'men', 'ஆண்கள்': 'men', 'ஆண்களுக்கு': 'men',
    'महिला': 'women', 'महिलाओं': 'women', 'औरत': 'women', 'लड़की': 'women', 'लड़कियों': 'women', 'பெண்': 'women', 'பெண்கள்': 'women', 'பெண்களுக்கு': 'women',
    watches: 'watch', wristwatch: 'watch', wristwatches: 'watch', timepiece: 'watch', timepieces: 'watch',
    gents: 'men', gent: 'men', male: 'men', males: 'men', mens: 'men', man: 'men', boys: 'men', boy: 'men', guys: 'men',
    ladies: 'women', lady: 'women', female: 'women', females: 'women', womens: 'women', woman: 'women', girls: 'women', girl: 'women',
    sunblock: 'sunscreen', spf: 'sunscreen',
    trainers: 'shoe', sneakers: 'shoe', sneaker: 'shoe', footwear: 'shoe',
    tshirt: 'tshirt', tshirts: 'tshirt', tee: 'tshirt', tees: 'tshirt'
  };
  var UNITS = '(?:ml|g|gm|gms|kg|kgs|w|watt|watts|l|ltr|litre|litres|cm|mm|inch|inches|mah|gb|pcs|pack|piece|pieces)';
  Object.keys(SYN).forEach(function (k) { var n = k.normalize('NFD'); if (n !== k) SYN[n] = SYN[k]; });
  Object.keys(STOP).forEach(function (k) { var n = k.normalize('NFD'); if (n !== k) STOP[n] = 1; });
  var KIND_WEIGHT = { 'Product': 5, 'Watch list': 4.5, 'Product type': 3.2, 'Guide': 3, 'Brand': 2.4, 'Style': 2, 'Category': 2.2, 'FAQ': 1.6, 'Page': 1 };
  var KIND_HUE = { 'Product': 22, 'Watch list': 38, 'Product type': 212, 'Guide': 160, 'Brand': 340, 'Style': 285, 'Category': 262, 'FAQ': 190, 'Page': 200 };
  var KIND_ICON = {
    'Product': '<path d="M20.6 13.4l-7.2 7.2a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.2"/>',
    'Watch list': '<circle cx="12" cy="12" r="5"/><path d="M12 9.5V12l1.8 1.2M9 3h6l-.8 4h-4.4zM9 21h6l-.8-4h-4.4z"/>',
    'Product type': '<rect x="4" y="4" width="7" height="7" rx="1.5"/><rect x="13" y="4" width="7" height="7" rx="1.5"/><rect x="4" y="13" width="7" height="7" rx="1.5"/><rect x="13" y="13" width="7" height="7" rx="1.5"/>',
    'Guide': '<path d="M5 4h9a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM17 8h2v12h-2"/><path d="M9 9h5M9 13h5"/>',
    'Brand': '<path d="M12 3l2.7 5.6 6.1.8-4.5 4.2 1.1 6.1L12 16.8 6.6 19.7l1.1-6.1L3.2 9.4l6.1-.8z"/>',
    'Style': '<path d="M12 3a9 9 0 1 0 0 18c1.4 0 2-1 1.5-2.2-.5-1.2.2-2.3 1.5-2.3H17a4 4 0 0 0 4-4C21 6.7 17 3 12 3z"/><circle cx="7.5" cy="11" r="1"/><circle cx="10" cy="7" r="1"/><circle cx="14.5" cy="7" r="1"/>',
    'Category': '<path d="M12 3l9 5-9 5-9-5zM3 13l9 5 9-5"/>',
    'FAQ': '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01"/>',
    'Page': '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/>'
  };
  var uid = 0;
  var LP = /^\/(hi|ta)(\/|$)/.test(location.pathname) ? '/' + location.pathname.split('/')[1] : '';
  var INDIC = '\u0900-\u097f\u0b80-\u0bff\u200c\u200d';
  var NONWORD = new RegExp('[^a-z0-9' + INDIC + ']+', 'g');
  var data = null;
  var loading = null;

  function esc(t) {
    return String(t).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function rupees(n) { return '₹' + Number(n).toLocaleString('en-IN'); }
  function isNum(w) { return /^\d+$/.test(w); }

  // ---------- words ----------
  function stem(w) {
    if (SYN[w]) return SYN[w];
    if (w.length > 3 && w.charAt(w.length - 1) === 's' && w.charAt(w.length - 2) !== 's') {
      var s = w.slice(0, -1);
      return SYN[s] || s;
    }
    return w;
  }
  function words(text) {
    var clean = String(text).normalize('NFD').toLowerCase().replace(/(\d),(?=\d)/g, '$1')
      .replace(/['’]s\b/g, '').replace(/\bt[\s-]+shirts?\b/g, 'tshirt').replace(NONWORD, ' ').trim();
    if (!clean) return [];
    return clean.split(' ').map(stem);
  }
  // one edit apart: a replaced, added or dropped letter, or two neighbouring letters swapped
  function nearWord(a, b) {
    var la = a.length, lb = b.length, i;
    if (Math.abs(la - lb) > 1) return false;
    if (la === lb) {
      var diff = [];
      for (i = 0; i < la; i++) if (a.charAt(i) !== b.charAt(i)) { diff.push(i); if (diff.length > 2) return false; }
      if (diff.length === 1) return true;
      return diff.length === 2 && diff[1] === diff[0] + 1 &&
        a.charAt(diff[0]) === b.charAt(diff[1]) && a.charAt(diff[1]) === b.charAt(diff[0]);
    }
    var s = la < lb ? a : b, l = la < lb ? b : a;
    for (i = 0; i < l.length; i++) if (l.slice(0, i) + l.slice(i + 1) === s) return true;
    return false;
  }

  // ---------- reading the query: budget, gender, keywords ----------
  function moneyValue(num, unit) {
    var n = parseFloat(num);
    if (unit === 'k' || unit === 'thousand') n *= 1000;
    else if (unit === 'l' || unit === 'lakh' || unit === 'lac') n *= 100000;
    return Math.round(n);
  }
  function parseQuery(raw) {
    var q = ' ' + String(raw).normalize('NFD').toLowerCase().replace(/(\d),(?=\d)/g, '$1') + ' ';
    var budget = null, min = null;
    var cur = '(?:₹|rs\\.?|inr)?\\s*';
    var amount = '(\\d+(?:\\.\\d+)?)\\s*(k|thousand|lakh|lac|l)?(?![a-z0-9])';
    var forms = [
      { re: new RegExp('(?:^|[^a-z0-9.])' + cur + '(\\d+(?:\\.\\d+)?)\\s*(k|thousand|lakh|lac)?\\s*(?:-|–|to|and)\\s*' + cur + amount), type: 'range' },
      { re: new RegExp('(?:(?:^|[^a-z])(?:above|over|more than|minimum|min|at least|starting from)(?![a-z])|>=?)\\s*' + cur + amount), type: 'min' },
      { re: new RegExp('(?:(?:^|[^a-z])(?:under|below|upto|up to|within|less than|lesser than|max|maximum|budget of|budget)(?![a-z])|<=?)\\s*' + cur + amount), type: 'max' },
      { re: new RegExp('(?:₹|(?:^|[^a-z])rs\\.?|(?:^|[^a-z])inr)\\s*' + amount), type: 'max' },
      { re: new RegExp('(?:^|[^a-z0-9.])(\\d+(?:\\.\\d+)?)\\s*(k|thousand|lakh|lac)?\\s*(?:rupees?|rs|inr)(?![a-z])'), type: 'max' },
      { re: /(?:^|[^a-z0-9.])(\d+(?:\.\d+)?)\s*(k|thousand|lakh|lac)(?![a-z0-9])/, type: 'max' },
      { re: new RegExp('(?:^|[^a-z0-9.])(\\d+(?:\\.\\d+)?)\\s*(k|thousand|lakh|lac)?\\s*(?:\u0938\u0947 \u0915\u092e|\u0915\u0947 \u0905\u0902\u0926\u0930|\u0915\u0947 \u092d\u0940\u0924\u0930|\u0924\u0915|\u0b95\u0bcd\u0b95\u0bc1\u0bb3\u0bcd|\u0b95\u0bc1\u0bb3\u0bcd|\u0b95\u0bcd\u0b95\u0bc1 \u0b95\u0bc0\u0bb4\u0bcd|\u0b95\u0bc0\u0bb4\u0bcd|\u0bb5\u0bb0\u0bc8)'), type: 'max' },
      { re: new RegExp('(?:^|[\\s(/\\-])(\\d{3,7})(?![a-z0-9.])()(?!\\s*' + UNITS + '(?![a-z]))'), type: 'max' }
    ];
    for (var i = 0; i < forms.length; i++) {
      var f = forms[i];
      if (f.type === 'max' && budget !== null) continue;
      if (f.type === 'min' && min !== null) continue;
      if (f.type === 'range' && budget !== null) continue;
      var m = f.re.exec(q);
      if (!m) continue;
      var v, ok = false;
      if (f.type === 'range') {
        var a = moneyValue(m[1], m[2]), b = moneyValue(m[3], m[4]);
        if (a >= 100 && b >= 100 && a <= 10000000 && b <= 10000000) { min = Math.min(a, b); budget = Math.max(a, b); ok = true; }
      } else {
        v = moneyValue(m[1], m[2]);
        if (v >= 100 && v <= 10000000) {
          if (f.type === 'min') min = v; else budget = v;
          ok = true;
        }
      }
      if (ok) { q = q.slice(0, m.index) + ' ' + q.slice(m.index + m[0].length); }
    }
    var toks = [], nums = [], gender = null, seen = {};
    words(q).forEach(function (w) {
      if (!w || w.length < 2 && !isNum(w) || STOP[w] || seen[w]) return;
      seen[w] = 1;
      if (w === 'men' || w === 'women') { gender = gender && gender !== w ? 'both' : w; return; }
      (isNum(w) ? nums : toks).push(w);
    });
    if (gender === 'both') gender = null;
    if (!toks.length && nums.length) { toks = nums; nums = []; }
    return { raw: raw, tokens: toks, nums: nums, budget: budget, min: min, gender: gender, fixes: [] };
  }

  // ---------- matching ----------
  function prepare(json) {
    var vocab = {};
    json.e.forEach(function (e) {
      e.tw = words(e.t);
      e.xw = words((e.x || '') + ' ' + (e.c || '') + ' ' + (e.k || '') + (e.g ? ' ' + e.g : ''));
      e.dw = words(e.d || '');
      e.tw.concat(e.xw).forEach(function (w) { vocab[w] = 1; });
      // pages with no gender field can still say "for Men" or "for Women" in their title
      e.gg = e.g || (e.tw.indexOf('women') > -1 ? 'women' : (e.tw.indexOf('men') > -1 ? 'men' : ''));
    });
    json.vocab = Object.keys(vocab);
    return json;
  }
  function fieldScore(tok, ws, exact, prefix) {
    var best = 0, numeric = isNum(tok);
    for (var i = 0; i < ws.length; i++) {
      var w = ws[i];
      if (w === tok) return exact;
      if (!numeric && tok.length >= 2 && w.indexOf(tok) === 0) best = Math.max(best, prefix);
    }
    return best;
  }
  function tokenScore(tok, e) {
    return Math.max(fieldScore(tok, e.tw, 6, 4), fieldScore(tok, e.xw, 4, 2.6), fieldScore(tok, e.dw, 2, 1.2));
  }
  // a word that is nowhere in the index is replaced by the closest word that is
  function correct(p) {
    p.tokens = p.tokens.map(function (t) {
      if (t.length < 4 || isNum(t)) return t;
      var known = data.vocab.some(function (w) { return w.indexOf(t) === 0; });
      if (known) return t;
      var best = null;
      data.vocab.forEach(function (w) {
        if (w.charAt(0) === t.charAt(0) && nearWord(t, w) &&
            (!best || Math.abs(w.length - t.length) < Math.abs(best.length - t.length))) best = w;
      });
      if (best) { p.fixes.push(best); return best; }
      return t;
    });
  }
  function search(raw) {
    var p = parseQuery(raw);
    var out = { p: p, items: [], related: false, note: '' };
    var constrained = p.budget !== null || p.min !== null || !!p.gender;
    if (!p.tokens.length && !constrained) return out;
    correct(p);
    var strict = [], loose = [], over = [];
    data.e.forEach(function (e) {
      if (p.gender && e.gg && e.gg !== p.gender) return;
      if (p.budget !== null && e.m && e.m > p.budget) { over.push(e); return; }
      if (p.min !== null && e.m && e.m <= p.min) return;
      var hits = 0, total = 0;
      p.tokens.forEach(function (t) {
        var s = tokenScore(t, e);
        if (s > 0) hits++;
        total += s;
      });
      p.nums.forEach(function (n) { if (e.tw.indexOf(n) > -1 || e.dw.indexOf(n) > -1) total += 1.5; });
      var base = total + (KIND_WEIGHT[e.k] || 1) * 0.8;
      if (p.budget !== null && e.m) base += 4 * (e.m / p.budget);
      if (p.gender) base += e.gg === p.gender ? 1.5 : -1.2;
      if (e.k === 'Category' && p.tokens.length && p.tokens.every(function (t) { return e.tw.indexOf(t) > -1; })) base += 3;
      if (p.tokens.length) {
        if (hits === p.tokens.length) strict.push({ e: e, s: base });
        else if (hits > 0) loose.push({ e: e, s: base - 3 });
      } else {
        var fits = (p.budget === null && p.min === null ? true : !!e.m) && (p.gender ? e.gg === p.gender : true);
        if (fits) strict.push({ e: e, s: base });
      }
    });
    function byScore(a, b) { return (b.s - a.s) || ((a.e.m || 0) - (b.e.m || 0)) || a.e.t.localeCompare(b.e.t); }
    strict.sort(byScore); loose.sort(byScore);
    if (strict.length) out.items = strict;
    else if (loose.length) { out.items = loose; out.related = true; }
    if (p.budget !== null && !out.items.some(function (r) { return r.e.m; }) && over.length) {
      var cheapest = over.filter(function (e) {
        return p.tokens.every(function (t) { return tokenScore(t, e) > 0; });
      }).sort(function (a, b) { return a.m - b.m; });
      if (cheapest.length) {
        out.note = __('Nothing is listed under {budget} yet. The closest list starts at {start}.', { budget: rupees(p.budget), start: rupees(cheapest[0].m) });
        out.items = cheapest.filter(function (e) { return e.m === cheapest[0].m; }).map(function (e) { return { e: e, s: 1 }; });
      }
    }
    out.items = out.items.slice(0, 12);
    return out;
  }

  // ---------- markup ----------
  function iconTile(kind) {
    return '<span class="sx-tile" style="--hue:' + (KIND_HUE[kind] || 210) + '" aria-hidden="true">' +
      '<svg class="sx-ic" viewBox="0 0 24 24">' + (KIND_ICON[kind] || KIND_ICON.Page) + '</svg></span>';
  }
  function highlight(text, p) {
    var raw = String(text);
    var parts = {};
    String(p.raw).toLowerCase().split(NONWORD).forEach(function (w) { if (w.length > 1 && !STOP[w] && !isNum(w)) parts[w] = 1; });
    p.tokens.forEach(function (w) { if (!isNum(w)) parts[w] = 1; });
    var list = Object.keys(parts).sort(function (a, b) { return b.length - a.length; })
      .map(function (w) { return w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); });
    if (!list.length) return esc(raw);
    var re = new RegExp('(^|[^a-z0-9' + INDIC + '])(' + list.join('|') + ')', 'ig');
    var out = '', last = 0, m;
    while ((m = re.exec(raw))) {
      var start = m.index + m[1].length;
      out += esc(raw.slice(last, start)) + '<mark>' + esc(m[2]) + '</mark>';
      last = start + m[2].length;
    }
    return out + esc(raw.slice(last));
  }
  function resultHtml(r, id, p) {
    var e = r.e;
    var sub = [__(e.k)];
    if (e.c && e.c !== e.t) sub.push(e.c);
    var chips = '';
    if (e.m) chips += '<span class="sx-pill">' + esc(__('Up to {n}', { n: rupees(e.m) })) + '</span>';
    if (e.s) chips += '<span class="sx-pill sx-pill-soon">' + esc(__('Being researched')) + '</span>';
    return '<li role="presentation"><a class="sx-row" role="option" id="' + id + '" href="' + esc(e.u) + '" tabindex="-1" aria-selected="false">' +
      iconTile(e.k) +
      '<span class="sx-text"><span class="sx-title">' + highlight(e.t, p) + '</span>' +
      '<span class="sx-sub">' + esc(sub.join(' · ')) + '</span>' +
      (chips ? '<span class="sx-chips">' + chips + '</span>' : '') + '</span>' +
      '<svg class="sx-go" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a></li>';
  }
  function readingOf(p) {
    var bits = [];
    if (p.min !== null && p.budget !== null) bits.push(__('{a} to {b}', { a: rupees(p.min), b: rupees(p.budget) }));
    else if (p.budget !== null) bits.push(__('up to {n}', { n: rupees(p.budget) }));
    else if (p.min !== null) bits.push(__('above {n}', { n: rupees(p.min) }));
    if (p.gender) bits.push(p.gender === 'men' ? __('men') : __('women'));
    return bits;
  }

  // ---------- one search panel (used in the overlay and on /search/) ----------
  function Panel(host, opts) {
    var n = ++uid;
    var self = this;
    this.opts = opts || {};
    this.listId = 'sx-list-' + n;
    host.innerHTML =
      '<div class="sx-panel">' +
      '<form class="sx-form" role="search" action="' + LP + '/search/" method="get">' +
      '<svg class="sx-lens" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.5-4.5"/></svg>' +
      '<input class="sx-input" type="search" name="q" role="combobox" aria-expanded="false" aria-controls="' + this.listId + '"' +
      ' aria-autocomplete="list" aria-label="' + esc(__('Search SAT')) + '" placeholder="' + esc(__('Search products, guides, categories')) + '" autocomplete="off"' +
      ' autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="search" maxlength="80">' +
      '<button class="sx-clear" type="button" aria-label="' + esc(__('Clear search')) + '" hidden><svg class="sx-ic" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button>' +
      '</form>' +
      '<div class="sx-read" aria-hidden="true" hidden></div>' +
      '<p class="sx-status" role="status" aria-live="polite"></p>' +
      '<ul class="sx-list" id="' + this.listId + '" role="listbox" aria-label="' + esc(__('Search results')) + '" hidden></ul>' +
      '<div class="sx-home"></div>' +
      '</div>';
    this.form = host.querySelector('.sx-form');
    this.input = host.querySelector('.sx-input');
    this.clear = host.querySelector('.sx-clear');
    this.read = host.querySelector('.sx-read');
    this.status = host.querySelector('.sx-status');
    this.list = host.querySelector('.sx-list');
    this.home = host.querySelector('.sx-home');
    this.active = -1;
    this.timer = null;
    this.typing = null;

    this.input.addEventListener('input', function () { self.schedule(); });
    this.clear.addEventListener('click', function () { self.setQuery(''); self.input.focus(); });
    this.form.addEventListener('submit', function (e) {
      e.preventDefault();
      if (self.timer) { clearTimeout(self.timer); self.timer = null; self.run(); }
      var links = self.list.querySelectorAll('a.sx-row');
      var target = links[self.active >= 0 ? self.active : 0];
      if (target) { window.location.href = target.getAttribute('href'); return; }
      var q = self.input.value.trim();
      if (q && !self.opts.inline) window.location.href = LP + '/search/?q=' + encodeURIComponent(q);
    });
    this.input.addEventListener('keydown', function (e) { self.keys(e); });
    this.home.addEventListener('click', function (e) {
      var tab = e.target.closest('[data-tab]');
      if (tab) { e.preventDefault(); self.pickTab(tab.getAttribute('data-tab'), true); return; }
      var chip = e.target.closest('[data-q]');
      if (chip) { e.preventDefault(); self.setQuery(chip.getAttribute('data-q')); self.input.focus(); }
    });
    this.home.addEventListener('keydown', function (e) {
      var tab = e.target.closest && e.target.closest('[data-tab]');
      if (!tab || (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft' && e.key !== 'Home' && e.key !== 'End')) return;
      var all = self.home.querySelectorAll('[data-tab]');
      var i = Array.prototype.indexOf.call(all, tab);
      if (e.key === 'ArrowRight') i = (i + 1) % all.length;
      else if (e.key === 'ArrowLeft') i = (i - 1 + all.length) % all.length;
      else if (e.key === 'Home') i = 0;
      else i = all.length - 1;
      e.preventDefault();
      self.pickTab(all[i].getAttribute('data-tab'), true);
    });
    this.list.addEventListener('mousemove', function (e) {
      var row = e.target.closest('a.sx-row');
      if (!row) return;
      var rows = self.list.querySelectorAll('a.sx-row');
      for (var i = 0; i < rows.length; i++) if (rows[i] === row && self.active !== i) self.setActive(i, false);
    });
  }
  Panel.prototype.setQuery = function (q) {
    this.input.value = q;
    this.run();
  };
  Panel.prototype.schedule = function () {
    var self = this;
    this.stopTyping();
    clearTimeout(this.timer);
    this.timer = setTimeout(function () { self.timer = null; self.run(); }, 60);
  };
  Panel.prototype.setActive = function (i, scroll) {
    var rows = this.list.querySelectorAll('a.sx-row');
    if (!rows.length) { this.active = -1; this.input.removeAttribute('aria-activedescendant'); return; }
    if (i < 0) i = rows.length - 1;
    if (i >= rows.length) i = 0;
    for (var k = 0; k < rows.length; k++) {
      var on = k === i;
      rows[k].classList.toggle('is-active', on);
      rows[k].setAttribute('aria-selected', on ? 'true' : 'false');
    }
    this.active = i;
    this.input.setAttribute('aria-activedescendant', rows[i].id);
    if (scroll !== false && rows[i].scrollIntoView) rows[i].scrollIntoView({ block: 'nearest' });
  };
  Panel.prototype.keys = function (e) {
    var rows = this.list.querySelectorAll('a.sx-row');
    if (e.key === 'ArrowDown' && rows.length) { e.preventDefault(); this.setActive(this.active + 1); }
    else if (e.key === 'ArrowUp' && rows.length) { e.preventDefault(); this.setActive(this.active < 0 ? rows.length - 1 : this.active - 1); }
    else if (e.key === 'Escape' && this.input.value) { e.preventDefault(); e.stopPropagation(); this.setQuery(''); }
  };
  Panel.prototype.stopTyping = function () {
    if (this.typing) { clearTimeout(this.typing); this.typing = null; }
    this.input.placeholder = __('Search products, guides, categories');
  };
  // the placeholder tries example searches, so people see what to type
  Panel.prototype.startTyping = function () {
    if (!data || !data.ex || !data.ex.length || this.input.value) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var self = this, i = 0, c = 0, del = false;
    function tick() {
      if (self.input.value || !self.typing) return;
      var full = data.ex[i % data.ex.length];
      c += del ? -1 : 1;
      self.input.placeholder = __('Try “{q}”', { q: full.slice(0, c) });
      var wait = 70;
      if (!del && c === full.length) { del = true; wait = 1500; }
      else if (del && c === 0) { del = false; i++; wait = 350; }
      else if (del) wait = 30;
      self.typing = setTimeout(tick, wait);
    }
    this.typing = setTimeout(tick, 600);
  };
  Panel.prototype.renderHome = function () {
    var self = this;
    var groups = data.kw || [];
    if (!groups.length) { this.home.innerHTML = '<p class="sx-fine">' + esc(__('Searches run in your browser.')) + '</p>'; return; }
    if (!this.tab) this.tab = groups[0].id;
    var cur = groups[0];
    groups.forEach(function (g) { if (g.id === self.tab) cur = g; });
    var tabs = groups.map(function (g) {
      var on = g.id === cur.id;
      return '<button type="button" role="tab" class="sx-tab' + (on ? ' is-on' : '') + '" data-tab="' + esc(g.id) + '" aria-selected="' + on +
        '" tabindex="' + (on ? '0' : '-1') + '" style="--hue:' + g.hue + '"><span class="sx-tab-dot" aria-hidden="true"></span>' + esc(g.label) + '</button>';
    }).join('');
    var chips = cur.q.map(function (q, i) {
      return '<button type="button" class="sx-chip" data-q="' + esc(q) + '" style="--i:' + i + '"><span class="sx-chip-dot" aria-hidden="true"></span>' + esc(q) + '</button>';
    }).join('');
    var more = cur.url ? '<a class="sx-more" href="' + esc(cur.url) + '">' + esc(__('Open {name}', { name: cur.name || cur.label })) +
      '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>' : '';
    this.home.innerHTML =
      '<p class="sx-label">' + esc(__('Browse by category')) + '</p>' +
      '<div class="sx-tabs" role="tablist" aria-label="' + esc(__('Browse by category')) + '">' + tabs + '</div>' +
      '<p class="sx-label sx-label-tight">' + (cur.id === 'popular' ? esc(__('Popular searches')) : esc(__('Search ideas in {name}', { name: cur.name || cur.label }))) + '</p>' +
      '<div class="sx-kw" style="--hue:' + cur.hue + '">' + chips + '</div>' + more +
      '<p class="sx-fine">' + esc(__('Searches run in your browser.')) + '</p>';
  };
  Panel.prototype.pickTab = function (id, focus) {
    this.tab = id;
    this.renderHome();
    var t = this.home.querySelector('.sx-tab.is-on');
    if (t && focus) t.focus();
    if (t && t.scrollIntoView) t.scrollIntoView({ inline: 'center', block: 'nearest' });
  };

  Panel.prototype.run = function () {
    var self = this;
    var raw = this.input.value;
    var trimmed = raw.trim();
    this.clear.hidden = !raw;
    if (this.opts.onQuery) this.opts.onQuery(trimmed);
    if (!data) {
      this.status.textContent = __('Loading…');
      load().then(function () { self.run(); }, function () { failed(self); });
      return;
    }
    if (!trimmed) {
      this.list.hidden = true; this.list.innerHTML = '';
      this.read.hidden = true; this.home.hidden = false;
      this.status.textContent = '';
      this.input.setAttribute('aria-expanded', 'false');
      this.input.removeAttribute('aria-activedescendant');
      this.active = -1;
      if (!this.home.firstChild) this.renderHome();
      if (!this.typing) this.startTyping();
      return;
    }
    var res = search(trimmed);
    var p = res.p;
    this.home.hidden = true;
    var bits = readingOf(p);
    var chips = [];
    if (p.budget !== null || p.min !== null) {
      var money = p.min !== null && p.budget !== null ? __('{a} to {b}', { a: rupees(p.min), b: rupees(p.budget) })
        : (p.budget !== null ? __('Up to {n}', { n: rupees(p.budget) }) : __('Above {n}', { n: rupees(p.min) }));
      chips.push('<span class="sx-read-chip sx-read-money">' + esc(money) + '</span>');
    }
    if (p.gender) chips.push('<span class="sx-read-chip">' + esc(p.gender === 'men' ? __('Men') : __('Women')) + '</span>');
    this.read.innerHTML = chips.length ? '<span class="sx-read-label">' + esc(__('Showing')) + '</span>' + chips.join('') : '';
    this.read.hidden = !chips.length;
    if (!res.items.length) {
      this.list.hidden = true; this.list.innerHTML = '';
      this.input.setAttribute('aria-expanded', 'false');
      this.input.removeAttribute('aria-activedescendant');
      this.active = -1;
      this.status.textContent = __('No match for “{q}”.', { q: trimmed });
      this.status.classList.remove('is-note');
      this.home.hidden = false;
      this.renderHome();
      return;
    }
    this.list.innerHTML = res.items.map(function (r, i) { return resultHtml(r, self.listId + '-' + i, p); }).join('');
    this.list.hidden = false;
    this.input.setAttribute('aria-expanded', 'true');
    var count = res.items.length === 1 ? __('1 result') : __('{n} results', { n: res.items.length });
    var text;
    if (res.note) text = res.note;
    else if (res.related) text = __('Closest matches');
    else text = count + (p.fixes.length ? ' ' + __('for “{q}”', { q: p.fixes.join(' ') }) : '') + (bits.length ? ', ' + bits.join(', ') : '');
    this.status.textContent = text;
    this.status.classList.toggle('is-note', !!res.note || res.related);
    this.setActive(0, false);
  };
  Panel.prototype.ready = function () {
    this.renderHome();
    this.run();
    if (!this.input.value) this.startTyping();
  };
  Panel.prototype.focus = function (select) {
    this.input.focus();
    if (select && this.input.value) this.input.select();
  };

  function load() {
    if (data) return Promise.resolve(data);
    if (!loading) {
      loading = fetch(indexUrl, { credentials: 'same-origin' })
        .then(function (r) { if (!r.ok) throw new Error('index ' + r.status); return r.json(); })
        .then(function (json) { data = prepare(json); return data; })
        .catch(function (err) { loading = null; throw err; });
    }
    return loading;
  }
  function failed(panel) {
    panel.status.textContent = __('Search could not load. Please try again.');
  }

  // ---------- the /search/ page ----------
  var pageHost = document.querySelector('[data-search-page]');
  var pagePanel = null;
  if (pageHost) {
    pagePanel = new Panel(pageHost, {
      inline: true,
      onQuery: function (q) {
        if (!window.history || !history.replaceState) return;
        var url = location.pathname + (q ? '?q=' + encodeURIComponent(q) : '');
        history.replaceState(null, '', url);
      }
    });
    var qm = /[?&]q=([^&]*)/.exec(location.search);
    if (qm) { try { pagePanel.input.value = decodeURIComponent(qm[1].replace(/\+/g, ' ')).slice(0, 80); } catch (e) { /* bad escape */ } }
    pagePanel.clear.hidden = !pagePanel.input.value;
    load().then(function () { pagePanel.ready(); if (!pagePanel.input.value) pagePanel.input.focus(); }, function () { failed(pagePanel); });
  }

  // ---------- the overlay ----------
  var overlay = null, overlayPanel = null, dialog = null, lastFocus = null;
  function tabbables() {
    return [].filter.call(overlay.querySelectorAll('button, input, a[href]'), function (el) {
      return !el.disabled && el.tabIndex >= 0 && el.offsetParent !== null;
    });
  }
  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key !== 'Tab') return;
    var f = tabbables();
    if (!f.length) { e.preventDefault(); return; }
    var first = f[0], last = f[f.length - 1], at = document.activeElement;
    if (!overlay.contains(at)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && (at === first || at === dialog)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && at === last) { e.preventDefault(); first.focus(); }
  }
  function onFocusIn(e) {
    if (overlay && !overlay.hidden && !overlay.contains(e.target)) overlayPanel.focus(false);
  }
  function build() {
    overlay = document.createElement('div');
    overlay.className = 'sx-overlay';
    overlay.hidden = true;
    overlay.innerHTML = '<div class="sx-scrim" data-close></div>' +
      '<div class="sx-dialog" role="dialog" aria-modal="true" aria-label="' + esc(__('Search SAT')) + '" tabindex="-1">' +
      '<div class="sx-dialog-head"><span class="sx-grab" aria-hidden="true"></span>' +
      '<button type="button" class="sx-close" data-close aria-label="' + esc(__('Close search')) + '"><svg class="sx-ic" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></button></div>' +
      '<div class="sx-host"></div></div>';
    document.body.appendChild(overlay);
    dialog = overlay.querySelector('.sx-dialog');
    overlayPanel = new Panel(overlay.querySelector('.sx-host'), {});
    overlay.addEventListener('click', function (e) { if (e.target.closest('[data-close]')) close(); });
    // swipe down on the sheet header closes it on phones
    var startY = null;
    var head = overlay.querySelector('.sx-dialog-head');
    head.addEventListener('touchstart', function (e) { startY = e.touches[0].clientY; }, { passive: true });
    head.addEventListener('touchend', function (e) {
      if (startY !== null && e.changedTouches[0].clientY - startY > 60) close();
      startY = null;
    }, { passive: true });
  }
  function isOpen() { return !!overlay && !overlay.hidden; }
  function open() {
    if (pagePanel) { pagePanel.focus(true); return; }
    if (!overlay) build();
    if (isOpen()) return;
    lastFocus = document.activeElement;
    var bar = window.innerWidth - document.documentElement.clientWidth;
    if (bar > 0) document.documentElement.style.paddingRight = bar + 'px';
    overlay.hidden = false;
    document.documentElement.classList.add('sx-lock');
    opener.setAttribute('aria-expanded', 'true');
    document.addEventListener('keydown', onKey);
    document.addEventListener('focusin', onFocusIn);
    // let the element paint before the entrance animation class lands
    window.requestAnimationFrame(function () { overlay.classList.add('is-open'); });
    overlayPanel.focus(true);
    if (data) overlayPanel.ready();
    else load().then(function () { overlayPanel.ready(); }, function () { failed(overlayPanel); });
  }
  function close() {
    if (!isOpen()) return;
    overlayPanel.stopTyping();
    overlay.classList.remove('is-open');
    overlay.hidden = true;
    document.documentElement.classList.remove('sx-lock');
    document.documentElement.style.paddingRight = '';
    opener.setAttribute('aria-expanded', 'false');
    document.removeEventListener('keydown', onKey);
    document.removeEventListener('focusin', onFocusIn);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  window.SATSearch = {
    open: open,
    close: close,
    toggle: function () { isOpen() ? close() : open(); },
    warm: function () { load().catch(function () { /* retried on open */ }); },
    isOpen: isOpen
  };
})();
