(function () {
  'use strict';
  // Floating "back to top" button. Added by script, so pages are unchanged without JavaScript.
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var CIRC = 125.66;
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'to-top';
  btn.setAttribute('aria-label', __('Back to top'));
  btn.innerHTML =
    '<svg class="to-top-ring" viewBox="0 0 44 44" aria-hidden="true"><circle class="to-top-track" cx="22" cy="22" r="20"/>' +
    '<circle class="to-top-bar" cx="22" cy="22" r="20" stroke-dasharray="' + CIRC + '" stroke-dashoffset="' + CIRC + '"/></svg>' +
    '<svg class="to-top-arrow" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
  document.body.appendChild(btn);
  var bar = btn.querySelector('.to-top-bar');
  var ticking = false;

  function update() {
    ticking = false;
    var y = window.pageYOffset || document.documentElement.scrollTop || 0;
    var max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    var p = Math.min(1, y / max);
    bar.style.strokeDashoffset = String(CIRC * (1 - p));
    btn.classList.toggle('is-on', y > 400);
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; window.requestAnimationFrame(update); }
  }, { passive: true });
  window.addEventListener('resize', update, { passive: true });
  update();

  btn.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    // keep keyboard focus somewhere sensible, because this button hides once the page is at the top
    var cands = document.querySelectorAll('.site-header a, .site-header summary');
    for (var i = 0; i < cands.length; i++) {
      if (cands[i].offsetParent !== null) { cands[i].focus({ preventScroll: true }); break; }
    }
  });
})();
