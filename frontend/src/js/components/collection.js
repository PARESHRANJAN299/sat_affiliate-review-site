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
    var topFilters = root.hasAttribute('data-top-filters');
    var quick = Array.from(root.querySelectorAll('[data-quick-filter]'));
    var styleButtons = Array.from(root.querySelectorAll('[data-style-toggle]'));
    var chips = Array.from(root.querySelectorAll('[data-quick-chip]'));
    var sliders = Array.from(root.querySelectorAll('[data-price-slider]'));
    var pager = root.querySelector('[data-pagination]');
    var pageSize = Number(root.dataset.pageSize) || 0;
    var page = 1;
    var heading = topFilters ? root.closest('.watch-store').querySelector('h1') : null;
    function inlinePanel() { return desktop.matches; }
    if (topFilters) root.querySelector('[data-quick-controls]').hidden = false;
    sliders.forEach(function (slider) {
      var steps = JSON.parse(slider.dataset.steps);
      slider.hidden = false;
      slider.querySelector('input').addEventListener('input', function (event) {
        var at = Number(event.target.value);  // 0 is "Any price"; step n picks the n-th band, which already means "under" that price
        boxes.filter(function (box) { return box.dataset.group === slider.dataset.group; }).forEach(function (box) { box.checked = at > 0 && box.value === steps[at - 1][0]; });
        update();
      });
    });
    cards.forEach(function (card, index) { card.dataset.order = index; card._searchText = card.textContent.toLocaleLowerCase(); });
    root.querySelector('[data-controls]').hidden = false;
    root.classList.add('is-enhanced');
    function removeButton(label, callback) {
      var button = document.createElement('button');
      button.type = 'button'; button.className = 'filter-chip';
      button.textContent = label + ' ×'; button.setAttribute('aria-label', 'Remove ' + label + ' filter');
      button.addEventListener('click', function () { callback(); update(); });
      active.appendChild(button);
    }
    function update(resetPage) {
      if (resetPage !== false) page = 1;
      var selected = {};
      boxes.forEach(function (box) {
        if (box.checked) (selected[box.dataset.group] || (selected[box.dataset.group] = [])).push(box.value);
      });
      var query = search.value.trim().toLocaleLowerCase();
      var terms = query.split(/\s+/).filter(Boolean);
      var matched = [];
      cards.forEach(function (card) {
        var matches = terms.every(function (term) { return card._searchText.indexOf(term) !== -1; }) &&
          (!gender || (card.dataset.gender || '').split(' ').indexOf(gender) !== -1) &&
          Object.keys(selected).every(function (group) {
            return selected[group].some(function (value) { return (card.getAttribute('data-' + group) || '').split(' ').indexOf(value) !== -1; });
          });
        if (matches) matched.push(card);
        card.hidden = true;
      });
      var totalPages = pageSize ? Math.max(1, Math.ceil(matched.length / pageSize)) : 1;
      page = Math.min(page, totalPages);
      var start = pageSize ? (page - 1) * pageSize : 0;
      var end = pageSize ? Math.min(start + pageSize, matched.length) : matched.length;
      matched.slice(start, end).forEach(function (card) { card.hidden = false; });
      var count = root.querySelector('[data-collection-count]');
      count.textContent = (pageSize && matched.length > pageSize ? (start + 1) + '–' + end + ' of ' : '') + matched.length + ' ' + (matched.length === 1 ? root.dataset.noun : plural);
      root.querySelector('[data-empty]').hidden = matched.length !== 0;
      if (pager) {
        pager.replaceChildren(); pager.hidden = totalPages <= 1;
        function pageButton(label, number, disabled, current) {
          var button = document.createElement('button'); button.type = 'button'; button.textContent = label; button.disabled = disabled;
          if (current) button.setAttribute('aria-current', 'page');
          button.setAttribute('aria-label', label === 'Previous' || label === 'Next' ? label + ' product page' : 'Page ' + label);
          button.addEventListener('click', function () {
            page = number; update(false);
            count.tabIndex = -1; count.focus({preventScroll:true}); count.scrollIntoView({block:'start'});
          });
          pager.appendChild(button);
        }
        pageButton('Previous', page - 1, page === 1, false);
        var first = Math.max(1, Math.min(page - 2, totalPages - 4));
        for (var i = first; i <= Math.min(totalPages, first + 4); i++) pageButton(String(i), i, false, i === page);
        pageButton('Next', page + 1, page === totalPages, false);
      }
      quick.forEach(function (select) {
        var values = selected[select.dataset.quickFilter] || [];
        select.value = values.length > 1 ? '__multiple' : (values[0] || '');
      });
      chips.forEach(function (chip) {
        chip.setAttribute('aria-pressed', (selected[chip.dataset.quickChip] || []).indexOf(chip.dataset.value) !== -1 && (!chip.dataset.chipGender || chip.dataset.chipGender === gender) ? 'true' : 'false');
      });
      sliders.forEach(function (slider) {
        var steps = JSON.parse(slider.dataset.steps);
        var picked = selected[slider.dataset.group] || [];
        var at = picked.length === 1 ? steps.map(function (step) { return step[0]; }).indexOf(picked[0]) + 1 : 0;
        var text = at ? steps[at - 1][1] : picked.length > 1 ? 'Several price bands' : picked[0] === 'unlisted' ? 'Price at retailer' : 'Any price';
        var input = slider.querySelector('input');
        input.value = at; input.setAttribute('aria-valuetext', text);
        slider.querySelector('[data-price-label]').textContent = text;
        Array.from(slider.querySelectorAll('[data-price-bar]')).forEach(function (bar, index) { bar.classList.toggle('is-in', at > 0 && index < at); });
      });
      styleButtons.forEach(function (button) {
        var values = selected.style || [];
        var tile = button.dataset.styleToggle;
        var chosen = !tile ? !values.length : values.indexOf(tile) !== -1;
        // a style with no watch under the other filters is hidden: tapping it would only show an empty list
        button.hidden = !!tile && !chosen && !cards.some(function (card) {
          return (!gender || (card.dataset.gender || '').split(' ').indexOf(gender) !== -1) &&
            (card.getAttribute('data-style') || '').split(' ').indexOf(tile) !== -1 &&
            Object.keys(selected).every(function (group) {
              return group === 'style' || selected[group].some(function (value) { return (card.getAttribute('data-' + group) || '').split(' ').indexOf(value) !== -1; });
            });
        });
        button.setAttribute('aria-current', (!button.dataset.styleToggle ? !values.length : values.indexOf(button.dataset.styleToggle) !== -1) ? 'true' : 'false');
      });
      if (heading) {
        var brands = boxes.filter(function (box) {return box.dataset.group === 'brand' && box.checked;});
        var styles = boxes.filter(function (box) {return box.dataset.group === 'style' && box.checked;});
        var budgets = boxes.filter(function (box) {return box.dataset.group === 'budget' && box.checked;});
        function label(box) {return box.parentElement.querySelector('span').textContent;}
        heading.textContent = !gender && !brands.length && !styles.length && !budgets.length ? 'Watches for every day.' :
          (brands.length === 1 ? label(brands[0]) + ' ' : '') + (gender === 'men' ? "Men's " : gender === 'women' ? "Women's " : '') +
          (styles.length === 1 ? label(styles[0]) + ' ' : '') + 'Watches' + (budgets.length === 1 && budgets[0].value !== 'unlisted' ? ' ' + label(budgets[0]) : '');
      }
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
    quick.forEach(function (select) {
      select.addEventListener('change', function () {
        boxes.filter(function (box) { return box.dataset.group === select.dataset.quickFilter; }).forEach(function (box) { box.checked = box.value === select.value; }); update();
      });
    });
    chips.forEach(function (chip) {
      chip.addEventListener('click', function () {
        var box = boxes.filter(function (b) { return b.dataset.group === chip.dataset.quickChip && b.value === chip.dataset.value; })[0];
        if (!box) return;
        if (chip.dataset.chipGender) {  // a phrase such as "leather strap watches for men" sets the shopper path and the filter together
          var on = chip.getAttribute('aria-pressed') === 'true';
          box.checked = !on; if (!on) gender = chip.dataset.chipGender;
        } else { box.checked = !box.checked; }
        update();
      });
    });
    styleButtons.forEach(function (button) {
      button.addEventListener('click', function (event) {
        event.preventDefault();
        var selected = button.getAttribute('aria-current') === 'true';
        boxes.filter(function (box) { return box.dataset.group === 'style'; }).forEach(function (box) { box.checked = !selected && box.value === button.dataset.styleToggle; }); update();
      });
    });
    segments.forEach(function (button) { button.addEventListener('click', function () { gender = gender === button.dataset.gender ? '' : button.dataset.gender; update(); }); });
    sort.addEventListener('change', function () {
      var ordered = cards.slice().sort(function (a, b) {
        if (sort.value === 'featured') return Number(a.dataset.order) - Number(b.dataset.order);
        var result = (a.dataset.name || a.querySelector('h3').textContent).localeCompare(b.dataset.name || b.querySelector('h3').textContent, 'en-IN', { numeric: true });
        return sort.value === 'name-desc' ? -result : result;
      });
      ordered.forEach(function (card) { grid.appendChild(card); }); cards = ordered; update();
    });
    root.querySelectorAll('[data-filter-clear]').forEach(function (button) { button.addEventListener('click', clearAll); });
    function closeSheet() { if (!inlinePanel() && panel.open) panel.close(); }
    opener.addEventListener('click', function () {
      if (panel.open || inlinePanel()) return;
      panel.showModal(); document.documentElement.classList.add('collection-modal-open');
    });
    panel.querySelectorAll('[data-filter-close]').forEach(function (button) { button.addEventListener('click', closeSheet); });
    panel.addEventListener('click', function (event) {
      var rect = panel.getBoundingClientRect();
      if (!inlinePanel() && (event.clientY < rect.top || event.clientX < rect.left || event.clientX > rect.right)) closeSheet();
    });
    panel.addEventListener('close', function () {
      document.documentElement.classList.remove('collection-modal-open');
      if (inlinePanel()) panel.setAttribute('open', '');
    });
    function resize() {
      if (panel.open) panel.close();
      document.documentElement.classList.remove('collection-modal-open');
      if (inlinePanel()) panel.setAttribute('open', '');
    }
    desktop.addEventListener('change', resize);
    resize(); update();
  });
})();
