(function () {
  'use strict';
  // Make the comparison table scrollable by keyboard only when it really overflows.
  var wrap = document.querySelector('.compare-table-wrap');
  if (!wrap) return;
  function check() {
    if (wrap.scrollWidth > wrap.clientWidth + 1) {
      wrap.setAttribute('tabindex', '0');
      wrap.setAttribute('role', 'region');
      wrap.setAttribute('aria-label', 'Racket comparison table');
    } else {
      wrap.removeAttribute('tabindex');
      wrap.removeAttribute('role');
      wrap.removeAttribute('aria-label');
    }
  }
  check();
  window.addEventListener('resize', check);
})();
