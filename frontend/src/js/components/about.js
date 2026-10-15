(function () {
  'use strict';
  // On phones the About intro starts short: the first line shows, the rest opens with "More about me".
  var more = document.querySelector('.about-more');
  if (!more || !window.matchMedia) return;
  if (window.matchMedia('(max-width: 819px)').matches) more.open = false;
})();
