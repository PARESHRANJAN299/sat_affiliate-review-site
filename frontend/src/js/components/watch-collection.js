(function () {
  'use strict';
  // Product collection on the Watches page: a preset (for example Fossil men's) is shown first. Filters, the Men's/Women's switch and sorting
  // widen it to every brand. Without JavaScript the preset stays visible and the brand, budget and style pages below still work.
  var root = document.querySelector('[data-collection]');
  if (!root) return;
  var grid = root.querySelector('[data-watch-grid]');
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.watch-card'));
  var panel = root.querySelector('[data-filter-panel]');
  var bar = root.querySelector('[data-collection-bar]');
  var seg = root.querySelector('[data-seg]');
  var title = root.querySelector('[data-collection-title]');
  var countEl = root.querySelector('[data-collection-count]');
  var sortSel = root.querySelector('[data-sort]');
  var empty = root.querySelector('[data-filter-empty]');
  var reset = root.querySelector('[data-reset]');
  var openBtn = root.querySelector('[data-filter-open]');
  var badge = root.querySelector('[data-filter-badge]');
  var scrim = document.querySelector('[data-filter-scrim]');
  var presetGender = root.getAttribute('data-preset-gender') || '';
  var presetBrand = root.getAttribute('data-preset-brand') || '';
  var defaultTitle = root.getAttribute('data-default-title') || 'Watches';
  var boxes = Array.prototype.slice.call(panel.querySelectorAll('input[type="checkbox"]'));
  var segBtns = seg ? Array.prototype.slice.call(seg.querySelectorAll('[data-gender]')) : [];
  cards.forEach(function (c, i) { c.setAttribute('data-i', String(i)); });
  bar.hidden = false; if (seg) seg.hidden = false; panel.hidden = false;

  var plural = root.getAttribute('data-plural') || 'products';
  var noun = root.getAttribute('data-noun') || 'product';
  var nounTitle = plural.charAt(0).toUpperCase() + plural.slice(1);
  var groupKeys = [];
  boxes.forEach(function (b) { var g = b.getAttribute('data-group'); if (groupKeys.indexOf(g) === -1) groupKeys.push(g); });
  var state = { gender: presetGender, sel: {}, sort: 'featured' };
  groupKeys.forEach(function (g) { state.sel[g] = []; });

  function read() {
    groupKeys.forEach(function (g) { state.sel[g] = []; });
    boxes.forEach(function (b) { if (b.checked) state.sel[b.getAttribute('data-group')].push(b.value); });
  }
  function match(c) {
    if (state.gender && (c.getAttribute('data-gender') || '').split(' ').indexOf(state.gender) === -1) return false;
    return groupKeys.every(function (g) {
      var want = state.sel[g];
      if (!want.length) return true;
      var have = (c.getAttribute('data-' + g) || '').split(' ');
      return want.some(function (x) { return have.indexOf(x) !== -1; });
    });
  }
  function isPreset() {
    var others = groupKeys.every(function (g) { return g === 'brand' ? (state.sel.brand.length === 1 && state.sel.brand[0] === presetBrand) : !state.sel[g].length; });
    return !!presetBrand && state.gender === presetGender && others;
  }
  function names(group) {
    return boxes.filter(function (b) { return b.checked && b.getAttribute('data-group') === group; })
      .map(function (b) { return b.getAttribute('data-label'); });
  }
  function headline() {
    if (isPreset()) return defaultTitle;
    var b = names('brand');
    var brandText = b.length === 0 ? '' : (b.length <= 2 ? b.join(' & ') : 'Selected brands');
    var g = state.gender === 'men' ? "Men's" : (state.gender === 'women' ? "Women's" : '');
    var other = groupKeys.filter(function (k) { return k !== 'brand' && state.sel[k].length === 1; }).map(function (k) { return names(k)[0]; });
    var t = [brandText, g].concat(other, [nounTitle]).filter(Boolean).join(' ');
    return (brandText || g || other.length) ? t : (presetBrand ? 'All ' + nounTitle : defaultTitle);
  }
  function sortCards() {
    var by = sortSel.value;
    var list = cards.slice();
    if (by === 'budget-low') list.sort(function (a, b) { return a.getAttribute('data-max') - b.getAttribute('data-max') || a.getAttribute('data-i') - b.getAttribute('data-i'); });
    else if (by === 'budget-high') list.sort(function (a, b) { return b.getAttribute('data-max') - a.getAttribute('data-max') || a.getAttribute('data-i') - b.getAttribute('data-i'); });
    else if (by === 'name') list.sort(function (a, b) { return a.querySelector('.watch-model').textContent.localeCompare(b.querySelector('.watch-model').textContent); });
    else list.sort(function (a, b) { return a.getAttribute('data-i') - b.getAttribute('data-i'); });
    list.forEach(function (c) { grid.appendChild(c); });
  }
  function update() {
    read();
    var shown = 0;
    cards.forEach(function (c) { var ok = match(c); c.hidden = !ok; if (ok) shown += 1; });
    title.textContent = headline();
    countEl.textContent = shown + (shown === 1 ? ' ' + noun : ' ' + plural);
    empty.hidden = shown !== 0;
    var chosen = boxes.filter(function (b) { return b.checked; }).length;
    if (badge) badge.textContent = chosen ? String(chosen) : '';
    if (reset) reset.hidden = isPreset();
    segBtns.forEach(function (b) { b.setAttribute('aria-pressed', b.getAttribute('data-gender') === state.gender ? 'true' : 'false'); });
  }

  boxes.forEach(function (b) { b.addEventListener('change', update); });
  segBtns.forEach(function (b) {
    b.addEventListener('click', function () {
      var g = b.getAttribute('data-gender');
      state.gender = state.gender === g ? '' : g;
      update();
    });
  });
  sortSel.addEventListener('change', function () { sortCards(); update(); });
  Array.prototype.forEach.call(root.querySelectorAll('[data-filter-clear]'), function (btn) {
    btn.addEventListener('click', function () { boxes.forEach(function (b) { b.checked = false; }); state.gender = ''; update(); });
  });
  if (reset) {
    reset.addEventListener('click', function () {
      boxes.forEach(function (b) { b.checked = (b.getAttribute('data-group') === 'brand' && b.value === presetBrand); });
      state.gender = presetGender; sortSel.value = 'featured'; sortCards(); update();
    });
  }

  // phones: the filter panel is a bottom sheet
  var lastFocus = null;
  function setSheet(open) {
    panel.classList.toggle('is-open', open);
    if (scrim) scrim.hidden = !open;
    document.documentElement.classList.toggle('no-scroll', open);
    openBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) { lastFocus = document.activeElement; var f = panel.querySelector('input,button'); if (f) f.focus(); }
    else if (lastFocus) lastFocus.focus();
  }
  openBtn.addEventListener('click', function () { setSheet(true); });
  Array.prototype.forEach.call(root.querySelectorAll('[data-filter-close]'), function (b) { b.addEventListener('click', function () { setSheet(false); }); });
  if (scrim) scrim.addEventListener('click', function () { setSheet(false); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && panel.classList.contains('is-open')) setSheet(false); });
  update();
})();
