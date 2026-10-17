(function () {
  'use strict';
  // Home page price slider: picks a band, then "Show watches" opens the Watches page with that band already chosen.
  document.querySelectorAll('[data-home-price]').forEach(function (box) {
    var slider = box.querySelector('[data-price-slider]');
    var steps = JSON.parse(slider.dataset.steps);
    var input = slider.querySelector('input');
    var label = slider.querySelector('[data-price-label]');
    var go = box.querySelector('[data-price-go]');
    var bars = Array.from(slider.querySelectorAll('[data-price-bar]'));
    function sync() {
      var at = Number(input.value);
      var text = at ? steps[at - 1][1] : 'Any price';
      label.textContent = text; input.setAttribute('aria-valuetext', text);
      go.href = at ? '/watches/?price=' + encodeURIComponent(steps[at - 1][0]) + '#watch-collection' : '/watches/';
      bars.forEach(function (bar, index) { bar.classList.toggle('is-in', at > 0 && index < at); });
    }
    slider.hidden = false;
    input.addEventListener('input', sync);
    sync();
  });
})();
