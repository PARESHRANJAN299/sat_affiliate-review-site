(function () {
  'use strict';
  // Category page picture showcase: the first picture is already in the page; the others are added after load, fade into each other
  // (the progress bar on the current dot is the timer), and can be changed with the dots. Nothing runs for visitors who ask
  // for less motion except the dots, and nothing extra loads when Data Saver is on.
  var box = document.querySelector('[data-cat-showcase]');
  if (!box) return;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var conn = navigator.connection || {};
  var saveData = conn.saveData || /^(slow-2g|2g|3g)$/.test(conn.effectiveType || '');
  var slides = [];
  try { slides = JSON.parse(box.getAttribute('data-slides') || '[]'); } catch (e) { slides = []; }
  if (!slides.length || saveData) return;
  // on phones the picture stays still: no extra downloads and no controls over the title
  if (window.matchMedia && window.matchMedia('(max-width: 719px)').matches) return;

  var label = box.getAttribute('data-label') || 'Category';
  box.setAttribute('role', 'group');
  box.setAttribute('aria-roledescription', 'carousel');
  box.setAttribute('aria-label', label + ' pictures');

  var imgs = [box.querySelector('img')];
  var current = 0;
  var userPaused = false, hover = false, focus = false, visible = true;
  var dots = null, count = null, pp = null, controls = null;

  function sync() {
    var paused = userPaused || hover || focus || !visible || document.hidden;
    box.classList.toggle('is-paused', paused);
  }
  function show(n) {
    imgs[current].classList.remove('is-on');
    if (dots) dots.children[current].removeAttribute('aria-current');
    current = (n + imgs.length) % imgs.length;
    imgs[current].classList.add('is-on');
    if (dots) {
      // removing and re-adding the attribute restarts the progress animation
      var d = dots.children[current];
      d.setAttribute('aria-current', 'true');
    }
    if (count) count.textContent = (current + 1) + ' / ' + imgs.length;
  }

  function buildControls() {
    controls = document.createElement('div');
    controls.className = 'cat-controls';
    dots = document.createElement('div');
    dots.className = 'cat-dots';
    imgs.forEach(function (img, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('aria-label', 'Show picture ' + (i + 1) + ' of ' + imgs.length);
      b.addEventListener('click', function () { show(i); });
      dots.appendChild(b);
    });
    dots.children[0].setAttribute('aria-current', 'true');
    controls.appendChild(dots);
    count = document.createElement('span');
    count.className = 'cat-count';
    count.setAttribute('aria-hidden', 'true');
    count.textContent = '1 / ' + imgs.length;
    controls.appendChild(count);
    if (!reduce) {
      pp = document.createElement('button');
      pp.type = 'button';
      pp.className = 'cat-pp';
      pp.setAttribute('aria-label', 'Pause pictures');
      pp.innerHTML = '<span aria-hidden="true">❚❚</span>';
      pp.addEventListener('click', function () {
        userPaused = !userPaused;
        pp.setAttribute('aria-label', userPaused ? 'Play pictures' : 'Pause pictures');
        pp.firstChild.textContent = userPaused ? '▶' : '❚❚';
        sync();
      });
      controls.appendChild(pp);
    }
    box.appendChild(controls);
    if (!reduce) {
      box.classList.add('is-playing');
      // the progress bar on the current dot ends -> the next picture
      dots.addEventListener('animationend', function (e) {
        if (e.animationName === 'cat-progress') show(current + 1);
      });
    }
  }

  function load() {
    var pending = slides.length;
    var made = [];
    slides.forEach(function (src, i) {
      var img = new Image();
      img.alt = '';
      img.width = 800;
      img.height = 480;
      img.decoding = 'async';
      var done = function (ok) {
        if (ok) made[i] = img;
        pending -= 1;
        if (pending === 0) {
          made.forEach(function (m) { if (m) { box.insertBefore(m, box.querySelector('.cat-controls')); imgs.push(m); } });
          if (imgs.length > 1) { buildControls(); sync(); }
        }
      };
      img.onload = function () { done(true); };
      img.onerror = function () { done(false); };
      img.src = src;
    });
  }

  box.addEventListener('pointerover', function (e) { if (e.target.closest && e.target.closest('.cat-controls')) { hover = true; sync(); } });
  box.addEventListener('pointerout', function (e) { if (e.target.closest && e.target.closest('.cat-controls')) { hover = false; sync(); } });
  box.addEventListener('focusin', function () { focus = true; sync(); });
  box.addEventListener('focusout', function () { focus = false; sync(); });
  document.addEventListener('visibilitychange', sync);
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) { visible = entries[0].isIntersecting; sync(); }).observe(box);
  }

  var begin = function () { if (window.requestIdleCallback) window.requestIdleCallback(load, { timeout: 4000 }); else window.setTimeout(load, 1500); };
  if (document.readyState === 'complete') begin(); else window.addEventListener('load', begin);
})();
