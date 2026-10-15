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

  // 2b) FAQ: one answer open at a time, smooth open and close, and links such as /about/#faq-prices open that answer
  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var faqs = Array.prototype.slice.call(document.querySelectorAll('.faq-item'));
  var animate = !reduceMotion && faqs.length && faqs[0].querySelector('.faq-a').animate;
  function bodyOf(d) { return d.querySelector('.faq-a'); }
  function stop(d) {
    if (d._anim) { d._anim.onfinish = null; d._anim.cancel(); d._anim = null; }
    if (d._timer) { clearTimeout(d._timer); d._timer = null; }
  }
  function openItem(d) {
    stop(d);
    d.open = true;
    if (!animate) return;
    var b = bodyOf(d);
    d._anim = b.animate([{ height: '0px', opacity: 0 }, { height: b.scrollHeight + 'px', opacity: 1 }], { duration: 280, easing: 'cubic-bezier(.2,.8,.2,1)' });
    // the timer guarantees the final state even if the browser pauses animations
    d._timer = setTimeout(function () { stop(d); }, 380);
  }
  function closeItem(d) {
    if (!d.open) return;
    stop(d);
    if (!animate) { d.open = false; return; }
    var b = bodyOf(d);
    d._anim = b.animate([{ height: b.offsetHeight + 'px', opacity: 1 }, { height: '0px', opacity: 0 }], { duration: 200, easing: 'ease-out' });
    d._timer = setTimeout(function () { stop(d); d.open = false; }, 300);
  }
  function closeOthers(d) { faqs.forEach(function (o) { if (o !== d) closeItem(o); }); }
  faqs.forEach(function (d) {
    d.querySelector('summary').addEventListener('click', function (e) {
      e.preventDefault();
      if (d.open) { closeItem(d); } else { closeOthers(d); openItem(d); }
    });
  });
  function openFromHash() {
    var id = decodeURIComponent((location.hash || '').slice(1));
    var el = id ? document.getElementById(id) : null;
    if (!el || !el.classList.contains('faq-item')) return;
    faqs.forEach(function (o) { if (o !== el) o.open = false; });
    el.open = true;
    if (el.scrollIntoView) el.scrollIntoView({ block: 'center', behavior: reduceMotion ? 'auto' : 'smooth' });
  }
  if (faqs.length) {
    openFromHash();
    window.addEventListener('hashchange', openFromHash);
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
