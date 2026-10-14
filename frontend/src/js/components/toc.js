(function () {
  'use strict';
  // The contents list starts open; fold it on small screens so it does not push the article down.
  var toc = document.querySelector('details.toc');
  if (!toc || !window.matchMedia) return;
  if (window.matchMedia('(max-width: 1099px)').matches) toc.open = false;
})();
