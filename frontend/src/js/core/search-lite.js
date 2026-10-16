(function () {
  'use strict';
  // Small always-on part of site search. The engine and its styles download the first time search is
  // wanted (or when the button is hovered, focused or touched). Without JavaScript the button is a link to /search/.
  var opener = document.querySelector('[data-search-index]');
  if (!opener || !window.Promise) return;
  var jsUrl = opener.getAttribute('data-search-js');
  var cssUrl = opener.getAttribute('data-search-css');
  var onSearchPage = !!document.querySelector('[data-search-page]');
  var pending = null;

  if (!onSearchPage) {
    opener.setAttribute('aria-haspopup', 'dialog');
    opener.setAttribute('aria-expanded', 'false');
  }

  function addCss() {
    return new Promise(function (resolve) {
      if (!cssUrl || onSearchPage || document.querySelector('link[data-sx-css]')) { resolve(); return; }
      var link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = cssUrl;
      link.setAttribute('data-sx-css', '');
      link.onload = resolve;
      link.onerror = resolve;
      document.head.appendChild(link);
    });
  }
  function addJs() {
    return new Promise(function (resolve, reject) {
      if (window.SATSearch) { resolve(); return; }
      if (!jsUrl) { reject(new Error('no search script')); return; }
      var script = document.createElement('script');
      script.src = jsUrl;
      script.async = true;
      script.onload = function () { window.SATSearch ? resolve() : reject(new Error('search failed to start')); };
      script.onerror = function () { reject(new Error('search script failed')); };
      document.head.appendChild(script);
    });
  }
  function ensure() {
    if (!pending) {
      pending = Promise.all([addCss(), addJs()]).then(function () { return window.SATSearch; });
      pending.catch(function () { pending = null; });
    }
    return pending;
  }
  function toggle() {
    ensure().then(function (api) { api.toggle(); }, function () { window.location.href = '/search/'; });
  }

  opener.addEventListener('click', function (e) {
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    toggle();
  });
  // the Search tab in the phone bottom bar opens the same overlay
  Array.prototype.forEach.call(document.querySelectorAll('[data-bn-search]'), function (tab) {
    tab.addEventListener('click', function (e) {
      if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;
      e.preventDefault();
      toggle();
    });
  });
  ['pointerenter', 'focus', 'touchstart'].forEach(function (name) {
    opener.addEventListener(name, function () {
      ensure().then(function (api) { api.warm(); }, function () { /* tried again on click */ });
    }, { passive: true, once: true });
  });
  document.addEventListener('keydown', function (e) {
    var t = e.target, tag = t && t.tagName;
    var typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (t && t.isContentEditable);
    if (typing || e.altKey) return;
    if ((e.key === '/' && !e.ctrlKey && !e.metaKey) || ((e.key === 'k' || e.key === 'K') && (e.ctrlKey || e.metaKey))) {
      e.preventDefault();
      ensure().then(function (api) { api.open(); }, function () { window.location.href = '/search/'; });
    }
  });
  window.addEventListener('pageshow', function (e) {
    if (e.persisted && window.SATSearch) window.SATSearch.close();
  });
})();
