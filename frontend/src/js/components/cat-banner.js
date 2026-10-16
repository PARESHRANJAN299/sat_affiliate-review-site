(function () {
  'use strict';
  // Category page banner: the first picture is already in the page; the rest are added after load and fade into each other.
  var box = document.querySelector('[data-cat-banner]');
  if (!box) return;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var slides = [];
  try { slides = JSON.parse(box.getAttribute('data-slides') || '[]'); } catch (e) { slides = []; }
  if (reduce || !slides.length) return;

  var imgs = [box.querySelector('img')];
  var current = 0;
  var timer = null;
  var visible = true;

  function show(n) {
    imgs[current].classList.remove('is-on');
    current = n;
    imgs[current].classList.add('is-on');
  }
  function next() {
    if (document.hidden || !visible || imgs.length < 2) return;
    show((current + 1) % imgs.length);
  }
  function start() {
    if (!timer) timer = window.setInterval(next, 7000);
  }
  function load() {
    slides.forEach(function (src) {
      var img = new Image();
      img.alt = '';
      img.width = 900;
      img.height = 405;
      img.decoding = 'async';
      img.onload = function () {
        box.appendChild(img);
        imgs.push(img);
        start();
      };
      img.src = src;
    });
  }
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) { visible = entries[0].isIntersecting; }).observe(box);
  }
  var begin = function () { window.setTimeout(load, 1200); };
  if (document.readyState === 'complete') begin(); else window.addEventListener('load', begin);
})();
