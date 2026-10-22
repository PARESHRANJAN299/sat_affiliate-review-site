(function () {
  'use strict';
  /* Category tabs on /fashion/, built with React (self-hosted, see /vendor/). The server still prints plain links and every category panel;
     this component only takes over the tab bar and shows one panel at a time. If React is missing, fashion-widgets.js keeps the old switcher. */
  var React = window.React, ReactDOM = window.ReactDOM;
  var nav = document.getElementById('fashion-categories');
  if (!React || !ReactDOM || !ReactDOM.createRoot || !nav) return;

  var panels = {};
  [].forEach.call(document.querySelectorAll('[data-category-panel]'), function (panel) { panels[panel.dataset.categoryPanel] = panel; });
  var serverCurrent = nav.querySelector('[data-category-tab][aria-current]');
  var tabs = [].map.call(nav.querySelectorAll('[data-category-tab]'), function (link) {
    var id = link.dataset.categoryTab, panel = panels[id];
    return { id: id, label: link.textContent, count: panel ? panel.querySelectorAll('.nykaa-product-shell').length : 0 };
  });
  if (!tabs.length) return;
  window.__fashionTabsReact = true;
  // A second switch at the bottom of the lists: after a long scroll, other categories are one tap away (no need to go back up).
  var lastPanel = panels[tabs[tabs.length - 1].id] || panels[Object.keys(panels).pop()];
  var moreHost = document.createElement('div');
  moreHost.className = 'ft-more';
  if (lastPanel && lastPanel.parentNode) lastPanel.parentNode.insertBefore(moreHost, lastPanel.nextSibling);

  var h = React.createElement, useState = React.useState, useEffect = React.useEffect, useLayoutEffect = React.useLayoutEffect, useRef = React.useRef;
  var reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);

  function idFromHash() {
    var id = decodeURIComponent(location.hash.slice(1));
    if (!id) return null;
    if (panels[id]) return id;
    var target = document.getElementById(id);
    var panel = target && target.closest ? target.closest('[data-category-panel]') : null;
    return panel ? panel.dataset.categoryPanel : null;
  }
  var startHash = idFromHash();
  var initial = startHash || (serverCurrent ? serverCurrent.dataset.categoryTab : tabs[0].id);

  function App() {
    var activeState = useState(initial), active = activeState[0], setActive = activeState[1];
    var indicatorState = useState({ x: 0, w: 0 }), indicator = indicatorState[0], setIndicator = indicatorState[1];
    var edgeState = useState({ start: false, end: false }), edges = edgeState[0], setEdges = edgeState[1];
    var scroller = useRef(null), tabRefs = useRef({}), byUser = useRef(false), firstPaint = useRef(true);

    function measure() {
      var el = tabRefs.current[active], box = scroller.current;
      if (!el || !box) return;
      setIndicator({ x: el.offsetLeft, w: el.offsetWidth });
      setEdges({ start: box.scrollLeft > 4, end: box.scrollLeft + box.clientWidth < box.scrollWidth - 4 });
    }
    useLayoutEffect(measure, [active]);
    useEffect(function () {
      window.addEventListener('resize', measure);
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
      return function () { window.removeEventListener('resize', measure); };
    }, [active]);

    // Show only the chosen panel; the others stay in the page (their Nykaa cards are lazy-loaded and load only once shown).
    useEffect(function () {
      Object.keys(panels).forEach(function (id) {
        var panel = panels[id], on = id === active;
        panel.hidden = !on;
        panel.setAttribute('role', 'tabpanel');
        panel.classList.remove('is-entering');
        if (on && !firstPaint.current && !reduce) { void panel.offsetWidth; panel.classList.add('is-entering'); }
      });
      window.dispatchEvent(new Event('resize'));  // card rows measure themselves again once visible
      var el = tabRefs.current[active], box = scroller.current;
      if (el && box) box.scrollTo({ left: Math.max(0, el.offsetLeft - (box.clientWidth - el.offsetWidth) / 2), behavior: reduce || firstPaint.current ? 'auto' : 'smooth' });
      if (byUser.current) {  // a visitor deep in a long list lands at the top of the new one
        byUser.current = false;
        var top = panels[active].getBoundingClientRect().top + window.pageYOffset - nav.offsetHeight - (parseInt(nav.style.getPropertyValue('--ft-top'), 10) || 0) - 8;
        if (window.pageYOffset > top + 4) window.scrollTo({ top: Math.max(0, top), behavior: reduce ? 'auto' : 'smooth' });
      }
      firstPaint.current = false;
    }, [active]);

    // The bar sticks just under the SAT menu bar, whatever its height is on this screen.
    useEffect(function () {
      function place() {
        var bar = document.querySelector('header.site-header');
        nav.style.setProperty('--ft-top', (bar ? Math.round(bar.getBoundingClientRect().height) : 0) + 'px');
      }
      place();
      window.addEventListener('resize', place);
      return function () { window.removeEventListener('resize', place); };
    }, []);

    useEffect(function () {
      function onHash() {
        var id = idFromHash();
        if (id) { byUser.current = true; setActive(id); }  // a link such as #footwear elsewhere on the page opens that list from its top
      }
      window.addEventListener('hashchange', onHash);
      return function () { window.removeEventListener('hashchange', onHash); };
    }, []);

    function choose(id) {
      byUser.current = true;
      setActive(id);
      try { history.replaceState(null, '', '#' + id); } catch (error) { /* the tabs still work without a hash */ }
    }
    function onKey(event) {
      var at = 0, i, to = null;
      for (i = 0; i < tabs.length; i++) if (tabs[i].id === active) at = i;
      if (event.key === 'ArrowRight') to = (at + 1) % tabs.length;
      else if (event.key === 'ArrowLeft') to = (at + tabs.length - 1) % tabs.length;
      else if (event.key === 'Home') to = 0;
      else if (event.key === 'End') to = tabs.length - 1;
      if (to === null) return;
      event.preventDefault();
      choose(tabs[to].id);
      var next = tabRefs.current[tabs[to].id];
      if (next) next.focus();
    }
    function onScroll() {
      var box = scroller.current;
      if (box) setEdges({ start: box.scrollLeft > 4, end: box.scrollLeft + box.clientWidth < box.scrollWidth - 4 });
    }

    var more = h('nav', { 'aria-label': 'More fashion categories' },
      h('p', { className: 'ft-more-title' }, 'More styles'),
      h('ul', { className: 'ft-more-list' }, tabs.filter(function (tab) { return tab.id !== active; }).map(function (tab) {
        return h('li', { key: tab.id }, h('a', { className: 'ft-more-btn', href: '#' + tab.id, onClick: function (event) { event.preventDefault(); choose(tab.id); } },
          h('span', { className: 'ft-more-label' }, tab.label), tab.count ? h('span', { className: 'ft-count' }, tab.count) : null, h('span', { 'aria-hidden': 'true' }, '\u2192')));
      })));
    return h(React.Fragment, null, ReactDOM.createPortal(more, moreHost), h('div', { className: 'ft-bar' },
      h('div', { className: 'ft-scroller' + (edges.start ? ' has-start' : '') + (edges.end ? ' has-end' : ''), ref: scroller, onScroll: onScroll },
        h('div', { className: 'ft-list', role: 'tablist', 'aria-label': 'Fashion categories', onKeyDown: onKey },
          tabs.map(function (tab) {
            var on = tab.id === active;
            return h('a', {
              key: tab.id, id: 'ft-tab-' + tab.id, className: 'ft-tab', href: '#' + tab.id, role: 'tab', 'aria-selected': on ? 'true' : 'false', 'aria-controls': tab.id,
              tabIndex: on ? 0 : -1, ref: function (el) { tabRefs.current[tab.id] = el; },
              onClick: function (event) { event.preventDefault(); choose(tab.id); }
            }, tab.label, tab.count ? h('span', { className: 'ft-count' }, tab.count) : null);
          }),
          h('i', { className: 'ft-ind', 'aria-hidden': 'true', style: { '--x': indicator.x + 'px', '--w': indicator.w + 'px' } })))));
  }

  nav.classList.add('is-react');
  ReactDOM.createRoot(nav).render(h(App));

  // A link from the home page opens the collection with the tabs in view; a card link (#pick-...) scrolls to that card.
  function landing() {
    var id = decodeURIComponent(location.hash.slice(1));
    var target = id && document.getElementById(id);
    if (/^pick-/.test(id) && target) { window.setTimeout(function () { target.scrollIntoView({ block: 'center' }); }, 80); return; }
    if (startHash) {
      var toTop = function () { window.scrollTo({ top: 0, left: 0, behavior: 'instant' }); };
      toTop();
      window.addEventListener('load', function () { toTop(); window.setTimeout(toTop, 60); });
    }
  }
  landing();
})();
