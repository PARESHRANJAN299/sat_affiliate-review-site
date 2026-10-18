(function () {
  'use strict';
  // Women / Men toggle: without JavaScript both lists are shown one after the other.
  var tabs = document.querySelectorAll('[data-audience-tab]');
  var panels = document.querySelectorAll('[data-audience-panel]');
  function showAudience(name) {
    panels.forEach(function (panel) { panel.hidden = panel.dataset.audiencePanel !== name; });
    tabs.forEach(function (tab) {
      if (tab.dataset.audienceTab === name) tab.setAttribute('aria-current', 'true'); else tab.removeAttribute('aria-current');
    });
  }
  function audienceFromHash() {
    var id = location.hash.slice(1);
    if (!id) return null;
    var target = document.getElementById(id);
    var panel = target && target.closest ? target.closest('[data-audience-panel]') : null;
    if (panel) return panel.dataset.audiencePanel;
    return document.querySelector('[data-audience-tab="' + id.replace(/[^a-z-]/g, '') + '"]') ? id : null;
  }
  if (tabs.length) {
    showAudience(audienceFromHash() || tabs[0].dataset.audienceTab);
    tabs.forEach(function (tab) {
      tab.addEventListener('click', function (event) {
        event.preventDefault();
        showAudience(tab.dataset.audienceTab);
        try { history.replaceState(null, '', '#' + tab.dataset.audienceTab); } catch (error) { /* the toggle still works */ }
      });
    });
  }

  var rails = document.querySelectorAll('[data-widget-rail], [data-widget-grid]');
  if (!rails.length) return;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  rails.forEach(function (rail) {
    var section = rail.closest('[data-rail-group]') || rail.closest('section') || document;
    var controls = section.querySelector('[data-rail-controls]');
    var prev = section.querySelector('[data-rail-prev]');
    var next = section.querySelector('[data-rail-next]');
    var status = section.querySelector('[data-widget-status]');

    function say(text) { if (status) status.textContent = text; }

    function update() {
      var scrollable = rail.scrollWidth > rail.clientWidth + 2;
      if (controls) controls.hidden = !scrollable;
      if (prev) prev.disabled = rail.scrollLeft <= 2;
      if (next) next.disabled = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 2;
    }
    function step(direction) {
      var card = rail.querySelector('.nykaa-product-shell');
      var width = card ? card.getBoundingClientRect().width + 16 : rail.clientWidth * 0.8;
      var count = Math.max(1, Math.floor(rail.clientWidth / width));
      rail.scrollBy({ left: direction * width * count, behavior: reduce ? 'auto' : 'smooth' });
    }
    if (prev) prev.addEventListener('click', function () { step(-1); });
    if (next) next.addEventListener('click', function () { step(1); });
    rail.addEventListener('scroll', function () { window.requestAnimationFrame(update); }, { passive: true });
    window.addEventListener('resize', update);
    update();

    rail.querySelectorAll('[data-copy-pick]').forEach(function (button) {
      button.hidden = false;
      button.addEventListener('click', function () {
        var url = button.dataset.url;
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(function () { say('Link copied.'); button.textContent = 'Copied'; setTimeout(function () { button.textContent = 'Copy link'; }, 2000); },
            function () { fallback(button, url); });
        } else { fallback(button, url); }
      });
    });
    function fallback(button, url) {
      var input = document.createElement('input');
      input.type = 'text'; input.readOnly = true; input.value = url; input.className = 'nykaa-share-input';
      input.setAttribute('aria-label', 'Link to copy');
      button.parentNode.replaceChild(input, button); input.select();
    }
    if (navigator.share) {
      rail.querySelectorAll('[data-share-pick]').forEach(function (button) {
        button.hidden = false;
        button.addEventListener('click', function () {
          navigator.share({ title: button.dataset.title, url: button.dataset.url }).catch(function (error) {
            if (error && error.name !== 'AbortError') say('Use WhatsApp or copy the link.');
          });
        });
      });
    }
  });

  // Sorting aid for the site owner: add ?sort=1 to a category page to mark products as men's, then copy their ids.
  if (/[?&]sort=1(&|$)/.test(location.search)) {
    var marked = {};
    var bar = document.createElement('div');
    bar.className = 'nykaa-sortbar';
    var label = document.createElement('span');
    var copyAll = document.createElement('button');
    copyAll.type = 'button'; copyAll.textContent = 'Copy men’s product ids';
    bar.appendChild(label); bar.appendChild(copyAll); document.body.appendChild(bar);
    var count = function () { var ids = Object.keys(marked); label.textContent = 'Marked as men: ' + ids.length; return ids; };
    count();
    document.querySelectorAll('.nykaa-product-shell').forEach(function (card) {
      var mark = document.createElement('button');
      mark.type = 'button'; mark.className = 'nykaa-mark'; mark.textContent = 'Mark as men'; mark.setAttribute('aria-pressed', 'false');
      mark.addEventListener('click', function () {
        var id = card.dataset.productId, on = !marked[id];
        if (on) marked[id] = true; else delete marked[id];
        card.classList.toggle('is-marked', on); mark.setAttribute('aria-pressed', String(on));
        mark.textContent = on ? 'Marked as men' : 'Mark as men'; count();
      });
      card.appendChild(mark);
    });
    copyAll.addEventListener('click', function () {
      var text = count().join(',');
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(function () { copyAll.textContent = 'Copied'; }, function () { window.prompt('Copy these ids', text); });
      else window.prompt('Copy these ids', text);
    });
  }

  // A shared link (#pick-<id>) scrolls its card into view along the rail.
  function reveal() {
    var target = location.hash && document.getElementById(location.hash.slice(1));
    if (!target || !target.classList.contains('nykaa-product-shell')) return;
    var panel = target.closest('[data-audience-panel]');
    if (panel && panel.hidden) showAudience(panel.dataset.audiencePanel);
    target.scrollIntoView({ inline: 'center', block: 'center' });
  }
  window.addEventListener('hashchange', reveal);
  window.addEventListener('load', reveal);
})();
