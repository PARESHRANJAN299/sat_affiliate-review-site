(function () {
  'use strict';
  // Filterable product list. Every product is already in the page as plain HTML (good for Google and slow phones);
  // this script adds the tabs, filters, sorting, "show more" and the details window on top.
  var roots = document.querySelectorAll('[data-pl]');
  if (!roots.length) return;
  var hasDialog = !!(document.createElement('dialog').showModal);
  if (hasDialog) document.documentElement.classList.add('has-dialog');
  var wide = window.matchMedia ? window.matchMedia('(min-width: 900px)') : { matches: true, addEventListener: function () {} };
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var root = document.documentElement;

  function toArray(list) { return Array.prototype.slice.call(list); }
  function dec(text) { try { return decodeURIComponent(text); } catch (e) { return text; } }
  function hashValue() { return dec(String(location.hash || '').slice(1)); }
  function words(value) { return value ? String(value).split(' ').filter(Boolean) : []; }
  function readParams() {
    var out = {};
    String(location.search).replace(/^\?/, '').split('&').forEach(function (pair) {
      if (!pair) return;
      var i = pair.indexOf('=');
      var key = dec(i < 0 ? pair : pair.slice(0, i));
      var val = i < 0 ? '' : dec(pair.slice(i + 1).replace(/\+/g, ' '));
      if (key !== '__proto__') out[key] = val;
    });
    return out;
  }

  // ---------- details window (shows the full review of one product) ----------
  var dialog = null, dialogBody = null, lastFocus = null;
  function buildDialog() {
    dialog = document.createElement('dialog');
    dialog.className = 'pl-dialog';
    dialog.setAttribute('aria-label', 'Product details');
    dialog.innerHTML = '<div class="pl-dialog-bar"><button type="button" class="pl-dialog-close">Close</button></div><div class="pl-dialog-body"></div>';
    document.body.appendChild(dialog);
    dialogBody = dialog.querySelector('.pl-dialog-body');
    dialog.querySelector('.pl-dialog-close').addEventListener('click', function () { dialog.close(); });
    dialog.addEventListener('click', function (e) { if (e.target === dialog) dialog.close(); });
    dialog.addEventListener('close', function () {
      root.classList.remove('pl-lock');
      if (lastFocus && lastFocus.focus) lastFocus.focus();
    });
  }
  function openDetails(id, from) {
    var article = document.getElementById('r-' + id);
    if (!article || !document.createElement('dialog').showModal) return false;
    if (!dialog) buildDialog();
    var copy = article.cloneNode(true);
    copy.removeAttribute('id');
    dialogBody.innerHTML = '';
    dialogBody.appendChild(copy);
    lastFocus = from || document.activeElement;
    root.classList.add('pl-lock');
    dialog.showModal();
    dialogBody.scrollTop = 0;
    return true;
  }
  document.addEventListener('click', function (e) {
    var link = e.target.closest && e.target.closest('a[href^="#r-"]');
    if (!link || link.closest('.pl-dialog')) return;
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
    if (openDetails(link.getAttribute('href').slice(3), link)) e.preventDefault();
  });

  // ---------- one list ----------
  function setupTabsOnly(box) {
    // no products yet: the tabs still switch which product-type shortcuts are shown
    var tabs = toArray(box.querySelectorAll('.pl-tab'));
    if (!tabs.length) return;
    var types = toArray(box.querySelectorAll('[data-types]'));
    var heading = box.querySelector('.empty-state h2');
    var current = null;
    function select(code, focus) {
      current = code;
      tabs.forEach(function (t) {
        var on = t.getAttribute('data-seg') === code;
        t.classList.toggle('is-on', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.tabIndex = on ? 0 : -1;
        if (on && focus) t.focus();
      });
      types.forEach(function (b) { b.hidden = words(b.getAttribute('data-types')).indexOf(code) === -1; });
      if (heading) {
        var label = tabs.filter(function (t) { return t.getAttribute('data-seg') === code; })[0];
        heading.textContent = (label ? label.textContent + ': p' : 'P') + 'roducts are being researched';
      }
    }
    bindTabKeys(tabs, select);
    tabs.forEach(function (t) { t.addEventListener('click', function () { select(t.getAttribute('data-seg')); }); });
    box.classList.add('is-js');
    toArray(box.querySelectorAll('.pl-tabs')).forEach(function (n) { n.hidden = false; });
    var hash = hashValue();
    var start = tabs.filter(function (t) { return t.getAttribute('data-seg') === (readParams()['for'] || hash); })[0] || tabs[0];
    select(start.getAttribute('data-seg'));
  }
  function bindTabKeys(tabs, select) {
    tabs.forEach(function (t, i) {
      t.addEventListener('keydown', function (e) {
        var n = null;
        if (e.key === 'ArrowRight') n = (i + 1) % tabs.length;
        else if (e.key === 'ArrowLeft') n = (i - 1 + tabs.length) % tabs.length;
        else if (e.key === 'Home') n = 0;
        else if (e.key === 'End') n = tabs.length - 1;
        if (n === null) return;
        e.preventDefault();
        select(tabs[n].getAttribute('data-seg'), true);
      });
    });
  }

  function setup(box) {
    var grid = box.querySelector('[data-grid]');
    if (!grid) { setupTabsOnly(box); return; }
    var panel = box.querySelector('[data-panel]');
    var bar = box.querySelector('.pl-bar');
    var chipsBox = box.querySelector('[data-chips]');
    var countEl = box.querySelector('[data-count]');
    var sortEl = box.querySelector('[data-sort]');
    var moreBtn = box.querySelector('[data-more]');
    var emptyEl = box.querySelector('[data-empty]');
    var openBtn = box.querySelector('[data-panel-open]');
    var badgeEl = box.querySelector('[data-filter-n]');
    var showN = box.querySelector('[data-show-n]');
    var main = box.querySelector('.pl-main');
    var tabs = toArray(box.querySelectorAll('.pl-tab'));
    var types = toArray(box.querySelectorAll('[data-types]'));
    var segMode = box.getAttribute('data-segments') === '1' && tabs.length > 0;
    var limit = parseInt(box.getAttribute('data-limit'), 10) || 12;
    var groups = toArray(box.querySelectorAll('.pl-group'));
    var state = { seg: null, sel: {}, sort: 'pick', shown: limit };
    countEl.setAttribute('tabindex', '-1');

    var cards = toArray(box.querySelectorAll('.pl-card')).map(function (el) {
      var f = {};
      toArray(el.attributes).forEach(function (a) {
        if (a.name.indexOf('data-f-') === 0) f[a.name.slice(7)] = words(a.value);
      });
      f.price = [el.getAttribute('data-price')];
      f.brand = [el.getAttribute('data-brand')];
      f.type = [el.getAttribute('data-type')];
      f.aud = words(el.getAttribute('data-aud'));
      return {
        el: el, li: el.parentNode, f: f,
        pick: el.getAttribute('data-pick') === '1' ? 1 : 0,
        rank: parseInt(el.getAttribute('data-rank'), 10) || 999,
        pord: parseInt(el.getAttribute('data-pord'), 10) || 0,
        i: parseInt(el.getAttribute('data-i'), 10) || 0
      };
    });
    var labels = {};
    groups.forEach(function (g) {
      toArray(g.querySelectorAll('input')).forEach(function (inp) {
        labels[g.getAttribute('data-key') + ':' + inp.value] = inp.parentNode.querySelector('.pl-opt-t').textContent;
      });
    });

    function matches(c, ignore) {
      if (segMode && state.seg && c.f.aud.indexOf(state.seg) === -1) return false;
      return Object.keys(state.sel).every(function (key) {
        var want = state.sel[key];
        if (key === ignore || !want.length) return true;
        var have = c.f[key] || [];
        return want.some(function (v) { return have.indexOf(v) !== -1; });
      });
    }
    function totalSelected() {
      return Object.keys(state.sel).reduce(function (n, k) { return n + state.sel[k].length; }, 0);
    }
    function segLabel() {
      var t = tabs.filter(function (x) { return x.getAttribute('data-seg') === state.seg; })[0];
      return t ? t.firstChild.textContent : '';
    }

    function render() {
      var vis = cards.filter(function (c) { return matches(c); });
      var order = {
        pick: function (a, b) { return (b.pick - a.pick) || (a.rank - b.rank) || (a.i - b.i); },
        'price-asc': function (a, b) { return (a.pord - b.pord) || (b.pick - a.pick) || (a.rank - b.rank) || (a.i - b.i); },
        'price-desc': function (a, b) { return (b.pord - a.pord) || (b.pick - a.pick) || (a.rank - b.rank) || (a.i - b.i); }
      }[state.sort];
      vis.sort(order);
      var visSet = {};
      vis.forEach(function (c, n) {
        visSet[c.i] = true;
        c.li.hidden = n >= state.shown;
        grid.appendChild(c.li);
      });
      cards.forEach(function (c) { if (!visSet[c.i]) { c.li.hidden = true; grid.appendChild(c.li); } });

      // counts next to each option: how many products you would get by ticking it
      groups.forEach(function (g) {
        var key = g.getAttribute('data-key');
        var visible = 0;
        toArray(g.querySelectorAll('.pl-opt')).forEach(function (lab) {
          var inp = lab.querySelector('input');
          var n = cards.filter(function (c) { return matches(c, key) && (c.f[key] || []).indexOf(inp.value) !== -1; }).length;
          lab.querySelector('.pl-n').textContent = n;
          lab.hidden = n === 0 && !inp.checked;
          if (!lab.hidden) visible += 1;
        });
        g.hidden = visible < 2 && !(state.sel[key] && state.sel[key].length);
      });
      tabs.forEach(function (t) {
        var code = t.getAttribute('data-seg');
        var n = cards.filter(function (c) {
          return c.f.aud.indexOf(code) !== -1 && Object.keys(state.sel).every(function (key) {
            var want = state.sel[key];
            if (!want.length) return true;
            return want.some(function (v) { return (c.f[key] || []).indexOf(v) !== -1; });
          });
        }).length;
        var badge = t.querySelector('.pl-tab-n');
        if (badge) badge.textContent = n;
      });

      var total = vis.length;
      var shownNow = Math.min(state.shown, total);
      var picked0 = totalSelected();
      countEl.textContent = !total ? (picked0 ? 'No products match these filters' : 'No products yet') : (total > shownNow ? 'Showing ' + shownNow + ' of ' + total + ' products' : total + (total === 1 ? ' product' : ' products'));
      if (showN) showN.textContent = total ? 'Show ' + total + (total === 1 ? ' product' : ' products') : 'Close';
      var picked = totalSelected();
      if (badgeEl) badgeEl.textContent = picked ? '(' + picked + ')' : '';
      moreBtn.hidden = total <= state.shown;
      if (!moreBtn.hidden) moreBtn.textContent = 'Show ' + Math.min(limit, total - state.shown) + ' more';
      if (emptyEl) {
        emptyEl.hidden = total !== 0;
        if (total === 0) {
          emptyEl.innerHTML = picked
            ? 'No products match these filters. <button type="button" class="linklike" data-clear>Clear filters</button>'
            : (segMode && state.seg ? 'No ' + esc(segLabel()) + ' products yet. We add a product only after we have read the shop listing.' : 'No products yet.');
        }
      }
      // removable chips for what is ticked
      var html = '';
      Object.keys(state.sel).forEach(function (key) {
        state.sel[key].forEach(function (v) {
          html += '<button type="button" class="pl-chip" data-unset="' + esc(key) + '" data-val="' + esc(v) + '" aria-label="Remove filter ' + esc(labels[key + ':' + v] || v) + '">' +
            esc(labels[key + ':' + v] || v) + '<span aria-hidden="true">×</span></button>';
        });
      });
      if (html) html += '<button type="button" class="pl-chip pl-chip-clear" data-clear>Clear all</button>';
      chipsBox.innerHTML = html;
      chipsBox.hidden = !html;
      writeUrl();
    }
    function esc(t) {
      return String(t).replace(/[&<>"']/g, function (ch) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]; });
    }

    // ---------- URL (shareable links, no extra history entries) ----------
    function writeUrl() {
      if (!window.history || !history.replaceState) return;
      var parts = [];
      if (segMode && state.seg) parts.push('for=' + encodeURIComponent(state.seg));
      Object.keys(state.sel).forEach(function (k) {
        if (state.sel[k].length) parts.push(encodeURIComponent(k) + '=' + state.sel[k].map(encodeURIComponent).join(','));
      });
      if (state.sort !== 'pick') parts.push('sort=' + state.sort);
      history.replaceState(null, '', location.pathname + (parts.length ? '?' + parts.join('&') : '') + (/^#r-/.test(location.hash) ? location.hash : ''));
    }
    function readUrl() {
      var params = readParams();
      groups.forEach(function (g) {
        var key = g.getAttribute('data-key');
        var valid = toArray(g.querySelectorAll('input')).map(function (i) { return i.value; });
        var want = words((params[key] || '').replace(/,/g, ' ')).filter(function (v, n, all) { return valid.indexOf(v) !== -1 && all.indexOf(v) === n; });
        if (want.length) state.sel[key] = want;
      });
      if (params.sort === 'price-asc' || params.sort === 'price-desc') state.sort = params.sort;
      sortEl.value = state.sort;
      groups.forEach(function (g) {
        var key = g.getAttribute('data-key');
        toArray(g.querySelectorAll('input')).forEach(function (inp) {
          inp.checked = (state.sel[key] || []).indexOf(inp.value) !== -1;
        });
      });
      if (segMode) {
        var hash = hashValue();
        var want = params['for'] || hash;
        var tab = tabs.filter(function (t) { return t.getAttribute('data-seg') === want; })[0];
        if (!tab) {
          tab = tabs.filter(function (t) { return cards.some(function (c) { return c.f.aud.indexOf(t.getAttribute('data-seg')) !== -1; }); })[0] || tabs[0];
        }
        state.seg = tab.getAttribute('data-seg');
      }
    }

    // ---------- segment tabs ----------
    function selectSeg(code, focus) {
      state.seg = code;
      state.shown = limit;
      tabs.forEach(function (t) {
        var on = t.getAttribute('data-seg') === code;
        t.classList.toggle('is-on', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
        t.tabIndex = on ? 0 : -1;
        if (on) { main.setAttribute('aria-labelledby', t.id); if (focus) t.focus(); }
      });
      types.forEach(function (b) { b.hidden = words(b.getAttribute('data-types')).indexOf(code) === -1; });
      render();
    }

    // ---------- filter panel: sidebar on desktop, bottom sheet on phones ----------
    var scrim = document.createElement('div');
    scrim.className = 'pl-scrim';
    scrim.hidden = true;
    box.appendChild(scrim);
    function openPanel() {
      panel.classList.add('is-open');
      scrim.hidden = false;
      root.classList.add('pl-lock');
      if (!wide.matches) {
        panel.setAttribute('role', 'dialog');
        panel.setAttribute('aria-modal', 'true');
        panel.setAttribute('aria-label', 'Filters');
      }
      if (openBtn) openBtn.setAttribute('aria-expanded', 'true');
      var close = panel.querySelector('.pl-panel-close');
      if (close) close.focus();
    }
    function closePanel(quiet) {
      if (!panel.classList.contains('is-open')) return;
      panel.classList.remove('is-open');
      scrim.hidden = true;
      root.classList.remove('pl-lock');
      panel.removeAttribute('role');
      panel.removeAttribute('aria-modal');
      panel.removeAttribute('aria-label');
      if (openBtn) openBtn.setAttribute('aria-expanded', 'false');
      if (openBtn && quiet !== true) openBtn.focus();
    }
    function trapTab(e) {
      if (e.key !== 'Tab' || !panel.classList.contains('is-open') || wide.matches) return;
      var f = toArray(panel.querySelectorAll('button, input, summary')).filter(function (el) { return !el.disabled && el.offsetParent !== null; });
      if (!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      else if (panel.contains(document.activeElement) === false) { e.preventDefault(); first.focus(); }
    }
    function afterClear() {
      var chip = chipsBox.querySelector('.pl-chip');
      var target = chip || (openBtn && openBtn.offsetParent !== null ? openBtn : countEl);
      if (target && target.focus) target.focus();
    }
    if (wide.addEventListener) wide.addEventListener('change', function () { if (wide.matches) closePanel(true); });
    if (openBtn) openBtn.setAttribute('aria-expanded', 'false');
    if (openBtn) openBtn.addEventListener('click', openPanel);
    scrim.addEventListener('click', closePanel);
    toArray(box.querySelectorAll('[data-panel-close]')).forEach(function (b) { b.addEventListener('click', closePanel); });
    box.addEventListener('keydown', function (e) { if (e.key === 'Escape') closePanel(); trapTab(e); });

    // ---------- events ----------
    panel.addEventListener('change', function (e) {
      var inp = e.target;
      if (!inp.name) return;
      var list = (state.sel[inp.name] || []).filter(function (v) { return v !== inp.value; });
      if (inp.checked) list.push(inp.value);
      state.sel[inp.name] = list;
      state.shown = limit;
      render();
    });
    sortEl.addEventListener('change', function () { state.sort = sortEl.value; state.shown = limit; render(); });
    moreBtn.addEventListener('click', function () {
      var before = state.shown;
      state.shown += limit;
      render();
      var next = grid.querySelectorAll('.pl-item:not([hidden])')[before];
      if (next) { var link = next.querySelector('a'); if (link) link.focus({ preventScroll: reduce }); }
    });
    box.addEventListener('click', function (e) {
      var unset = e.target.closest('[data-unset]');
      if (unset) {
        var key = unset.getAttribute('data-unset'), val = unset.getAttribute('data-val');
        state.sel[key] = (state.sel[key] || []).filter(function (v) { return v !== val; });
        var inp = panel.querySelector('input[name="' + key + '"][value="' + val + '"]');
        if (inp) inp.checked = false;
        state.shown = limit;
        render();
        afterClear();
        return;
      }
      if (e.target.closest('[data-clear]')) {
        state.sel = {};
        toArray(panel.querySelectorAll('input')).forEach(function (i) { i.checked = false; });
        state.shown = limit;
        render();
        afterClear();
      }
    });
    if (segMode) {
      tabs.forEach(function (t) { t.addEventListener('click', function () { selectSeg(t.getAttribute('data-seg')); }); });
      bindTabKeys(tabs, selectSeg);
      toArray(box.querySelectorAll('.pl-tabs')).forEach(function (n) { n.hidden = false; });
      main.setAttribute('role', 'tabpanel');
    }

    // keep the toolbar just under the site header (which can hide on phones while you read)
    var header = document.querySelector('.site-header');
    function syncTop() {
      if (!header) return;
      var sticky = window.getComputedStyle(header).position === 'sticky';
      var hidden = header.classList.contains('is-hidden');
      box.style.setProperty('--pl-top', (sticky && !hidden ? Math.round(header.getBoundingClientRect().height) : 0) + 'px');
    }
    if (header) {
      syncTop();
      window.addEventListener('resize', syncTop, { passive: true });
      if (window.MutationObserver) new MutationObserver(syncTop).observe(header, { attributes: true, attributeFilter: ['class'] });
    }

    readUrl();
    box.classList.add('is-js');
    bar.hidden = false;
    panel.hidden = false;
    if (segMode) selectSeg(state.seg); else render();

    // used by links like #r-<id> (search results, shared links): show that product, then open its details
    box._pl = {
      reveal: function (id) {
        var card = cards.filter(function (c) { return c.el.getAttribute('data-id') === id; })[0];
        if (!card) return false;
        if (segMode && state.seg && card.f.aud.indexOf(state.seg) === -1 && card.f.aud.length) selectSeg(card.f.aud[0]);
        if (!matches(card)) {
          state.sel = {};
          toArray(panel.querySelectorAll('input')).forEach(function (i) { i.checked = false; });
        }
        state.shown = Math.max(state.shown, cards.length);
        render();
        card.el.scrollIntoView({ block: 'center' });
        return true;
      }
    };
  }

  function openFromHash() {
    var m = /^r-(.+)$/.exec(hashValue());
    if (!m) return;
    var done = false;
    toArray(roots).forEach(function (box) { if (!done && box._pl && box._pl.reveal(m[1])) done = true; });
    if (done || document.getElementById('r-' + m[1])) openDetails(m[1], null);
  }

  toArray(roots).forEach(function (box) {
    try { setup(box); } catch (err) { /* leave the plain list in place */ }
  });
  openFromHash();
  window.addEventListener('hashchange', openFromHash);
})();
