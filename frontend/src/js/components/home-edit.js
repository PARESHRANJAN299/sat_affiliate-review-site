(function () {
  'use strict';
  /* The SAT Edit carousel on the home page, built with React (self-hosted in /vendor/). The first slide is plain HTML in the page, so nothing waits for React;
     React (about 45 KB compressed) is fetched only when the carousel is about to scroll into view. If it cannot load, the first slide simply stays. */
  var root = document.querySelector('[data-he]');
  var dataEl = document.getElementById('he-data');
  if (!root || !dataEl) return;
  var slides;
  try { slides = JSON.parse(dataEl.textContent); } catch (error) { return; }
  if (!slides || slides.length < 2) return;

  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var tag = document.createElement('script');
      tag.src = src;
      tag.onload = resolve;
      tag.onerror = reject;
      document.head.appendChild(tag);
    });
  }
  function start() {
    var ready = window.React && window.ReactDOM ? Promise.resolve() : loadScript('/vendor/react-18.3.1.production.min.js').then(function () { return loadScript('/vendor/react-dom-18.3.1.production.min.js'); });
    ready.then(mount).catch(function () { /* the first slide stays as it is */ });
  }

  function mount() {
    var React = window.React, ReactDOM = window.ReactDOM;
    if (!React || !ReactDOM || !ReactDOM.createRoot) return;
    var h = React.createElement;
    var reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    var total = slides.length;

    function pad(n) { return n < 10 ? '0' + n : '' + n; }

    function Slide(props) {
      var slide = props.slide, image = slide.image;
      var title = [];
      slide.title.forEach(function (line, i) { if (i) title.push(h('br', { key: 'b' + i })); title.push(line); });
      return h('article', { className: 'he-slide he-' + slide.style + (props.active ? ' is-active' : ''), role: 'group', 'aria-roledescription': 'slide', 'aria-label': (props.index + 1) + ' of ' + total, 'data-slide': slide.id },
        h('img', { className: 'he-photo' + (slide.cutout ? ' he-cutout' : ''), src: image.src, srcSet: image.srcset, sizes: '(min-width: 900px) 60vw, 100vw', alt: image.alt, width: image.width, height: image.height, loading: props.index ? 'lazy' : 'eager', decoding: 'async' }),
        h('span', { className: 'he-shade', 'aria-hidden': 'true' }),
        h('div', { className: 'he-copy' },
          h('p', { className: 'he-kicker' }, h('span', { 'aria-hidden': 'true' }), slide.kicker),
          h('h2', null, title),
          h('p', { className: 'he-sub' }, slide.sub),
          slide.tags && slide.tags.length ? h('ul', { className: 'he-tags' }, slide.tags.map(function (tag) { return h('li', { key: tag }, tag); })) : null,
          h('a', { className: 'he-btn', href: slide.href, tabIndex: props.active ? 0 : -1 }, slide.cta + ' ', h('span', { 'aria-hidden': 'true' }, '→'))));
    }

    function App() {
      var state = React.useState(0), index = state[0], setIndex = state[1];
      var hold = React.useRef(false), startX = React.useRef(null);
      React.useEffect(function () {
        if (reduce) return undefined;
        var timer = window.setInterval(function () {
          if (!hold.current && !document.hidden) setIndex(function (i) { return (i + 1) % total; });
        }, 7500);
        return function () { window.clearInterval(timer); };
      }, []);
      function go(to) { setIndex((to + total) % total); }
      function onKey(event) {
        if (event.key === 'ArrowRight') { go(index + 1); } else if (event.key === 'ArrowLeft') { go(index - 1); }
      }
      return h('div', {
        className: 'he-stage' + (slides[index].style === 'dark' ? ' he-on-dark' : ''),
        onMouseEnter: function () { hold.current = true; }, onMouseLeave: function () { hold.current = false; },
        onFocus: function () { hold.current = true; }, onBlur: function () { hold.current = false; },
        onKeyDown: onKey,
        onPointerDown: function (event) { startX.current = event.clientX; },
        onPointerUp: function (event) {
          if (startX.current === null) return;
          var dx = event.clientX - startX.current;
          startX.current = null;
          if (Math.abs(dx) > 50) go(index + (dx < 0 ? 1 : -1));
        }
      },
        slides.map(function (slide, i) { return h(Slide, { key: slide.id, slide: slide, index: i, active: i === index }); }),
        h('div', { className: 'he-ui' },
          h('div', { className: 'he-dots', role: 'group', 'aria-label': 'Choose a slide' }, slides.map(function (slide, i) {
            return h('button', { key: slide.id, type: 'button', className: 'he-dot', 'aria-label': 'Slide ' + (i + 1) + ' of ' + total, 'aria-current': i === index ? 'true' : 'false', onClick: function () { go(i); } }, pad(i + 1));
          })),
          h('div', { className: 'he-arrows' },
            h('button', { type: 'button', className: 'he-arrow', 'aria-label': 'Previous slide', onClick: function () { go(index - 1); } }, '←'),
            h('button', { type: 'button', className: 'he-arrow', 'aria-label': 'Next slide', onClick: function () { go(index + 1); } }, '→'))));
    }

    ReactDOM.createRoot(root).render(h(App));
  }

  // Load React when the carousel is about to be seen. Three triggers share one guard: the carousel nearing the viewport, the first scroll, and a quiet moment after the page has loaded.
  var started = false;
  function begin() { if (started) return; started = true; start(); }
  if ('IntersectionObserver' in window) {
    var watcher = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) { watcher.disconnect(); begin(); }
    }, { rootMargin: '700px 0px' });
    watcher.observe(root);
  }
  window.addEventListener('scroll', begin, { once: true, passive: true });
  window.addEventListener('load', function () { window.setTimeout(begin, 5000); });
})();
