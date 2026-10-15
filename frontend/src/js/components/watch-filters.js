(function () {
  'use strict';
  // Filter chips (desktop) and bottom sheet (phones) for watch cards. Everything stays visible without JavaScript.
  var bar = document.querySelector('[data-filters]');
  var cards = document.querySelectorAll('.watch-card[data-styles]');
  if (!bar || !cards.length) return;
  bar.hidden = false;

  var buttons = document.querySelectorAll('[data-filter]');
  var count = bar.querySelector('[data-filter-count]');
  var badge = bar.querySelector('[data-filter-badge]');
  var empty = document.querySelector('[data-filter-empty]');
  var sheet = document.querySelector('[data-sheet]');
  var active = {};

  function activeTotal() {
    return Object.keys(active).reduce(function (n, g) { return n + active[g].length; }, 0);
  }

  function matches(card) {
    var styles = card.getAttribute('data-styles').split(' ');
    return Object.keys(active).every(function (group) {
      return !active[group].length || active[group].some(function (s) { return styles.indexOf(s) !== -1; });
    });
  }

  function setVisible(id, visible) {
    var nodes = document.querySelectorAll('[data-id="' + id + '"]');
    Array.prototype.forEach.call(nodes, function (n) { n.hidden = !visible; });
  }

  function update() {
    var shown = 0;
    Array.prototype.forEach.call(cards, function (card) {
      var ok = matches(card);
      setVisible(card.getAttribute('data-id'), ok);
      if (ok) shown += 1;
    });
    var total = activeTotal();
    if (count) count.textContent = __('Showing {a} of {b} watches', { a: shown, b: cards.length });
    if (badge) badge.textContent = total ? String(total) : '';
    if (empty) empty.hidden = shown !== 0;
  }

  Array.prototype.forEach.call(buttons, function (button) {
    button.addEventListener('click', function () {
      var group = button.getAttribute('data-group') || 'style';
      var value = button.getAttribute('data-filter');
      var list = active[group] = active[group] || [];
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

  Array.prototype.forEach.call(document.querySelectorAll('[data-filter-clear]'), function (clear) {
    clear.addEventListener('click', function () {
      active = {};
      Array.prototype.forEach.call(buttons, function (b) { b.setAttribute('aria-pressed', 'false'); });
      update();
    });
  });

  var open = document.querySelector('[data-sheet-open]');
  if (open && sheet && sheet.showModal) {
    open.addEventListener('click', function () { sheet.showModal(); });
    Array.prototype.forEach.call(document.querySelectorAll('[data-sheet-close]'), function (b) {
      b.addEventListener('click', function () { sheet.close(); open.focus(); });
    });
    sheet.addEventListener('click', function (event) {
      if (event.target === sheet) sheet.close();
    });
  } else if (open) {
    open.hidden = true;
    var inline = bar.querySelector('.filters-inline');
    if (inline) inline.classList.add('no-dialog');
  }
  update();
})();
