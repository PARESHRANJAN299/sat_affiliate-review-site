(function () {
  'use strict';
  // Filter chips (desktop) and bottom sheet (phones) for watch cards. Cards stay visible without JavaScript.
  var bar = document.querySelector('[data-filters]');
  var cards = document.querySelectorAll('.watch-card[data-styles]');
  if (!bar || !cards.length) return;
  bar.hidden = false;

  var buttons = document.querySelectorAll('[data-filter]');
  var count = bar.querySelector('[data-filter-count]');
  var sheet = document.querySelector('[data-sheet]');
  var active = { style: [], strap: [] };

  function matches(card) {
    var styles = card.getAttribute('data-styles').split(' ');
    return ['style', 'strap'].every(function (group) {
      return !active[group].length || active[group].some(function (s) { return styles.indexOf(s) !== -1; });
    });
  }

  function update() {
    var shown = 0;
    Array.prototype.forEach.call(cards, function (card) {
      var ok = matches(card);
      card.hidden = !ok;
      if (ok) shown += 1;
    });
    if (count) count.textContent = 'Showing ' + shown + ' of ' + cards.length + ' watches';
  }

  Array.prototype.forEach.call(buttons, function (button) {
    button.addEventListener('click', function () {
      var group = button.getAttribute('data-group') || 'style';
      var value = button.getAttribute('data-filter');
      var list = active[group];
      var at = list.indexOf(value);
      if (at === -1) list.push(value); else list.splice(at, 1);
      Array.prototype.forEach.call(buttons, function (b) {
        if (b.getAttribute('data-filter') === value) {
          b.setAttribute('aria-pressed', at === -1 ? 'true' : 'false');
        }
      });
      update();
    });
  });

  var clear = document.querySelector('[data-filter-clear]');
  if (clear) {
    clear.addEventListener('click', function () {
      active = { style: [], strap: [] };
      Array.prototype.forEach.call(buttons, function (b) { b.setAttribute('aria-pressed', 'false'); });
      update();
    });
  }

  var open = document.querySelector('[data-sheet-open]');
  if (open && sheet && sheet.showModal) {
    open.addEventListener('click', function () { sheet.showModal(); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-sheet-close]'), function (b) {
      b.addEventListener('click', function () { sheet.close(); });
    });
    sheet.addEventListener('click', function (event) {
      if (event.target === sheet) sheet.close();
    });
  } else if (open) {
    open.hidden = true;
  }
  update();
})();
