(function () {
  'use strict';
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

  // A shared link (#pick-<id>) scrolls its card into view along the rail.
  function reveal() {
    var target = location.hash && document.getElementById(location.hash.slice(1));
    if (target && target.classList.contains('nykaa-product-shell')) target.scrollIntoView({ inline: 'center', block: 'nearest' });
  }
  window.addEventListener('hashchange', reveal);
  window.addEventListener('load', reveal);
})();
