(function () {
  'use strict';
  document.querySelectorAll('[data-collection]').forEach(function (root) {
    var store = root.hasAttribute('data-store');   // the Watches page: filter panel is always a sheet or drawer, with visual sub-sheets
    var grid = root.querySelector('[data-collection-grid]');
    var cards = Array.from(grid.children);
    var panel = root.querySelector('[data-filter-panel]');
    var boxes = Array.from(panel.querySelectorAll('input'));
    var search = root.querySelector('[data-search]');
    var sort = root.querySelector('[data-sort]');
    var active = root.querySelector('[data-active]');
    var gender = root.dataset.presetGender || '';
    var segments = Array.from(root.querySelectorAll('[data-gender]'));
    var plate = root.querySelector('.gender-plate');
    var genderBoxes = boxes.filter(function (box) { return box.dataset.group === 'gender'; });
    var desktop = window.matchMedia('(min-width: 1000px)');
    var openers = Array.from(root.querySelectorAll('[data-filter-open]'));
    var plural = root.dataset.plural;
    var topFilters = root.hasAttribute('data-top-filters');
    var quick = Array.from(root.querySelectorAll('[data-quick-filter]'));
    var styleButtons = Array.from(root.querySelectorAll('[data-style-toggle]'));
    var chips = Array.from(root.querySelectorAll('[data-quick-chip]'));
    var sliders = Array.from(root.querySelectorAll('[data-price-slider]'));
    var brandTiles = Array.from(root.querySelectorAll('[data-brand-tile]'));
    var pager = root.querySelector('[data-pagination]');
    var pageSize = Number(root.dataset.pageSize) || 0;
    var page = 1;
    var heading = topFilters ? root.closest('.watch-store').querySelector('h1') : null;
    var headingDefault = heading ? (heading.dataset.default || heading.textContent) : '';
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    function inlinePanel() { return !store && desktop.matches; }
    var quickControls = root.querySelector('[data-quick-controls]');
    if (topFilters && quickControls) quickControls.hidden = false;
    var money = function (label) { return label.replace(/^Under\s*/i, ''); };
    function labelOf(box) { return box.parentElement.querySelector('span').textContent; }
    function bandsSlider() { return sliders.filter(function (s) { return s.classList.contains('price-bands'); })[0]; }
    function toResults() {
      var anchorEl = root.querySelector('[data-collection-count]');
      if (anchorEl) anchorEl.scrollIntoView({ block: 'center', behavior: reduce.matches ? 'auto' : 'smooth' });
    }
    sliders.forEach(function (slider) {
      var steps = JSON.parse(slider.dataset.steps);
      var group = slider.dataset.group;
      slider.hidden = false;
      var priceBox = boxes.filter(function (box) { return box.dataset.group === group; })[0];
      if (priceBox && priceBox.closest('fieldset')) priceBox.closest('fieldset').hidden = true;   // the budget rail replaces the Price checkboxes
      // Stepped budget rail: choosing a step ticks that "Under" band (cumulative, as before); choosing it again, or Any, clears it.
      slider._lo = 0;
      function setMax(i) {
        slider._lo = 0;
        boxes.filter(function (box) { return box.dataset.group === group; }).forEach(function (box) { box.checked = i >= 0 && box.value === steps[i][0]; });
        update();
      }
      slider._setMax = setMax;
      slider.querySelectorAll('.sr-step').forEach(function (step) {
        step.addEventListener('click', function () {
          var i = Number(step.dataset.step);
          setMax(i >= 0 && step.getAttribute('aria-pressed') === 'true' ? -1 : i);
        });
      });
      var clearBudget = slider.querySelector('[data-price-clear]');
      if (clearBudget) clearBudget.addEventListener('click', function () { setMax(-1); });
    });
    function ownIndex(card) {  // position of the watch's own price band among the slider steps (0 = no band given)
      var slider = bandsSlider();
      if (!slider) return 0;
      if (!slider._own) slider._own = JSON.parse(slider.dataset.steps).map(function (s) { return s[0]; });
      return slider._own.indexOf(card.dataset.own || '__none__') + 1;
    }
    function fromLimit() { var s = bandsSlider(); return s ? s._lo || 0 : 0; }
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
      if (genderBoxes.length) {   // the Men / Women plate and the Gender rows are the same filter
        var gs = genderBoxes.filter(function (box) { return box.checked; });
        gender = gs.length === 1 ? gs[0].value : '';
      }
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
      var cfCount = root.querySelector('[data-cf-count]');
      if (cfCount) cfCount.textContent = matched.length + (matched.length === 1 ? ' match' : ' matches');
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
      var budgetValue = 'Any price';
      sliders.forEach(function (slider) {
        var steps = JSON.parse(slider.dataset.steps);
        var picked = (selected[slider.dataset.group] || []).filter(function (v) { return v !== 'unlisted'; });
        var values = steps.map(function (s) { return s[0]; });
        var hiAt = picked.length ? Math.max.apply(null, picked.map(function (v) { return values.indexOf(v) + 1; })) : 0;
        var loAt = slider._lo || 0;
        if (hiAt && loAt >= hiAt) loAt = Math.max(0, hiAt - 1);
        slider._lo = loAt;
        var any = !hiAt && !loAt;
        var text = any ? 'Any price' : !loAt ? 'Up to ' + money(steps[hiAt - 1][1]) : !hiAt ? money(steps[loAt - 1][1]) + ' and above' : money(steps[loAt - 1][1]) + ' – ' + money(steps[hiAt - 1][1]);
        slider.querySelector('[data-price-label]').textContent = text;
        var shortText = any ? 'Any price' : !loAt ? 'Under ' + money(steps[hiAt - 1][1]) : text;
        budgetValue = shortText;
        slider.querySelector('[data-price-help]').textContent = shortText;
        var clearBudget = slider.querySelector('[data-price-clear]');
        if (clearBudget) clearBudget.disabled = any;
        var sel = !loAt && hiAt ? hiAt : 0;   // position of the chosen step on the rail (Any is 0)
        slider.style.setProperty('--sel', String(sel));
        slider.classList.toggle('has-sel', sel > 0);
        var tip = slider.querySelector('[data-price-tip]');
        if (tip) tip.textContent = sel ? shortText : '';
        Array.from(slider.querySelectorAll('.sr-step')).forEach(function (step) {
          var i = Number(step.dataset.step);
          var on = i < 0 ? any : sel === i + 1;
          step.setAttribute('aria-pressed', on ? 'true' : 'false');
          step.classList.toggle('is-reached', i + 1 <= sel);
          if (i < 0) return;
          var n = cards.filter(function (card) { return passes(card, terms, selected, slider.dataset.group) && (card.getAttribute('data-' + slider.dataset.group) || '').split(' ').indexOf(steps[i][0]) !== -1; }).length;
          step.disabled = n === 0 && !on;   // a band with no watch under the other filters cannot be chosen
          step.setAttribute('aria-label', steps[i][1] + ', ' + n + (n === 1 ? ' watch' : ' watches'));
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
      root.querySelectorAll('[data-intent]').forEach(function (card) {
        var parts = card.dataset.intent.split(':');
        var onlyThis = Object.keys(selected).filter(function (g) { return g !== 'gender'; });
        card.setAttribute('aria-current', onlyThis.length === 1 && onlyThis[0] === parts[0] && selected[parts[0]].length === 1 && selected[parts[0]][0] === parts[1] ? 'true' : 'false');
      });
      brandTiles.forEach(function (tile) { tile.setAttribute('aria-current', (selected.brand || []).indexOf(tile.dataset.brandTile) !== -1 ? 'true' : 'false'); });
      if (heading && !heading.hasAttribute('data-static')) {
        var brands = boxes.filter(function (box) {return box.dataset.group === 'brand' && box.checked;});
        var styles = boxes.filter(function (box) {return box.dataset.group === 'style' && box.checked;});
        var budgets = boxes.filter(function (box) {return box.dataset.group === 'budget' && box.checked;});
        var priceText = budgetValue === 'Any price' ? '' : budgetValue.replace(/^Under /, 'Up to ');
        heading.textContent = !gender && !brands.length && !styles.length && !budgets.length ? headingDefault :
          (brands.length === 1 ? labelOf(brands[0]) + ' ' : '') + (gender === 'men' ? "Men's " : gender === 'women' ? "Women's " : '') +
          (styles.length === 1 ? labelOf(styles[0]) + ' ' : '') + 'Watches' + (priceText ? ' ' + priceText : '');
      }
      active.replaceChildren();
      boxes.filter(function (box) { return box.checked; }).forEach(function (box) {
        removeButton(labelOf(box), function () { box.checked = false; });
      });
      if (gender && !genderBoxes.length) removeButton(gender === 'men' ? "Men's" : "Women's", function () { gender = ''; });
      var fromAt = fromLimit();
      if (fromAt) { var fs = bandsSlider(); removeButton('From ' + money(JSON.parse(fs.dataset.steps)[fromAt - 1][1]), function () { fs._lo = 0; }); }
      if (query) removeButton('Search: ' + search.value.trim(), function () { search.value = ''; });
      var total = boxes.filter(function (box) { return box.checked; }).length + (gender && !genderBoxes.length ? 1 : 0) + (fromLimit() ? 1 : 0);
      root.querySelector('[data-filter-badge]').textContent = total ? '(' + total + ')' : '';
      if (store && total) count.textContent += ' · refined by your choices';
      countGroups();
      quickValues(selected, budgetValue);
      active.hidden = active.children.length === 0;
      if (!active.hidden) {
        var clear = document.createElement('button'); clear.type = 'button'; clear.className = 'linklike'; clear.textContent = 'Clear all'; clear.addEventListener('click', clearAll); active.appendChild(clear);
      }
      segments.forEach(function (button) { button.setAttribute('aria-pressed', button.dataset.gender === gender ? 'true' : 'false'); });
      if (plate) plate.dataset.pick = gender;
      syncSubs();
    }
    function clearAll() {
      boxes.forEach(function (box) { box.checked = false; }); gender = ''; search.value = ''; update();
    }
    // Quick filter row under the hero: the current choice for Budget, Brand, Style and the other filters.
    function quickValues(selected, budgetValue) {
      root.querySelectorAll('[data-qa-val]').forEach(function (el) {
        var key = el.dataset.qaVal, text = el.dataset.qaDefault;
        if (key === 'budget') text = budgetValue === 'Any price' ? text : budgetValue;
        else if (key === 'brand' || key === 'style') {
          var names = boxes.filter(function (b) { return b.dataset.group === key && b.checked; }).map(labelOf);
          if (names.length) text = names.length > 2 ? names.length + ' selected' : names.join(', ');
        } else {
          var more = groups.filter(function (g) { return ['brand', 'budget', 'style', 'gender'].indexOf(g.dataset.fgroup) === -1 && g.querySelector('input:checked'); }).map(function (g) { return g.querySelector('.fg-title').textContent; });
          if (more.length) text = more.length > 2 ? more.length + ' selected' : more.join(', ');
        }
        el.textContent = text;
      });
    }
    // Filter groups are boutique-menu rows: title, the current choice, a chevron. Case size and Strap open a visual sub-sheet.
    var groups = Array.from(panel.querySelectorAll('.fgroup'));
    var subKeys = store ? ['dial', 'strapmat'] : [];
    var subs = {};
    groups.forEach(function (group, index) {
      var legend = group.querySelector('legend');
      if (!legend) return;
      var key = group.dataset.fgroup;
      var title = legend.textContent;
      var button = document.createElement('button');
      button.type = 'button'; button.className = 'fg-toggle';
      button.innerHTML = '<span class="fg-lab"><span class="fg-title"></span><em class="fg-sum"></em></span><b class="fg-n" aria-hidden="true"></b><i class="fg-chev" aria-hidden="true"></i>';
      button.querySelector('.fg-title').textContent = title;
      legend.textContent = ''; legend.appendChild(button);
      var hasSub = subKeys.indexOf(key) !== -1;
      var collapsed = store ? true : desktop.matches && index >= 3;
      group.classList.toggle('is-collapsed', collapsed);
      group.classList.toggle('has-sub', hasSub);
      button.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      button.addEventListener('click', function () {
        if (hasSub) { openSub(key); return; }
        var shut = group.classList.toggle('is-collapsed');
        button.setAttribute('aria-expanded', shut ? 'false' : 'true');
      });
    });
    function countGroups() {
      groups.forEach(function (group) {
        var checked = Array.from(group.querySelectorAll('input:checked')), badge = group.querySelector('.fg-n'), sum = group.querySelector('.fg-sum');
        if (badge) badge.textContent = checked.length ? String(checked.length) : '';
        if (sum) sum.textContent = checked.length ? checked.map(labelOf).join(', ') : 'Any';
        group.classList.toggle('has-sel', checked.length > 0);
      });
    }
    // ---- visual sub-sheets (Case size, Strap) ----
    var DIAL_CARDS = { '36-and-under': ['Small', '≤36 mm', 14], '37-40': ['Balanced', '37–40 mm', 18], '41-44': ['Bold', '41–44 mm', 22], '45-plus': ['Oversized', '45 mm+', 26] };
    var STRAPS = [['Leather', 'Classic look', ['leather'], 'leather'], ['Metal', 'Formal / durable', ['stainless-steel', 'brass', 'metal'], 'metal'], ['Mesh', 'Slim / modern', ['mesh'], 'mesh'],
                  ['Silicone', 'Sporty', ['silicone-rubber'], 'silicone'], ['Nylon', 'Lightweight', ['fabric-nylon'], 'nylon'], ['Other', 'Unique styles', ['ceramic', 'resin', 'plastic', 'polyurethane'], 'other']];
    function caseSvg(r) {
      return '<svg viewBox="0 0 60 70" aria-hidden="true"><rect x="22" y="2" width="16" height="16" rx="3"/><rect x="22" y="52" width="16" height="16" rx="3"/><circle cx="30" cy="35" r="' + r + '"/><circle cx="30" cy="35" r="' + (r - 4) + '"/><path d="M30 35V26M30 35l6 3"/></svg>';
    }
    function strapSvg(kind) {
      var body = '<rect x="12" y="4" width="36" height="62" rx="9"/>';
      var tex = { leather: '<path d="M16 8v54M44 8v54" stroke-dasharray="2.5 3"/>', metal: '<path d="M12 18h36M12 30h36M12 42h36M12 54h36"/>', mesh: '<path d="M14 14l32 12M14 26l32 12M14 38l32 12M46 14L14 26M46 26L14 38M46 38L14 50"/>',
                  silicone: '<circle cx="30" cy="18" r="2.2"/><circle cx="30" cy="30" r="2.2"/><circle cx="30" cy="42" r="2.2"/><circle cx="30" cy="54" r="2.2"/>', nylon: '<path d="M18 6v58M26 6v58M34 6v58M42 6v58"/>', other: '<circle cx="22" cy="20" r="2"/><circle cx="38" cy="30" r="2"/><circle cx="24" cy="44" r="2"/><circle cx="38" cy="56" r="2"/>' };
      return '<svg viewBox="0 0 60 70" aria-hidden="true">' + body + tex[kind] + '</svg>';
    }
    function buildSub(key) {
      var group = panel.querySelector('[data-fgroup="' + key + '"]');
      if (!group) return null;
      var title = group.querySelector('.fg-title').textContent;
      var dlg = document.createElement('dialog');
      dlg.className = 'collection-sub'; dlg.setAttribute('aria-label', title);
      dlg.innerHTML = '<div class="sub-head"><div><strong></strong><span class="sub-count"></span></div><button type="button" class="cf-x" aria-label="Close">✕</button></div><div class="sub-body"></div><div class="sub-foot"><button type="button" class="btn btn-primary">Apply</button></div>';
      dlg.querySelector('strong').textContent = title;
      var body = dlg.querySelector('.sub-body'), cardsEl = document.createElement('div');
      cardsEl.className = key === 'dial' ? 'sub-cards sub-cards-4' : 'sub-cards sub-cards-3';
      var groupBoxes = Array.from(group.querySelectorAll('input'));
      var defs = [];
      if (key === 'dial') {
        groupBoxes.forEach(function (box) { var d = DIAL_CARDS[box.value]; if (d) defs.push({ name: d[0], note: d[1], art: caseSvg(d[2]), boxes: [box] }); });
      } else {
        STRAPS.forEach(function (s) {
          var mine = groupBoxes.filter(function (box) { return s[2].indexOf(box.value) !== -1; });
          if (mine.length) defs.push({ name: s[0], note: s[1], art: strapSvg(s[3]), boxes: mine });
        });
      }
      defs.forEach(function (d) {
        var b = document.createElement('button');
        b.type = 'button'; b.className = 'sub-card';
        b.innerHTML = '<span class="sub-art">' + d.art + '</span><strong></strong><small></small>';
        b.querySelector('strong').textContent = d.name; b.querySelector('small').textContent = d.note;
        b.addEventListener('click', function () {
          var on = !d.boxes.every(function (box) { return box.checked; });
          d.boxes.forEach(function (box) { if (!box.disabled) box.checked = on; });
          update();
        });
        d._el = b; cardsEl.appendChild(b);
      });
      body.appendChild(cardsEl);
      if (key === 'dial') {
        var sizes = [];
        try { sizes = JSON.parse(panel.dataset.sizes || '[]'); } catch (e) { sizes = []; }
        if (sizes.length) {
          var q = document.createElement('div'); q.className = 'sub-quick';
          q.innerHTML = '<p class="sub-note">Common sizes for everyday wear.</p><h4>Quick select</h4><div class="sub-sizes"></div>';
          sizes.forEach(function (s) {
            var b = document.createElement('button'); b.type = 'button'; b.className = 'sub-size'; b.textContent = s[0] + ' mm';
            b.addEventListener('click', function () {
              groupBoxes.forEach(function (box) { box.checked = box.value === s[1] && !box.disabled; });
              update();
            });
            q.querySelector('.sub-sizes').appendChild(b);
          });
          body.appendChild(q);
        }
      }
      dlg.querySelector('.cf-x').addEventListener('click', function () { dlg.close(); });
      dlg.querySelector('.sub-foot .btn').addEventListener('click', function () { dlg.close(); });
      dlg.addEventListener('click', function (event) {
        var rect = dlg.getBoundingClientRect();
        if (event.clientY < rect.top || event.clientX < rect.left || event.clientX > rect.right) dlg.close();
      });
      root.appendChild(dlg);
      return { dlg: dlg, defs: defs, boxes: groupBoxes };
    }
    function syncSubs() {
      Object.keys(subs).forEach(function (key) {
        var s = subs[key], n = s.defs.filter(function (d) { return d.boxes.every(function (box) { return box.checked; }); }).length;
        s.dlg.querySelector('.sub-count').textContent = n ? n + ' selected' : 'None selected';
        s.defs.forEach(function (d) {
          var on = d.boxes.every(function (box) { return box.checked; });
          d._el.setAttribute('aria-pressed', on ? 'true' : 'false');
          d._el.disabled = d.boxes.every(function (box) { return box.disabled; });
        });
      });
    }
    function openSub(key) {
      if (!subs[key]) subs[key] = buildSub(key);
      if (!subs[key]) return;
      syncSubs();
      subs[key].dlg.tabIndex = -1; subs[key].dlg.showModal(); subs[key].dlg.focus({ preventScroll: true });
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
          box.checked = !on;
          if (!on) { if (genderBoxes.length) genderBoxes.forEach(function (g) { g.checked = g.value === chip.dataset.chipGender; }); else gender = chip.dataset.chipGender; }
        } else { box.checked = !box.checked; }
        update();
      });
    });
    styleButtons.forEach(function (button) {
      button.addEventListener('click', function (event) {
        event.preventDefault();
        var selected = button.getAttribute('aria-current') === 'true';
        boxes.filter(function (box) { return box.dataset.group === 'style'; }).forEach(function (box) { box.checked = !selected && box.value === button.dataset.styleToggle; }); update();
        if (button.classList.contains('lx-style')) toResults();
      });
    });
    brandTiles.forEach(function (tile) {
      tile.addEventListener('click', function (event) {
        event.preventDefault();
        var box = boxes.filter(function (b) { return b.dataset.group === 'brand' && b.value === tile.dataset.brandTile; })[0];
        if (!box) return;
        var was = box.checked;
        boxes.filter(function (b) { return b.dataset.group === 'brand'; }).forEach(function (b) { b.checked = false; });
        box.checked = !was; update(); toResults();
      });
    });
    root.querySelectorAll('[data-intent]').forEach(function (card) {   // "What are you looking for?" cards apply an existing filter
      card.addEventListener('click', function (event) {
        event.preventDefault();   // the link still works without scripts; with scripts the filter is applied in place
        var parts = card.dataset.intent.split(':'), group = parts[0], value = parts[1];
        var slider = bandsSlider();
        // an intent replaces the other filters (the shopper path Men / Women stays), so its promised count is what appears
        boxes.forEach(function (b) { if (b.dataset.group !== 'gender') b.checked = false; });
        if (slider) slider._lo = 0;
        search.value = '';
        if (group === 'budget' && slider) {
          var at = JSON.parse(slider.dataset.steps).map(function (s) { return s[0]; }).indexOf(value);
          if (at >= 0) { slider._setMax(at); toResults(); return; }
        }
        boxes.filter(function (b) { return b.dataset.group === group && b.value === value; }).forEach(function (b) { b.checked = true; });
        update();
        toResults();
      });
    });
    segments.forEach(function (button) {
      button.addEventListener('click', function () {
        var value = button.dataset.gender;
        if (genderBoxes.length) {
          var box = genderBoxes.filter(function (b) { return b.value === value; })[0];
          var was = box && box.checked;
          genderBoxes.forEach(function (b) { b.checked = false; });
          if (box && !was) box.checked = true;
        } else { gender = gender === value ? '' : value; }
        update();
      });
    });
    sort.addEventListener('change', function () {
      var ordered = cards.slice().sort(function (a, b) {
        if (sort.value === 'featured') return Number(a.dataset.order) - Number(b.dataset.order);
        var result = (a.dataset.name || a.querySelector('h3').textContent).localeCompare(b.dataset.name || b.querySelector('h3').textContent, 'en-IN', { numeric: true });
        return sort.value === 'name-desc' ? -result : result;
      });
      ordered.forEach(function (card) { grid.appendChild(card); }); cards = ordered; update();
    });
    root.querySelectorAll('[data-filter-clear]').forEach(function (button) { button.addEventListener('click', clearAll); });
    // saved watches: a heart on each card, remembered in this browser only
    var saved = [];
    try { saved = JSON.parse(localStorage.getItem('sat-saved-watches') || '[]'); } catch (e) { saved = []; }
    root.querySelectorAll('[data-fav]').forEach(function (heart) {
      heart.setAttribute('aria-pressed', saved.indexOf(heart.dataset.fav) !== -1 ? 'true' : 'false');
      heart.addEventListener('click', function () {
        var i = saved.indexOf(heart.dataset.fav);
        if (i === -1) saved.push(heart.dataset.fav); else saved.splice(i, 1);
        heart.setAttribute('aria-pressed', i === -1 ? 'true' : 'false');
        try { localStorage.setItem('sat-saved-watches', JSON.stringify(saved)); } catch (e) { /* private mode: the heart still works for this visit */ }
      });
    });
    function closeSheet() { if (!inlinePanel() && panel.open) panel.close(); }
    var JUMPS = { more: 'dial' };
    openers.forEach(function (opener) {
      opener.addEventListener('click', function () {
        if (panel.open || inlinePanel()) return;
        panel.tabIndex = -1; panel.showModal(); panel.focus({ preventScroll: true }); document.documentElement.classList.add('collection-modal-open');
        var jump = JUMPS[opener.dataset.jump] || opener.dataset.jump;   // a quick filter opens the panel at that section
        var target = jump === 'budget' ? panel.querySelector('.price-slider') : jump ? panel.querySelector('[data-fgroup="' + jump + '"]') : null;
        if (target && target.classList.contains('fgroup') && target.classList.contains('is-collapsed') && !target.classList.contains('has-sub')) {
          target.classList.remove('is-collapsed'); target.querySelector('.fg-toggle').setAttribute('aria-expanded', 'true');
        }
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
