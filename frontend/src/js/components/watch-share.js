(function () {
  'use strict';
  // Share a watch. Every card and product page carries <a data-share-open href="https://wa.me/?text=..."> made at build time, so WhatsApp works
  // without JavaScript. This script turns a click into the "Share this watch" sheet (WhatsApp, Copy link, More), always sharing the SAT product
  // page address from data-share-url, never the shop link. Nothing here may break the page: every step is guarded.
  var sheet = null, current = null, trigger = null, closing = null, timer = null;

  // analytics: Cloudflare Web Analytics (the only provider) counts page views only, so events go out as a window event any later hook can
  // listen for, and into window.dataLayer when the page already has one. Only the product id, brand and page type are sent; no personal data.
  function sourceOf(el) {
    if (el.closest('.watch-pdp-info')) return 'product_page';
    if (el.closest('.watch-pdp-wrap')) return 'product_page_card';
    return /^\/watches\/?$/.test(location.pathname) ? 'hub_card' : 'collection_card';
  }
  function track(name, item) {
    try {
      var data = { product_id: item.id, brand: item.brand, source: item.source };
      window.dispatchEvent(new CustomEvent('sat:analytics', { detail: { event: name, product_id: data.product_id, brand: data.brand, source: data.source } }));
      if (window.dataLayer && typeof window.dataLayer.push === 'function') window.dataLayer.push({ event: name, product_id: data.product_id, brand: data.brand, source: data.source });
    } catch (e) { /* analytics must never break sharing */ }
  }

  function el(tag, cls, html) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (html) node.innerHTML = html;
    return node;
  }
  var ICON_WA = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path class="ws-bubble" d="M12 2.8a9.1 9.1 0 0 0-7.8 13.7L2.9 21.1l4.7-1.2A9.1 9.1 0 1 0 12 2.8z"/><path class="ws-handset" transform="translate(6.6 6.6) scale(.45)" d="M6.6 10.8c1.4 2.8 3.8 5.1 6.6 6.6l2.2-2.2c.3-.3.7-.4 1-.2 1.1.4 2.3.6 3.6.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C10.6 21 3 13.4 3 4c0-.6.4-1 1-1h3.5c.6 0 1 .4 1 1 0 1.3.2 2.5.6 3.6.1.3 0 .7-.2 1l-2.3 2.2z"/></svg>';
  var ICON_COPY = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6.5A2.5 2.5 0 0 1 7.5 4H15"/></svg>';
  var ICON_MORE = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="5.5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="18.5" cy="12" r="1.6"/></svg>';
  var ICON_X = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M6 6l12 12M18 6L6 18"/></svg>';

  function build() {
    var dialog = el('dialog', 'watch-share-sheet');
    dialog.setAttribute('aria-labelledby', 'watch-share-title');
    dialog.innerHTML =
      '<div class="ws-inner"><span class="ws-grip" aria-hidden="true"></span>' +
      '<div class="ws-head"><div><h2 class="ws-title" id="watch-share-title">Share this watch</h2><p class="ws-name" data-ws-name></p></div>' +
      '<button type="button" class="ws-close" data-ws-close aria-label="Close">' + ICON_X + '</button></div>' +
      '<ul class="ws-list">' +
      '<li><a class="ws-item ws-primary" data-ws-whatsapp target="_blank" rel="noopener noreferrer">' + ICON_WA + '<span>WhatsApp</span></a></li>' +
      '<li><button type="button" class="ws-item" data-ws-copy>' + ICON_COPY + '<span>Copy link</span></button></li>' +
      '<li><button type="button" class="ws-item" data-ws-more hidden>' + ICON_MORE + '<span>More</span></button></li>' +
      '</ul><p class="ws-status" role="status" aria-live="polite" data-ws-status></p></div>';
    document.body.appendChild(dialog);
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog) close();                 // a tap on the dimmed area (the dialog box itself) closes it
      var hit = event.target.closest ? event.target : event.target.parentNode;
      if (hit.closest('[data-ws-close]')) close();
      else if (hit.closest('[data-ws-whatsapp]')) { if (current) track('product_share_whatsapp', current); window.setTimeout(close, 150); }
      else if (hit.closest('[data-ws-copy]')) copy();
      else if (hit.closest('[data-ws-more]')) more();
    });
    dialog.addEventListener('cancel', function (event) { event.preventDefault(); close(); });   // Escape: close with the same slide-down
    dialog.addEventListener('close', finish);
    dialog.addEventListener('keydown', function (event) {   // for a browser without <dialog>
      if (event.key === 'Escape') { event.preventDefault(); close(); }
    });
    return dialog;
  }

  function say(text) {
    var status = sheet && sheet.querySelector('[data-ws-status]');
    if (!status) return;
    status.textContent = '';
    window.setTimeout(function () { status.textContent = text; }, 40);   // a fresh node text is announced again by screen readers
    window.clearTimeout(timer);
    timer = window.setTimeout(function () { if (status) status.textContent = ''; }, 3500);
  }

  function open(link) {
    if (!sheet) sheet = build();
    trigger = link;
    current = { id: link.getAttribute('data-share-product') || '', brand: link.getAttribute('data-share-brand') || '', name: link.getAttribute('data-share-name') || '',
                url: link.getAttribute('data-share-url') || '', wa: link.getAttribute('href') || '', source: sourceOf(link) };
    sheet.querySelector('[data-ws-name]').textContent = current.name;
    sheet.querySelector('[data-ws-whatsapp]').setAttribute('href', current.wa);
    sheet.querySelector('[data-ws-more]').hidden = typeof navigator.share !== 'function';
    sheet.querySelector('[data-ws-status]').textContent = '';
    sheet.classList.remove('is-closing');
    window.clearTimeout(closing);
    if (!sheet.open) {
      if (typeof sheet.showModal === 'function') sheet.showModal(); else sheet.setAttribute('open', '');
    }
    document.documentElement.classList.add('watch-share-open');
    var first = sheet.querySelector('[data-ws-whatsapp]');
    try { first.focus({ preventScroll: true }); } catch (e) { first.focus(); }
    track('product_share_open', current);
  }

  function close() {
    if (!sheet || !sheet.open) return;
    var still = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (still) { hide(); return; }
    sheet.classList.add('is-closing');
    window.clearTimeout(closing);
    closing = window.setTimeout(hide, 210);   // let the slide-down play, then really close
  }
  function hide() {
    window.clearTimeout(closing);
    if (!sheet) return;
    sheet.classList.remove('is-closing');
    document.documentElement.classList.remove('watch-share-open');   // the page scrolls again at once, not a tick later
    if (typeof sheet.close === 'function' && sheet.open) sheet.close(); else { sheet.removeAttribute('open'); finish(); }
  }
  function finish() {
    document.documentElement.classList.remove('watch-share-open');
    var back = trigger;
    trigger = null;
    if (back && document.contains(back)) { try { back.focus({ preventScroll: true }); } catch (e) { back.focus(); } }   // focus goes back to the icon that opened the sheet
  }

  function copy() {
    if (!current) return;
    var item = current, url = item.url;
    function done() { track('product_share_copy', item); say('Link copied'); }
    function fallback() {
      var area = document.createElement('textarea');
      area.value = url;
      area.setAttribute('readonly', '');
      area.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;';
      sheet.appendChild(area);
      area.select();
      area.setSelectionRange(0, url.length);
      var ok = false;
      try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
      sheet.removeChild(area);
      if (ok) done(); else { say('Copy this link: ' + url); }
    }
    try {
      if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') navigator.clipboard.writeText(url).then(done, fallback);
      else fallback();
    } catch (e) { fallback(); }
  }

  function more() {
    if (!current || typeof navigator.share !== 'function') return;
    var item = current;
    track('product_share_more', item);
    try {
      var result = navigator.share({ title: item.name, text: 'Check this watch on SAT: ' + item.name, url: item.url });
      if (result && typeof result.then === 'function') result.then(function () { close(); }, function () { /* the shopper cancelled: keep the sheet */ });
    } catch (e) { /* not allowed right now: the sheet stays so WhatsApp and Copy link still work */ }
  }

  // one listener for every card and product page, so cards that are moved or added later work too
  document.addEventListener('click', function (event) {
    var link = event.target.closest && event.target.closest('[data-share-open]');
    if (!link || event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    event.stopPropagation();
    open(link);
  });
  document.addEventListener('keydown', function (event) {
    var link = event.target.closest && event.target.closest('[data-share-open]');
    if (link && event.key === ' ') { event.preventDefault(); link.click(); }   // the control is announced as a button, so Space works like on a button
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-share-open]'), function (link) { link.setAttribute('role', 'button'); });
})();
