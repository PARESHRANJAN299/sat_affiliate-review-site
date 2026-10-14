(function () {
  'use strict';
  // Phone jump bar: appears after you scroll past the intro, hides near the footer.
  var bar = document.querySelector('.pick-bar');
  var sentinel = document.getElementById('picks-start');
  if (!bar || !sentinel || !('IntersectionObserver' in window)) return;
  bar.hidden = false;
  var pastIntro = false;
  var atFooter = false;
  function update() { bar.classList.toggle('is-visible', pastIntro && !atFooter); }
  new IntersectionObserver(function (entries) {
    pastIntro = !entries[0].isIntersecting && entries[0].boundingClientRect.top < 0;
    update();
  }).observe(sentinel);
  var footer = document.querySelector('.site-footer');
  if (footer) {
    new IntersectionObserver(function (entries) {
      atFooter = entries[0].isIntersecting;
      update();
    }).observe(footer);
  }
})();
