(function () {
  'use strict';
  document.querySelectorAll('[data-collection]').forEach(function (root) {
    var grid = root.querySelector('[data-collection-grid]');
    var cards = Array.from(grid.children);
    var panel = root.querySelector('[data-filter-panel]');
    var boxes = Array.from(panel.querySelectorAll('input'));
    var search = root.querySelector('[data-search]');
    var sort = root.querySelector('[data-sort]');
    var active = root.querySelector('[data-active]');
    var gender = root.dataset.presetGender || '';
    var segments = Array.from(root.querySelectorAll('[data-gender]'));
    var desktop = window.matchMedia('(min-width: 1000px)');
    var opener = root.querySelector('[data-filter-open]');
    var plural = root.dataset.plural;
    cards.forEach(function (card, index) { card.dataset.order = index; });
    root.querySelector('[data-controls]').hidden = false;
    root.classList.add('is-enhanced');
    function removeButton(label, callback) {
      var button = document.createElement('button');
      button.type = 'button'; button.className = 'filter-chip';
      button.textContent = label + ' ×'; button.setAttribute('aria-label', 'Remove ' + label + ' filter');
      button.addEventListener('click', function () { callback(); update(); });
      active.appendChild(button);
    }
    function update() {
      var selected = {};
      boxes.forEach(function (box) {
        if (box.checked) (selected[box.dataset.group] || (selected[box.dataset.group] = [])).push(box.value);
      });
      var query = search.value.trim().toLocaleLowerCase();
      var terms = query.split(/\s+/).filter(Boolean);
      var shown = 0;
      cards.forEach(function (card) {
        var text = card.textContent.toLocaleLowerCase();
        var matches = terms.every(function (term) { return text.indexOf(term) !== -1; }) &&
          (!gender || (card.dataset.gender || '').split(' ').indexOf(gender) !== -1) &&
          Object.keys(selected).every(function (group) {
            return selected[group].some(function (value) { return (card.getAttribute('data-' + group) || '').split(' ').indexOf(value) !== -1; });
          });
        card.hidden = !matches; if (matches) shown++;
      });
      root.querySelector('[data-collection-count]').textContent = shown + ' of ' + cards.length + ' ' + (cards.length === 1 ? root.dataset.noun : plural);
      root.querySelector('[data-empty]').hidden = shown !== 0;
      active.replaceChildren();
      boxes.filter(function (box) { return box.checked; }).forEach(function (box) {
        removeButton(box.parentElement.querySelector('span').textContent, function () { box.checked = false; });
      });
      if (gender) removeButton(gender === 'men' ? "Men's" : "Women's", function () { gender = ''; });
      if (query) removeButton('Search: ' + search.value.trim(), function () { search.value = ''; });
      var total = boxes.filter(function (box) { return box.checked; }).length + (gender ? 1 : 0);
      root.querySelector('[data-filter-badge]').textContent = total ? '(' + total + ')' : '';
      active.hidden = active.children.length === 0;
      if (!active.hidden) {
        var clear = document.createElement('button'); clear.type = 'button'; clear.className = 'linklike'; clear.textContent = 'Clear all'; clear.addEventListener('click', clearAll); active.appendChild(clear);
      }
      segments.forEach(function (button) { button.setAttribute('aria-pressed', button.dataset.gender === gender ? 'true' : 'false'); });
    }
    function clearAll() {
      boxes.forEach(function (box) { box.checked = false; }); gender = ''; search.value = ''; update();
    }
    boxes.forEach(function (box) { box.addEventListener('change', update); });
    search.addEventListener('input', update);
    segments.forEach(function (button) { button.addEventListener('click', function () { gender = button.dataset.gender; update(); }); });
    sort.addEventListener('change', function () {
      var ordered = cards.slice().sort(function (a, b) {
        if (sort.value === 'featured') return Number(a.dataset.order) - Number(b.dataset.order);
        var result = (a.dataset.name || a.querySelector('h3').textContent).localeCompare(b.dataset.name || b.querySelector('h3').textContent, 'en-IN', { numeric: true });
        return sort.value === 'name-desc' ? -result : result;
      });
      ordered.forEach(function (card) { grid.appendChild(card); });
    });
    root.querySelectorAll('[data-filter-clear]').forEach(function (button) { button.addEventListener('click', clearAll); });
    function closeSheet() { if (!desktop.matches && panel.open) panel.close(); }
    opener.addEventListener('click', function () {
      if (panel.open || desktop.matches) return;
      panel.showModal(); document.documentElement.classList.add('collection-modal-open');
    });
    panel.querySelectorAll('[data-filter-close]').forEach(function (button) { button.addEventListener('click', closeSheet); });
    panel.addEventListener('click', function (event) {
      var rect = panel.getBoundingClientRect();
      if (!desktop.matches && (event.clientY < rect.top || event.clientX < rect.left || event.clientX > rect.right)) closeSheet();
    });
    panel.addEventListener('close', function () {
      document.documentElement.classList.remove('collection-modal-open');
      if (desktop.matches) panel.setAttribute('open', '');
    });
    function resize() {
      if (panel.open) panel.close();
      document.documentElement.classList.remove('collection-modal-open');
      if (desktop.matches) panel.setAttribute('open', '');
    }
    desktop.addEventListener('change', resize);
    resize(); update();
  });
})();
