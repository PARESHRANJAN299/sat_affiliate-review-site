(function () {
  'use strict';
  // Folds the contents list on small screens and marks the section you are reading.
  var toc = document.querySelector('details.toc');
  if (toc && window.matchMedia && window.matchMedia('(max-width: 899px)').matches) toc.open = false;
  if (!('IntersectionObserver' in window)) return;

  var links = document.querySelectorAll('.toc a[href^="#"], .pick-bar a[href^="#"]');
  var byId = {};
  Array.prototype.forEach.call(links, function (a) {
    var id = a.getAttribute('href').slice(1);
    (byId[id] = byId[id] || []).push(a);
  });
  var visible = {};
  function mark() {
    var ids = Object.keys(byId);
    var current = null;
    for (var i = 0; i < ids.length; i++) {
      if (visible[ids[i]]) { current = ids[i]; break; }
    }
    Array.prototype.forEach.call(links, function (a) {
      var on = current && a.getAttribute('href') === '#' + current;
      if (a.closest('.pick-bar')) {
        if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
      } else if (on) {
        a.setAttribute('aria-current', 'location');
      } else {
        a.removeAttribute('aria-current');
      }
    });
  }
  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting; });
    mark();
  }, { rootMargin: '-80px 0px -55% 0px' });
  Object.keys(byId).forEach(function (id) {
    var el = document.getElementById(id);
    if (el) observer.observe(el);
  });
})();
