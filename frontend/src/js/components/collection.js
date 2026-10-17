(function () {
  'use strict';
  document.querySelectorAll('[data-collection]').forEach(function (root) {
    var grid = root.querySelector('[data-collection-grid]');
    var tips = Array.from(grid.querySelectorAll('[data-tip]'));
    var cards = Array.from(grid.children).filter(function (el) { return !el.hasAttribute('data-tip'); });
    var panel = root.querySelector('[data-filter-panel]');
    var boxes = Array.from(panel.querySelectorAll('input'));
    var search = root.querySelector('[data-search]');
    var sort = root.querySelector('[data-sort]');
    var active = root.querySelector('[data-active]');
    var gender = root.dataset.presetGender || '';
    var segments = Array.from(root.querySelectorAll('[data-gender]'));
    var desktop = window.matchMedia('(min-width: 1000px)');
    var openers = Array.from(root.querySelectorAll('[data-filter-open]'));
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
    var headingDefault = heading ? (heading.dataset.default || heading.textContent) : '';
    function inlinePanel() { return desktop.matches; }
    var quickControls = root.querySelector('[data-quick-controls]');
    if (topFilters && quickControls) quickControls.hidden = false;
    var money = function (label) { return label.replace(/^Under\s*/i, ''); };
    sliders.forEach(function (slider) {
      var steps = JSON.parse(slider.dataset.steps);
      var group = slider.dataset.group;
      slider.hidden = false;
      var priceBox = boxes.filter(function (box) { return box.dataset.group === group; })[0];
      if (priceBox && priceBox.closest('fieldset')) priceBox.closest('fieldset').hidden = true;   // the chip rail replaces the Price checkboxes
      // Maximum-budget chips: choosing a band ticks that "Under" band (cumulative, as before); choosing it again, or Any, clears it.
      var n = steps.length;
      slider._lo = 0;
      function setMax(i) {
        slider._lo = 0;
        boxes.filter(function (box) { return box.dataset.group === group; }).forEach(function (box) { box.checked = i >= 0 && box.value === steps[i][0]; });
        update();
      }
      slider.querySelectorAll('.pb-chip').forEach(function (chip) {
        chip.addEventListener('click', function () {
          var i = Number(chip.dataset.step);
          setMax(i >= 0 && chip.getAttribute('aria-pressed') === 'true' ? -1 : i);
        });
      });
    });
    function ownIndex(card) {  // position of the watch's own price band among the slider steps (0 = no band given)
      var slider = sliders.filter(function (s) { return s.classList.contains('price-bands'); })[0];
      if (!slider) return 0;
      if (!slider._own) slider._own = JSON.parse(slider.dataset.steps).map(function (s) { return s[0]; });
      return slider._own.indexOf(card.dataset.own || '__none__') + 1;
    }
    function fromLimit() { var s = sliders.filter(function (x) { return x.classList.contains('price-bands'); })[0]; return s ? s._lo || 0 : 0; }
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
    // Magazine rhythm: the first watch shown (and one every 12 grid cells after it) is a wide lead card; an editorial tip follows every 6 cells.
    function rhythm(visible) {
      var cols = desktop.matches ? 3 : 2, units = 0, next = 0;
      cards.forEach(function (card) { card.classList.remove('is-lead'); });
      tips.forEach(function (tip) { tip.hidden = true; });
      visible.forEach(function (card, index) {
        var lead = visible.length >= 4 && units % 12 === 0;
        card.classList.toggle('is-lead', lead);
        units += lead ? cols : 1;
        if (units % 6 === 0 && next < tips.length && index < visible.length - 2) {
          card.insertAdjacentElement('afterend', tips[next]); tips[next].hidden = false; next++;
        }
      });
    }
    function passes(card, terms, selected, skip) {   // does a watch match the search, shopper path, From limit and every group except `skip`?
      return terms.every(function (term) { return card._searchText.indexOf(term) !== -1; }) &&
        (!gender || (card.dataset.gender || '').split(' ').indexOf(gender) !== -1) &&
        (fromLimit() === 0 || ownIndex(card) > fromLimit()) &&
        Object.keys(selected).every(function (group) {
          return group === skip || selected[group].some(function (value) { return (card.getAttribute('data-' + group) || '').split(' ').indexOf(value) !== -1; });
        });
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
        var matches = passes(card, terms, selected, '');
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
      var applyLabel = root.querySelector('[data-apply-label]');
      if (applyLabel) applyLabel.textContent = 'Show ' + matched.length + ' ' + (matched.length === 1 ? root.dataset.noun : plural);
      rhythm(matched.slice(start, end));
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
        var picked = (selected[slider.dataset.group] || []).filter(function (v) { return v !== 'unlisted'; });
        var values = steps.map(function (s) { return s[0]; });
        var hiAt = picked.length ? Math.max.apply(null, picked.map(function (v) { return values.indexOf(v) + 1; })) : 0;
        var loAt = slider._lo || 0;
        if (hiAt && loAt >= hiAt) loAt = Math.max(0, hiAt - 1);
        slider._lo = loAt;
        var any = !hiAt && !loAt;
        var text = any ? 'Any price' : !loAt ? 'Up to ' + money(steps[hiAt - 1][1]) : !hiAt ? money(steps[loAt - 1][1]) + ' and above' : money(steps[loAt - 1][1]) + ' \u2013 ' + money(steps[hiAt - 1][1]);
        slider.querySelector('[data-price-label]').textContent = text;
        var help = any ? 'Any price' : !loAt ? 'Showing watches under ' + money(steps[hiAt - 1][1]) : text;
        slider.querySelector('[data-price-help]').textContent = help + (any ? '' : ' \u00b7 ' + matched.length + (matched.length === 1 ? ' watch' : ' watches'));
        var rail = slider.querySelector('.pb-rail');
        Array.from(slider.querySelectorAll('.pb-chip')).forEach(function (chip) {
          var i = Number(chip.dataset.step);
          var on = i < 0 ? any : !loAt && hiAt === i + 1;
          chip.setAttribute('aria-pressed', on ? 'true' : 'false');
          if (i < 0) return;
          var count = cards.filter(function (card) { return passes(card, terms, selected, slider.dataset.group) && (card.getAttribute('data-' + slider.dataset.group) || '').split(' ').indexOf(steps[i][0]) !== -1; }).length;
          chip.disabled = count === 0 && !on;   // a band with no watch under the other filters cannot be chosen
          chip.setAttribute('aria-label', steps[i][1] + ', ' + count + (count === 1 ? ' watch' : ' watches'));
          if (on && rail.scrollWidth > rail.clientWidth) rail.scrollTo({ left: Math.max(0, chip.offsetLeft - 22), behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
        });
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
        var priceSlider = sliders.filter(function (x) { return x.classList.contains('price-bands'); })[0];
        var priceText = priceSlider ? priceSlider.querySelector('[data-price-label]').textContent : '';
        var brands = boxes.filter(function (box) {return box.dataset.group === 'brand' && box.checked;});
        var styles = boxes.filter(function (box) {return box.dataset.group === 'style' && box.checked;});
        var budgets = boxes.filter(function (box) {return box.dataset.group === 'budget' && box.checked;});
        function label(box) {return box.parentElement.querySelector('span').textContent;}
        heading.textContent = !gender && !brands.length && !styles.length && !budgets.length ? headingDefault :
          (brands.length === 1 ? label(brands[0]) + ' ' : '') + (gender === 'men' ? "Men's " : gender === 'women' ? "Women's " : '') +
          (styles.length === 1 ? label(styles[0]) + ' ' : '') + 'Watches' + (priceText && priceText !== 'Any price' ? ' ' + priceText : '');
      }
      active.replaceChildren();
      boxes.filter(function (box) { return box.checked; }).forEach(function (box) {
        removeButton(box.parentElement.querySelector('span').textContent, function () { box.checked = false; });
      });
      if (gender) removeButton(gender === 'men' ? "Men's" : "Women's", function () { gender = ''; });
      var fromAt = fromLimit();
      if (fromAt) { var fs = sliders.filter(function (x) { return x.classList.contains('price-bands'); })[0]; removeButton('From ' + money(JSON.parse(fs.dataset.steps)[fromAt - 1][1]), function () { fs._lo = 0; }); }
      if (query) removeButton('Search: ' + search.value.trim(), function () { search.value = ''; });
      var total = boxes.filter(function (box) { return box.checked; }).length + (gender ? 1 : 0) + (fromLimit() ? 1 : 0);
      root.querySelector('[data-filter-badge]').textContent = total ? '(' + total + ')' : '';
      if (typeof countGroups === 'function') countGroups();
      var chipBudget = root.querySelector('[data-chip-val="budget"]'), chipBrand = root.querySelector('[data-chip-val="brand"]');
      var bandsEl = sliders.filter(function (x) { return x.classList.contains('price-bands'); })[0];
      if (chipBudget && bandsEl) { var t = bandsEl.querySelector('[data-price-label]').textContent; chipBudget.textContent = t === 'Any price' ? '' : t; chipBudget.parentElement.classList.toggle('is-set', t !== 'Any price'); }
      if (chipBrand) {
        var picked = boxes.filter(function (b) { return b.dataset.group === 'brand' && b.checked; }).map(function (b) { return b.parentElement.querySelector('span').textContent; });
        chipBrand.textContent = picked.length > 1 ? picked.length + ' brands' : picked[0] || ''; chipBrand.parentElement.classList.toggle('is-set', picked.length > 0);
      }
      active.hidden = active.children.length === 0;
      if (!active.hidden) {
        var clear = document.createElement('button'); clear.type = 'button'; clear.className = 'linklike'; clear.textContent = 'Clear all'; clear.addEventListener('click', clearAll); active.appendChild(clear);
      }
      segments.forEach(function (button) { button.setAttribute('aria-pressed', button.dataset.gender === gender ? 'true' : 'false'); });
    }
    function clearAll() {
      boxes.forEach(function (box) { box.checked = false; }); gender = ''; search.value = ''; update();
    }
    // Filter groups collapse like a boutique menu. On laptops only the first three start open; the phone sheet starts fully open.
    var groups = Array.from(panel.querySelectorAll('.fgroup'));
    groups.forEach(function (group, index) {
      var legend = group.querySelector('legend');
      if (!legend) return;
      var title = legend.textContent;
      var button = document.createElement('button');
      button.type = 'button'; button.className = 'fg-toggle';
      button.innerHTML = '<span></span><b class="fg-n" aria-hidden="true"></b><i class="fg-chev" aria-hidden="true"></i>';
      button.firstChild.textContent = title;
      legend.textContent = ''; legend.appendChild(button);
      var collapsed = desktop.matches && index >= 3;
      group.classList.toggle('is-collapsed', collapsed);
      button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      button.addEventListener('click', function () {
        var shut = group.classList.toggle('is-collapsed');
        button.setAttribute('aria-expanded', shut ? 'false' : 'true');
      });
    });
    function countGroups() {
      groups.forEach(function (group) {
        var n = group.querySelectorAll('input:checked').length, badge = group.querySelector('.fg-n');
        if (badge) badge.textContent = n ? String(n) : '';
        group.classList.toggle('has-sel', n > 0);
      });
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
        var anchorEl = root.querySelector('[data-collection-count]'); if (anchorEl && button.classList.contains('lx-style')) anchorEl.scrollIntoView({ block: 'center', behavior: 'smooth' });
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
    openers.forEach(function (opener) {
      opener.addEventListener('click', function () {
        if (panel.open || inlinePanel()) return;
        panel.showModal(); document.documentElement.classList.add('collection-modal-open');
        var jump = opener.dataset.jump;   // a Budget or Brand chip opens the sheet at that section
        var target = jump === 'budget' ? panel.querySelector('.price-slider') : jump ? panel.querySelector('[data-fgroup="' + jump + '"]') : null;
        panel.scrollTop = target ? Math.max(0, target.offsetTop - 84) : 0;
      });
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
      if (typeof update === 'function') update(false);
    }
    desktop.addEventListener('change', resize);
    // /watches/?price=under-3000 (the home page slider) opens the list with that price band chosen
    var query = new URLSearchParams(window.location.search);
    var from = query.get('from');   // /watches/?price=under-3000&from=under-2000 opens the 2,000 to 3,000 range
    if (from) sliders.forEach(function (slider) {
      var at = JSON.parse(slider.dataset.steps).map(function (step) { return step[0]; }).indexOf(from);
      if (at >= 0 && slider.classList.contains('price-bands')) slider._lo = at + 1;
    });
    var wanted = query.get('price');
    if (wanted) boxes.forEach(function (box) { if (box.dataset.group === 'budget' && box.value === wanted) box.checked = true; });
    resize(); update();
  });
})();
