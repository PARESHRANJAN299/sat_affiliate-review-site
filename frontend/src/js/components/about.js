(function () {
  'use strict';
  // 1) On phones the intro starts short: the first line shows, the rest opens with "More about me".
  var more = document.querySelector('.about-more');
  if (more && window.matchMedia && window.matchMedia('(max-width: 819px)').matches) more.open = false;

  // 2) "Copy email" button (only shown when copying is possible)
  var copy = document.querySelector('[data-copy-email]');
  var status = document.querySelector('[data-copy-status]');
  var email = document.querySelector('.about-email');
  if (copy && email && navigator.clipboard && navigator.clipboard.writeText) {
    copy.hidden = false;
    copy.addEventListener('click', function () {
      navigator.clipboard.writeText(email.textContent.trim()).then(function () {
        copy.textContent = 'Copied \u2713';
        if (status) status.textContent = 'Email address copied';
        window.setTimeout(function () { copy.textContent = 'Copy email'; if (status) status.textContent = ''; }, 2200);
      });
    });
  }

  // 3) Sections and cards fade up as they scroll into view (added by script, so nothing is hidden without JavaScript)
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !('IntersectionObserver' in window)) return;
  var items = document.querySelectorAll('.about-block > h2, .about-statement, .about-points > li, .cover-grid > li, .about-contact');
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) { entry.target.classList.add('is-in'); io.unobserve(entry.target); }
    });
  }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });
  Array.prototype.forEach.call(items, function (el) {
    var siblings = el.parentNode ? Array.prototype.indexOf.call(el.parentNode.children, el) : 0;
    el.classList.add('reveal-up');
    el.style.transitionDelay = Math.min(siblings, 5) * 70 + 'ms';
    io.observe(el);
  });
  window.setTimeout(function () {
    Array.prototype.forEach.call(document.querySelectorAll('.reveal-up:not(.is-in)'), function (el) {
      if (el.getBoundingClientRect().top < window.innerHeight) el.classList.add('is-in');
    });
  }, 1500);
})();
