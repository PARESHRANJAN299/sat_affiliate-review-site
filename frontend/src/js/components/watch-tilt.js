(function () {
  'use strict';
  // Gentle 3D tilt: the drawn watch turns toward the pointer on desktop. Touch screens and people who prefer reduced motion get none (the product page sways slowly instead, in CSS).
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
  var active = null;
  function reset(art) { if (!art) return; art.style.setProperty('--rx', '0deg'); art.style.setProperty('--ry', '0deg'); }
  document.addEventListener('pointermove', function (event) {
    var stage = event.target.closest && event.target.closest('.watch-tile, .watch-pdp-photo');
    if (!stage) { if (active) { reset(active); active = null; } return; }
    var art = stage.querySelector('.dial-art');
    if (!art) return;
    if (active && active !== art) reset(active);
    active = art;
    var box = stage.getBoundingClientRect();
    var x = (event.clientX - box.left) / box.width - 0.5;
    var y = (event.clientY - box.top) / box.height - 0.5;
    art.style.setProperty('--ry', (x * 22).toFixed(1) + 'deg');
    art.style.setProperty('--rx', (-y * 16).toFixed(1) + 'deg');
  }, { passive: true });
  document.addEventListener('pointerleave', function () { if (active) { reset(active); active = null; } });
})();
