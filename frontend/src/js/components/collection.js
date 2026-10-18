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
    var premium = null;   // {from, top, label, heading}: the Premium range shown as one label (the filter underneath is a lower limit plus a top band)
    try { premium = JSON.parse(root.dataset.premium || 'null'); } catch (e) { premium = null; }
    var heading = topFilters ? root.closest('.watch-store').querySelector('h1') : null;
    var headingDefault = heading ? (heading.dataset.default || heading.textContent) : '';
    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
    var docEl = document.documentElement;
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
    // the sheet's own parts (the Watches page only)
    var cfBody = panel.querySelector('[data-cf-body]');
    var cfHead = panel.querySelector('[data-cf-head]');
    var cfFoot = panel.querySelector('[data-cf-foot]');
    var cfActive = panel.querySelector('[data-cf-active]');
    var cfQuick = panel.querySelector('[data-cf-quick]');
    var cfZero = panel.querySelector('[data-cf-zero]');
    var cfUndo = panel.querySelector('[data-cf-undo]');
    var cfReset = panel.querySelector('.cf-reset');
    var applyLabel = root.querySelector('[data-apply-label]');
    var lastCount = cards.length;
    var undoPick = null;   // the chip whose removal brings back the most watches (used by "Clear one filter")
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
    // ---- the filter state, and which watches pass it ----
    function has(card, group, value) {   // does the watch carry this value for the group? (attributes are static, so they are split once)
      var cache = card._tok || (card._tok = {});
      var list = cache[group] || (cache[group] = (card.getAttribute('data-' + group) || '').split(' '));
      return list.indexOf(value) !== -1;
    }
    function readState() {
      if (genderBoxes.length) {   // the Men / Women plate and the Gender rows are the same filter
        var gs = genderBoxes.filter(function (box) { return box.checked; });
        gender = gs.length === 1 ? gs[0].value : '';
      }
      var selected = {};
      boxes.forEach(function (box) {
        if (box.checked) (selected[box.dataset.group] || (selected[box.dataset.group] = [])).push(box.value);
      });
      return { terms: search.value.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean), gender: gender, lo: fromLimit(), selected: selected };
    }
    function cloneState(st) {
      var selected = {};
      Object.keys(st.selected).forEach(function (g) { selected[g] = st.selected[g].slice(); });
      return { terms: st.terms, gender: st.gender, lo: st.lo, selected: selected };
    }
    function passes(card, st, skip) {   // does a watch match the search, shopper path, From limit and every group except `skip`?
      return st.terms.every(function (term) { return card._searchText.indexOf(term) !== -1; }) &&
        (skip === 'gender' || !st.gender || has(card, 'gender', st.gender)) &&
        (st.lo === 0 || ownIndex(card) > st.lo) &&
        Object.keys(st.selected).every(function (group) {
          return group === skip || st.selected[group].some(function (value) { return has(card, group, value); });
        });
    }
    function countFor(st) { return cards.filter(function (card) { return passes(card, st, ''); }).length; }
    var pools = {};
    function pool(st, group) { return pools[group] || (pools[group] = cards.filter(function (card) { return passes(card, st, group); })); }
    // one removable filter: label, how to remove it, and the state without it
    function items(st, premiumOn) {
      var list = [];
      boxes.forEach(function (box) {
        if (!box.checked || (premiumOn && box.dataset.group === 'budget')) return;
        list.push({ label: labelOf(box), remove: function () { box.checked = false; }, drop: function (s) {
          var g = box.dataset.group;
          s.selected[g] = (s.selected[g] || []).filter(function (v) { return v !== box.value; });
          if (!s.selected[g].length) delete s.selected[g];
          if (g === 'gender' && genderBoxes.length) s.gender = s.selected.gender && s.selected.gender.length === 1 ? s.selected.gender[0] : '';
        } });
      });
      if (premiumOn) list.push({ label: premium.label, remove: function () {   // one chip for the whole Premium range; removing it clears both internal filters
        boxes.forEach(function (box) { if (box.dataset.group === 'budget') box.checked = false; });
        var ps = bandsSlider(); if (ps) ps._lo = 0;
      }, drop: function (s) { delete s.selected.budget; s.lo = 0; } });
      if (gender && !genderBoxes.length) list.push({ label: gender === 'men' ? "Men's" : "Women's", remove: function () { gender = ''; }, drop: function (s) { s.gender = ''; } });
      var fromAt = fromLimit();
      if (fromAt && !premiumOn) { var fs = bandsSlider(); list.push({ label: 'From ' + money(JSON.parse(fs.dataset.steps)[fromAt - 1][1]), remove: function () { fs._lo = 0; }, drop: function (s) { s.lo = 0; } }); }
      if (st.terms.length) list.push({ label: 'Search: ' + search.value.trim(), remove: function () { search.value = ''; }, drop: function (s) { s.terms = []; } });
      return list;
    }
    function chipButton(item, extraClass) {
      var button = document.createElement('button');
      button.type = 'button'; button.className = 'filter-chip' + (extraClass ? ' ' + extraClass : '');
      var text = document.createElement('span'); text.textContent = item.label;
      var cross = document.createElement('i'); cross.setAttribute('aria-hidden', 'true'); cross.textContent = '×';
      button.appendChild(text); button.appendChild(cross);
      button.setAttribute('aria-label', 'Remove ' + item.label + ' filter');
      button.addEventListener('click', function () { item.remove(); update(); });
      return button;
    }
    function update(resetPage) {
      if (resetPage !== false) page = 1;
      var st = readState();
      var selected = st.selected;
      var terms = st.terms;
      pools = {};
      var query = terms.join(' ');
      var matched = [];
      cards.forEach(function (card) {
        var matches = passes(card, st, '');
        if (matches) matched.push(card);
        card.hidden = true;
      });
      lastCount = matched.length;
      var totalPages = pageSize ? Math.max(1, Math.ceil(matched.length / pageSize)) : 1;
      page = Math.min(page, totalPages);
      var start = pageSize ? (page - 1) * pageSize : 0;
      var end = pageSize ? Math.min(start + pageSize, matched.length) : matched.length;
      matched.slice(start, end).forEach(function (card) { card.hidden = false; });
      var count = root.querySelector('[data-collection-count]');
      count.textContent = (pageSize && matched.length > pageSize ? (start + 1) + '–' + end + ' of ' : '') + matched.length + ' ' + (matched.length === 1 ? root.dataset.noun : plural);
      root.querySelector('[data-empty]').hidden = matched.length !== 0;
      var noun = matched.length === 1 ? root.dataset.noun : plural;
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
      var premiumOn = false;
      sliders.forEach(function (slider) {
        var steps = JSON.parse(slider.dataset.steps);
        var picked = (selected[slider.dataset.group] || []).filter(function (v) { return v !== 'unlisted'; });
        var values = steps.map(function (s) { return s[0]; });
        var hiAt = picked.length ? Math.max.apply(null, picked.map(function (v) { return values.indexOf(v) + 1; })) : 0;
        var loAt = slider._lo || 0;
        if (hiAt && loAt >= hiAt) loAt = Math.max(0, hiAt - 1);
        slider._lo = loAt; st.lo = fromLimit();
        var any = !hiAt && !loAt;
        var text = any ? 'Any price' : !loAt ? 'Up to ' + money(steps[hiAt - 1][1]) : !hiAt ? money(steps[loAt - 1][1]) + ' and above' : money(steps[loAt - 1][1]) + ' – ' + money(steps[hiAt - 1][1]);
        var shortText = any ? 'Any price' : !loAt ? 'Under ' + money(steps[hiAt - 1][1]) : text;
        if (premium && slider.classList.contains('price-bands')) {   // from the end of the last tier up to the top band is the Premium range
          var pf = values.indexOf(premium.from), pt = values.indexOf(premium.top);
          if (pf >= 0 && pt >= 0 && loAt === pf + 1 && (!hiAt || hiAt >= pt + 1)) { premiumOn = true; text = shortText = premium.label; }
        }
        slider.querySelector('[data-price-label]').textContent = text;
        budgetValue = shortText;
        slider.querySelector('[data-price-help]').textContent = shortText;
        var clearBudget = slider.querySelector('[data-price-clear]');
        if (clearBudget) clearBudget.disabled = any;
        var sel = !loAt && hiAt ? hiAt : 0;   // position of the chosen step on the rail (Any is 0)
        slider.style.setProperty('--sel', String(sel));
        slider.classList.toggle('has-sel', sel > 0);
        var tip = slider.querySelector('[data-price-tip]');
        if (tip) tip.textContent = sel ? shortText : '';
        var poolForBudget = pool(st, slider.dataset.group);
        Array.from(slider.querySelectorAll('.sr-step')).forEach(function (step) {
          var i = Number(step.dataset.step);
          var on = i < 0 ? any : sel === i + 1;
          step.setAttribute('aria-pressed', on ? 'true' : 'false');
          step.classList.toggle('is-reached', i + 1 <= sel);
          if (i < 0) return;
          var n = poolForBudget.filter(function (card) { return has(card, slider.dataset.group, steps[i][0]); }).length;
          step.disabled = n === 0 && !on;   // a band with no watch under the other filters cannot be chosen
          step.classList.toggle('is-dim', n === 0 && !on);
          step.setAttribute('aria-label', steps[i][1] + ', ' + n + (n === 1 ? ' watch' : ' watches'));
          step._n = n;
          if (n === 0 && !on) step.title = 'No watch matches your other choices'; else step.removeAttribute('title');
        });
        slider._steps = steps;
      });
      styleButtons.forEach(function (button) {
        var values = selected.style || [];
        var tile = button.dataset.styleToggle;
        var chosen = !tile ? !values.length : values.indexOf(tile) !== -1;
        // a style with no watch under the other filters is hidden: tapping it would only show an empty list
        button.hidden = !!tile && !chosen && !cards.some(function (card) {
          return (!gender || has(card, 'gender', gender)) && has(card, 'style', tile) &&
            Object.keys(selected).every(function (group) {
              return group === 'style' || selected[group].some(function (value) { return has(card, group, value); });
            });
        });
        button.setAttribute('aria-current', (!button.dataset.styleToggle ? !values.length : values.indexOf(button.dataset.styleToggle) !== -1) ? 'true' : 'false');
      });
      brandTiles.forEach(function (tile) { tile.setAttribute('aria-current', (selected.brand || []).indexOf(tile.dataset.brandTile) !== -1 ? 'true' : 'false'); });
      if (heading && !heading.hasAttribute('data-static')) {
        var brands = boxes.filter(function (box) {return box.dataset.group === 'brand' && box.checked;});
        var styles = boxes.filter(function (box) {return box.dataset.group === 'style' && box.checked;});
        var budgets = boxes.filter(function (box) {return box.dataset.group === 'budget' && box.checked;});
        var priceText = budgetValue === 'Any price' ? '' : budgetValue.replace(/^Under /, 'Up to ');
        heading.textContent = !gender && !brands.length && !styles.length && !budgets.length && !premiumOn ? headingDefault :
          (brands.length === 1 ? labelOf(brands[0]) + ' ' : '') + (gender === 'men' ? "Men's " : gender === 'women' ? "Women's " : '') +
          (styles.length === 1 ? labelOf(styles[0]) + ' ' : '') + (premiumOn ? premium.heading : 'Watches' + (priceText ? ' ' + priceText : ''));
      }
      var list = items(st, premiumOn);
      active.replaceChildren();
      list.forEach(function (item) { active.appendChild(chipButton(item)); });
      var total = boxes.filter(function (box) { return box.checked; }).length + (gender && !genderBoxes.length ? 1 : 0) + (fromLimit() ? 1 : 0) - (premiumOn ? 1 : 0);
      var badge = root.querySelector('[data-filter-badge]');
      badge.textContent = total ? (store ? String(total) : '(' + total + ')') : '';
      if (store) badge.setAttribute('aria-label', total + (total === 1 ? ' filter' : ' filters') + ' active');
      if (store && total) count.textContent += ' · refined by your choices';
      if (store) refreshOptions(st);
      countGroups();
      quickValues(selected, budgetValue);
      active.hidden = active.children.length === 0;
      if (!active.hidden) {
        var clear = document.createElement('button'); clear.type = 'button'; clear.className = 'linklike'; clear.textContent = 'Clear all'; clear.addEventListener('click', clearAll); active.appendChild(clear);
      }
      segments.forEach(function (button) { button.setAttribute('aria-pressed', button.dataset.gender === gender ? 'true' : 'false'); });
      if (plate) plate.dataset.pick = gender;
      syncSubs();
      if (store) sheetState(st, list, matched.length, premiumOn);
      else if (applyLabel) applyLabel.textContent = 'Show ' + matched.length + ' ' + noun;
    }
    // Live counts: each option shows how many watches it would give with the other choices kept, and an option that would give none is switched off.
    var NO_MATCH = 'No watch matches your other choices';
    function refreshOptions(st) {
      groups.forEach(function (group) {
        var g = group.dataset.fgroup, rows = pool(st, g), off = 0;
        Array.from(group.querySelectorAll('input')).forEach(function (box) {
          var n = rows.filter(function (card) { return has(card, g, box.value); }).length;
          var label = box.parentElement, small = label.querySelector('small');
          box._n = n;
          if (small) small.textContent = String(n);
          var dead = n === 0 && !box.checked;
          box.disabled = dead;
          label.classList.toggle('is-empty', dead);
          label.classList.toggle('is-on', box.checked);   // the chosen look does not rely on :has(), which older WebViews lack
          if (dead) { label.title = NO_MATCH; off++; } else label.removeAttribute('title');
        });
        var note = group.querySelector('.fopts-note');
        if (off && !note) {
          note = document.createElement('p'); note.className = 'fopts-note'; note.textContent = 'Dimmed options have no watch with your other choices.';
          group.appendChild(note);
        }
        if (note) note.hidden = !off;
      });
    }
    // The sheet's own summary: Active selections, Quick refine, the zero-result way back, the button labels.
    function sheetState(st, list, n, premiumOn) {
      var noun = n === 1 ? root.dataset.noun : plural;
      var anyChip = list.length > 0;
      if (cfReset) { cfReset.disabled = !anyChip; cfReset.classList.toggle('is-idle', !anyChip); }
      if (cfActive) {
        cfActive.replaceChildren();
        cfActive.hidden = !anyChip;
        if (anyChip) {
          var top = document.createElement('div'); top.className = 'cf-sum-t';
          var t = document.createElement('span'); t.textContent = 'Active selections';
          var all = document.createElement('button'); all.type = 'button'; all.className = 'linklike'; all.textContent = 'Clear all'; all.addEventListener('click', clearAll);
          top.appendChild(t); top.appendChild(all);
          var row = document.createElement('div'); row.className = 'cf-sum-c';
          list.forEach(function (item) { row.appendChild(chipButton(item)); });
          cfActive.appendChild(top); cfActive.appendChild(row);
        }
      }
      var zero = n === 0 && anyChip;
      undoPick = null;
      if (cfZero) {
        cfZero.replaceChildren();
        cfZero.hidden = !zero;
        if (zero) {
          var fixes = list.map(function (item) { var s = cloneState(st); item.drop(s); return { item: item, n: countFor(s) }; })
            .filter(function (f) { return f.n > 0; }).sort(function (a, b) { return b.n - a.n; });
          if (fixes.length) undoPick = fixes[0].item;
          var h = document.createElement('b'); h.textContent = 'No watch matches all your choices.';
          var p = document.createElement('p'); p.textContent = fixes.length ? 'Remove one to see watches:' : 'Reset the filters to see every watch.';
          cfZero.appendChild(h); cfZero.appendChild(p);
          if (fixes.length) {
            var fix = document.createElement('div'); fix.className = 'cf-fix';
            fixes.slice(0, 5).forEach(function (f) {
              var b = document.createElement('button'); b.type = 'button';
              var l = document.createElement('span'); l.textContent = 'Remove ' + f.item.label;
              var e = document.createElement('em'); e.textContent = f.n + (f.n === 1 ? ' watch' : ' watches');
              b.appendChild(l); b.appendChild(e);
              b.addEventListener('click', function () { f.item.remove(); update(); });
              fix.appendChild(b);
            });
            cfZero.appendChild(fix);
          }
        }
      }
      if (applyLabel) {
        applyLabel.textContent = n ? 'Show ' + n + ' ' + noun : 'No matches';
        applyLabel.disabled = n === 0;
      }
      if (cfFoot) cfFoot.classList.toggle('is-zero', zero);
      if (cfUndo) cfUndo.hidden = !zero;
      if (state.open && !state.closing) {
        quickRefine(st, n);   // Quick refine stays current while the sheet is open
        placeTips();
        var ae = document.activeElement;
        if (cfBody && (!ae || ae === document.body || !panel.contains(ae) || ae.disabled || ae.hidden || !ae.offsetParent && ae !== cfBody)) cfBody.focus({ preventScroll: true });   // a tapped chip was replaced: keep focus inside the sheet
      }
    }
    // Quick refine: the most useful options for the current selection, ranked by how many watches each keeps; never one already chosen, hidden when empty.
    function quickRefine(st, n) {
      if (!cfQuick) return;
      cfQuick.replaceChildren();
      var picks = [];
      var budget = bandsSlider();
      if (budget && !(st.selected.budget || []).length && !st.lo) {
        var bs = [];
        Array.from(budget.querySelectorAll('.sr-step')).forEach(function (step) {
          var i = Number(step.dataset.step);
          if (i >= 0 && step._n > 0 && step._n <= n * 0.6) bs.push({ label: budget._steps[i][1], n: step._n, run: function () { budget._setMax(i); } });
        });
        picks = picks.concat(bs.sort(function (a, b) { return b.n - a.n; }).slice(0, 2));
      }
      groups.forEach(function (group) {
        var g = group.dataset.fgroup;
        if (g === 'budget' && budget) return;
        if ((st.selected[g] || []).length) return;
        var own = Array.from(group.querySelectorAll('input')).filter(function (box) { return box._n > 0 && box._n < n && !box.checked; })
          .sort(function (a, b) { return b._n - a._n; }).slice(0, 2);
        own.forEach(function (box) { picks.push({ label: labelOf(box), group: group.querySelector('.fg-title').textContent, n: box._n, run: function () { box.checked = true; update(); } }); });
      });
      picks.sort(function (a, b) { return b.n - a.n; });
      picks = picks.slice(0, 6);
      var names = picks.map(function (pick) { return pick.label; });
      picks.forEach(function (pick) {   // two options with the same name (Analog as a style and as a display) say which group they belong to
        if (pick.group && names.indexOf(pick.label) !== names.lastIndexOf(pick.label)) pick.label = pick.group + ': ' + pick.label;
      });
      cfQuick.hidden = n < 2 || !picks.length;
      if (cfQuick.hidden) return;
      var t = document.createElement('div'); t.className = 'cf-qt'; t.textContent = 'Quick refine';
      var row = document.createElement('div'); row.className = 'cf-qrow';
      picks.forEach(function (pick) {
        var b = document.createElement('button'); b.type = 'button'; b.className = 'cf-q';
        var l = document.createElement('span'); l.textContent = pick.label;
        var e = document.createElement('em'); e.textContent = String(pick.n);
        b.appendChild(l); b.appendChild(e);
        b.setAttribute('aria-label', 'Add ' + pick.label + ', ' + pick.n + (pick.n === 1 ? ' watch' : ' watches'));
        b.addEventListener('click', pick.run);
        row.appendChild(b);
      });
      cfQuick.appendChild(t); cfQuick.appendChild(row);
    }
    function clearAll() {
      boxes.forEach(function (box) { box.checked = false; }); gender = ''; search.value = '';
      var ps = bandsSlider(); if (ps) ps._lo = 0;
      update();
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
      if (hasSub) button.setAttribute('aria-haspopup', 'dialog');
      button.addEventListener('click', function () {
        if (hasSub) { openSub(key, button); return; }
        var shut = group.classList.toggle('is-collapsed');
        button.setAttribute('aria-expanded', shut ? 'false' : 'true');
        if (store && !shut) {   // one row open at a time keeps the sheet short
          groups.forEach(function (other) {
            if (other === group || other.classList.contains('has-sub') || other.classList.contains('is-collapsed')) return;
            other.classList.add('is-collapsed'); var tg = other.querySelector('.fg-toggle'); if (tg) tg.setAttribute('aria-expanded', 'false');
          });
          scrollInto(group);
        }
      });
    });
    function countGroups() {
      groups.forEach(function (group) {
        var checked = Array.from(group.querySelectorAll('input:checked')), badge = group.querySelector('.fg-n'), sum = group.querySelector('.fg-sum');
        if (badge) badge.textContent = checked.length ? String(checked.length) : '';
        if (sum) sum.textContent = checked.length ? checked.map(labelOf).join(', ') : 'Any';
        group.classList.toggle('has-sel', checked.length > 0);
      });
      if (store) {   // a section with nothing to show is hidden, and a section with a choice says so
        Array.from(panel.querySelectorAll('.cf-sec')).forEach(function (sec) {
          var rows = Array.from(sec.querySelectorAll('.fgroup, .price-slider')).filter(function (el) { return !el.hidden; });
          sec.hidden = rows.length === 0;
        });
      }
    }
    // ---- visual sub-sheets (Case size, Strap): layers inside the one sheet, never a second dialog ----
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
      var layer = document.createElement('div');
      layer.className = 'cf-sub'; layer.hidden = true; layer.setAttribute('role', 'group'); layer.setAttribute('aria-label', title);
      layer.innerHTML = '<div class="sub-head"><button type="button" class="sub-back" data-layer-focus><i aria-hidden="true"></i>Back</button><div class="sub-ht"><strong></strong><span class="sub-count"></span></div></div>' +
        '<div class="sub-body"></div><div class="sub-foot"><button type="button" class="btn btn-primary sub-done">Show watches</button></div>';
      layer.querySelector('strong').textContent = title;
      var body = layer.querySelector('.sub-body'), cardsEl = document.createElement('div');
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
        b.innerHTML = '<span class="sub-art">' + d.art + '</span><strong></strong><small></small><em class="sub-n"></em>';
        b.querySelector('strong').textContent = d.name; b.querySelector('small').textContent = d.note;
        b.addEventListener('click', function () {
          var on = !d.boxes.every(function (box) { return box.checked; });
          d.boxes.forEach(function (box) { if (!box.disabled) box.checked = on; });
          update();
        });
        d._el = b; cardsEl.appendChild(b);
      });
      body.appendChild(cardsEl);
      var sizeButtons = [];
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
            b._box = groupBoxes.filter(function (box) { return box.value === s[1]; })[0];
            sizeButtons.push(b);
            q.querySelector('.sub-sizes').appendChild(b);
          });
          body.appendChild(q);
        }
      }
      layer.querySelector('.sub-back').addEventListener('click', function () { closeLayer(layer); });
      layer.querySelector('.sub-done').addEventListener('click', function () { closeLayer(layer); });
      panel.appendChild(layer);
      return { layer: layer, defs: defs, boxes: groupBoxes, sizes: sizeButtons };
    }
    function syncSubs() {
      Object.keys(subs).forEach(function (key) {
        var s = subs[key], n = s.defs.filter(function (d) { return d.boxes.every(function (box) { return box.checked; }); }).length;
        s.layer.querySelector('.sub-count').textContent = n ? n + ' selected' : 'None selected';
        s.layer.querySelector('.sub-done').textContent = lastCount ? 'Show ' + lastCount + ' ' + (lastCount === 1 ? root.dataset.noun : plural) : 'No matches';
        s.layer.querySelector('.sub-done').disabled = !lastCount;
        s.defs.forEach(function (d) {
          var on = d.boxes.every(function (box) { return box.checked; });
          d._el.setAttribute('aria-pressed', on ? 'true' : 'false');
          var dead = d.boxes.every(function (box) { return box.disabled; });
          d._el.disabled = dead;
          var total = d.boxes.reduce(function (sum, box) { return sum + (box._n || 0); }, 0);
          var tag = d._el.querySelector('.sub-n');
          if (tag) tag.textContent = String(total);
          if (dead) d._el.title = NO_MATCH; else d._el.removeAttribute('title');
        });
        s.sizes.forEach(function (b) {
          var box = b._box, dead = !box || (box.disabled && !box.checked);
          b.disabled = dead; b.setAttribute('aria-pressed', box && box.checked ? 'true' : 'false');
          if (dead) b.title = NO_MATCH; else b.removeAttribute('title');
        });
      });
    }
    // ---- layers inside the sheet: sub-sheets and the small explanation sheet ----
    var layers = [];
    function setInert(on) { [cfHead, cfBody, cfFoot].forEach(function (el) { if (!el) return; if (on) el.setAttribute('inert', ''); else el.removeAttribute('inert'); if (on) el.setAttribute('aria-hidden', 'true'); else el.removeAttribute('aria-hidden'); }); }
    function openLayer(layer, from) {
      if (!layer || layers.indexOf(layer) !== -1) return;
      layer._from = from || document.activeElement;
      layer.classList.remove('is-leaving'); layer.hidden = false;
      layers.push(layer); setInert(true);
      var first = layer.querySelector('[data-layer-focus]') || layer.querySelector('button');
      if (first) first.focus({ preventScroll: true });
    }
    function closeLayer(layer, instant) {
      var at = layers.indexOf(layer);
      if (at === -1) return;
      layers.splice(at, 1);
      function done() {
        layer.hidden = true; layer.classList.remove('is-leaving');
        if (!layers.length) setInert(false);
        var back = layer._from;
        if (!instant && back && back.focus && panel.contains(back)) back.focus({ preventScroll: true });
      }
      if (instant || reduce.matches) done();
      else { layer.classList.add('is-leaving'); window.setTimeout(done, 200); }
    }
    function openSub(key, from) {
      if (!subs[key]) subs[key] = buildSub(key);
      if (!subs[key]) return;
      syncSubs();
      openLayer(subs[key].layer, from);
    }
    panel.addEventListener('click', function (event) {
      var open = event.target.closest('[data-info-open]');
      if (open) { openLayer(panel.querySelector('[data-info="' + open.dataset.infoOpen + '"]'), open); return; }
      var shut = event.target.closest('[data-info-close]');
      if (shut) closeLayer(shut.closest('.cf-info'));
    });
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
      if (tile.target === '_blank') return;   // a tile that opens an outside link is never turned into an in-page filter
      tile.addEventListener('click', function (event) {
        event.preventDefault();
        var box = boxes.filter(function (b) { return b.dataset.group === 'brand' && b.value === tile.dataset.brandTile; })[0];
        if (!box) return;
        var was = box.checked;
        boxes.filter(function (b) { return b.dataset.group === 'brand'; }).forEach(function (b) { b.checked = false; });
        box.checked = !was; update(); toResults();
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
    if (cfUndo) cfUndo.addEventListener('click', function () {   // the way back from "No matches": drop the choice that brings back the most watches
      if (undoPick) { var label = undoPick.label; undoPick.remove(); update(); announce('Removed ' + label + '. ' + lastCount + (lastCount === 1 ? ' watch' : ' watches') + ' match.'); }
      else if (cfZero) { cfZero.scrollIntoView({ block: 'nearest' }); }
    });
    var live = null;
    function announce(text) {
      if (!live) { live = document.createElement('p'); live.className = 'visually-hidden'; live.setAttribute('role', 'status'); live.setAttribute('aria-live', 'polite'); panel.appendChild(live); }
      live.textContent = text;
    }
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
    // ---- the sheet itself: open, close, fallback, scroll lock, focus, swipe ----
    var state = { open: false, closing: false, openedAt: 0, opener: null, backdrop: null };
    var CLOSE_MS = 200;
    function lockPage() {
      var bar = window.innerWidth - docEl.clientWidth;   // desktop scrollbar width, so the page does not jump sideways when it disappears
      docEl.style.setProperty('--cf-sbw', (bar > 0 ? bar : 0) + 'px');
      docEl.classList.add('collection-modal-open');
    }
    function unlockPage() { docEl.classList.remove('collection-modal-open'); docEl.style.removeProperty('--cf-sbw'); }
    function addBackdrop() {   // used only when the browser has no working <dialog>.showModal()
      if (state.backdrop) return;
      var b = document.createElement('div'); b.className = 'cf-backdrop';
      b.addEventListener('click', function () { if (Date.now() - state.openedAt > 350) goBack(); });
      document.body.appendChild(b); state.backdrop = b;
      void b.offsetWidth; b.classList.add('is-on');
    }
    function removeBackdrop() { if (state.backdrop) { state.backdrop.remove(); state.backdrop = null; } }
    function placeTips() {   // keep the budget tooltip inside the sheet at both ends of the rail
      sliders.forEach(function (slider) {
        var tip = slider.querySelector('[data-price-tip]'), wrap = slider.querySelector('.sr-wrap');
        if (!tip || !wrap || !tip.textContent) return;
        var w = wrap.clientWidth, tw = tip.offsetWidth, n = Number(getComputedStyle(slider).getPropertyValue('--n')) || 1;
        var sel = Number(getComputedStyle(slider).getPropertyValue('--sel')) || 0;
        if (!w || !tw) return;
        var centre = (sel + .5) / n * w, left = Math.min(Math.max(centre, tw / 2), w - tw / 2);
        tip.style.left = left + 'px'; tip.style.setProperty('--arrow', (centre - left) + 'px');
      });
    }
    function scrollInto(el) {
      if (!cfBody || !el) return;
      window.requestAnimationFrame(function () {
        var top = el.getBoundingClientRect().top - cfBody.getBoundingClientRect().top + cfBody.scrollTop - 10;
        cfBody.scrollTo ? cfBody.scrollTo({ top: Math.max(0, top), behavior: reduce.matches ? 'auto' : 'smooth' }) : (cfBody.scrollTop = Math.max(0, top));
      });
    }
    function expandRow(group) {
      if (!group || !group.classList.contains('is-collapsed') || group.classList.contains('has-sub')) return;
      groups.forEach(function (other) { if (other !== group && !other.classList.contains('is-collapsed') && !other.classList.contains('has-sub')) { other.classList.add('is-collapsed'); other.querySelector('.fg-toggle').setAttribute('aria-expanded', 'false'); } });
      group.classList.remove('is-collapsed'); group.querySelector('.fg-toggle').setAttribute('aria-expanded', 'true');
    }
    var JUMPS = { more: 'dial' };
    function jumpTo(jump) {   // a quick filter opens the panel at that section
      var target = jump === 'budget' ? panel.querySelector('.price-slider') : jump ? panel.querySelector('[data-fgroup="' + jump + '"]') : null;
      if (!store) {
        if (target && target.classList.contains('fgroup') && target.classList.contains('is-collapsed') && !target.classList.contains('has-sub')) {
          target.classList.remove('is-collapsed'); target.querySelector('.fg-toggle').setAttribute('aria-expanded', 'true');
        }
        panel.scrollTop = target ? Math.max(0, target.offsetTop - 84) : 0;
        return;
      }
      if (cfBody) cfBody.scrollTop = 0;
      if (!target) return;
      expandRow(target);
      var anchor = target.classList.contains('price-slider') ? (target.closest('.cf-sec') || target) : target;
      var box = cfBody.getBoundingClientRect(), at = target.getBoundingClientRect();
      if (at.bottom > box.bottom - 24) cfBody.scrollTop = Math.max(0, anchor.getBoundingClientRect().top - box.top + cfBody.scrollTop - 10);   // only scroll when the section is not already on the first screen
    }
    function openSheet(opener) {
      if (state.open || inlinePanel()) return;
      state.open = true; state.closing = false; state.openedAt = Date.now(); state.opener = opener || null;
      panel.classList.remove('is-closing', 'is-dragged');
      var native = false;
      if (typeof panel.showModal === 'function') { try { panel.showModal(); native = true; } catch (e) { native = false; } }
      if (!native) {   // an older WebView or in-app browser: the same sheet, opened by attribute, with our own backdrop
        panel.classList.add('is-fallback'); panel.setAttribute('open', ''); panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true');
        if (store) addBackdrop();
      }
      lockPage();
      panel.tabIndex = -1; panel.focus({ preventScroll: true });
      if (store) { quickRefineNow(); placeTips(); }
      jumpTo(JUMPS[opener && opener.dataset.jump] || (opener && opener.dataset.jump) || '');
    }
    function quickRefineNow() { var st = readState(); quickRefine(st, lastCount); }
    function teardown() {   // everything that must be true once the sheet is gone (idempotent)
      if (!state.open) return;
      var wasFallback = panel.classList.contains('is-fallback');
      state.open = false; state.closing = false;
      panel.classList.remove('is-closing', 'is-dragged', 'is-fallback');
      panel.style.transform = ''; panel.style.transition = '';
      panel.removeAttribute('aria-modal');
      if (wasFallback) panel.removeAttribute('role');
      layers.slice().forEach(function (layer) { closeLayer(layer, true); });
      setInert(false);
      removeBackdrop(); unlockPage();
      var back = state.opener; state.opener = null;
      if (back && back.focus && document.contains(back)) back.focus({ preventScroll: true });
    }
    function hardClose() {
      if (!state.open) return;
      if (panel.classList.contains('is-fallback') || typeof panel.close !== 'function') panel.removeAttribute('open');
      else { try { panel.close(); } catch (e) { panel.removeAttribute('open'); } }
      teardown();
    }
    function closeSheet(fromDrag) {
      if (!state.open || state.closing) return;
      if (inlinePanel()) return;
      state.closing = true;
      layers.slice().forEach(function (layer) { closeLayer(layer, true); });
      if (state.backdrop) state.backdrop.classList.remove('is-on');
      if (store && !reduce.matches) {
        panel.classList.add(fromDrag ? 'is-dragged' : 'is-closing');
        if (fromDrag) { panel.style.transition = 'transform ' + CLOSE_MS + 'ms ease-in'; panel.style.transform = 'translate3d(0,100%,0)'; panel.classList.add('is-closing'); }
        window.setTimeout(hardClose, CLOSE_MS + 20);
      } else hardClose();
    }
    function goBack() {   // Escape, the Android back gesture and a backdrop tap: the top layer first, then the sheet
      if (layers.length) { closeLayer(layers[layers.length - 1]); return; }
      closeSheet(false);
    }
    openers.forEach(function (opener) {
      opener.addEventListener('click', function () { openSheet(opener); });
    });
    panel.querySelectorAll('[data-filter-close]').forEach(function (button) { button.addEventListener('click', function () { closeSheet(false); }); });
    panel.addEventListener('click', function (event) {   // a tap on the dimmed area (the native backdrop reports the dialog itself as the target)
      if (event.target !== panel || !state.open || Date.now() - state.openedAt < 350) return;
      var rect = panel.getBoundingClientRect();
      if (event.clientY < rect.top || event.clientX < rect.left || event.clientX > rect.right || event.clientY > rect.bottom) goBack();
    });
    panel.addEventListener('cancel', function (event) { event.preventDefault(); if (state.open) goBack(); });   // Escape and the Android back gesture
    document.addEventListener('keydown', function (event) {
      if (!state.open) return;
      if (event.key === 'Escape' || event.key === 'Esc') { event.preventDefault(); goBack(); return; }
      if (event.key === 'Tab' && panel.classList.contains('is-fallback')) {   // no native focus trap here, so keep Tab inside the sheet
        var focusable = Array.from(panel.querySelectorAll('button, input, select, a[href], [tabindex]:not([tabindex="-1"])')).filter(function (el) { return !el.disabled && el.offsetParent !== null && !el.closest('[inert]') && !el.closest('[hidden]'); });
        if (!focusable.length) return;
        var firstEl = focusable[0], lastEl = focusable[focusable.length - 1];
        if (event.shiftKey && (document.activeElement === firstEl || document.activeElement === panel)) { event.preventDefault(); lastEl.focus(); }
        else if (!event.shiftKey && document.activeElement === lastEl) { event.preventDefault(); firstEl.focus(); }
      }
    });
    panel.addEventListener('close', function () {
      if (state.open) teardown();
      if (inlinePanel()) panel.setAttribute('open', '');
    });
    window.addEventListener('pageshow', function (event) { if (event.persisted && state.open) hardClose(); });
    // swipe down on the header (the drag handle) to close; passive listeners, the header has touch-action: none
    if (store && cfHead) {
      var drag = null;
      cfHead.addEventListener('touchstart', function (event) {
        if (!state.open || state.closing || desktop.matches || layers.length || event.touches.length !== 1 || event.target.closest('button')) return;
        drag = { y: event.touches[0].clientY, t: Date.now(), dy: 0 };
      }, { passive: true });
      cfHead.addEventListener('touchmove', function (event) {
        if (!drag) return;
        drag.dy = Math.max(0, event.touches[0].clientY - drag.y);
        if (drag.dy > 4) { panel.classList.add('is-dragged'); panel.style.transition = 'none'; panel.style.transform = 'translate3d(0,' + drag.dy + 'px,0)'; }
      }, { passive: true });
      var endDrag = function () {
        if (!drag) return;
        var d = drag; drag = null;
        var speed = d.dy / Math.max(1, Date.now() - d.t);
        if (d.dy > 96 || (d.dy > 36 && speed > 0.5)) closeSheet(true);
        else if (d.dy > 0) {
          panel.style.transition = reduce.matches ? 'none' : 'transform 180ms ease-out'; panel.style.transform = '';
          window.setTimeout(function () { if (!state.closing) { panel.classList.remove('is-dragged'); panel.style.transition = ''; } }, 200);
        }
      };
      cfHead.addEventListener('touchend', endDrag, { passive: true });
      cfHead.addEventListener('touchcancel', endDrag, { passive: true });
    }
    function resize() {
      if (state.open) hardClose();
      docEl.classList.remove('collection-modal-open');
      if (inlinePanel()) panel.setAttribute('open', '');
      if (typeof update === 'function') update(false);
    }
    if (desktop.addEventListener) desktop.addEventListener('change', resize); else if (desktop.addListener) desktop.addListener(resize);
    // /watches/?price=under-3000 (the home page slider) opens the list with that price band chosen
    var query = new URLSearchParams(window.location.search);
    var from = query.get('from') || root.dataset.presetFrom;   // /watches/?price=under-3000&from=under-2000 opens the 2,000 to 3,000 range
    if (from) sliders.forEach(function (slider) {
      var at = JSON.parse(slider.dataset.steps).map(function (step) { return step[0]; }).indexOf(from);
      if (at >= 0 && slider.classList.contains('price-bands')) slider._lo = at + 1;
    });
    var wanted = query.get('price');
    if (wanted) boxes.forEach(function (box) { if (box.dataset.group === 'budget' && box.value === wanted) box.checked = true; });
    resize(); update();
  });
})();
