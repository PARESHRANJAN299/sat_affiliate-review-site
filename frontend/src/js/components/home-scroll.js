(function () {
  'use strict';
  // Scroll effects for the home page. Nothing is hidden unless this script runs, and nothing moves for visitors who ask for less motion.
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  // the drifting rows stop while the hero is scrolled out of view, so they do not use the GPU for nothing
  var heroBox = document.querySelector('.home-hero');
  if (heroBox && 'IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) { heroBox.classList.toggle('is-offscreen', !entries[0].isIntersecting); }).observe(heroBox);
  }
  if (reduce) return;

  // 1) the picture wall drifts a little slower than the page
  var media = document.querySelector('.home-hero-media');
  var hero = document.querySelector('.home-hero');
  if (media && hero) {
    var ticking = false;
    var update = function () {
      ticking = false;
      var top = hero.getBoundingClientRect().top;
      var shift = Math.max(-80, Math.min(80, -top * 0.28));
      media.style.transform = 'translate3d(0,' + shift.toFixed(1) + 'px,0)';
    };
    window.addEventListener('scroll', function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(update); }
    }, { passive: true });
    update();
  }

  // 2) cards and sections fade up as they come into view
  if (!('IntersectionObserver' in window)) return;
  var items = document.querySelectorAll('.home-section-head, .home-cat-strip > li, .home-approach');
  var seen = 0;
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-in');
        io.unobserve(entry.target);
      }
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
  Array.prototype.forEach.call(items, function (el, i) {
    el.classList.add('reveal');
    el.style.transitionDelay = (el.parentNode && el.parentNode.classList.contains('home-cat-strip') ? (i % 6) * 60 : 0) + 'ms';
    io.observe(el);
    seen += 1;
  });
  // safety net: never leave anything hidden
  window.setTimeout(function () {
    Array.prototype.forEach.call(document.querySelectorAll('.reveal:not(.is-in)'), function (el) {
      var r = el.getBoundingClientRect();
      if (r.top < window.innerHeight) el.classList.add('is-in');
    });
  }, 1500);
})();
