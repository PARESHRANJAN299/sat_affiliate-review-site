(function () {
  'use strict';
  // Contact page. The site has no server, so the form builds an email in the visitor's own email app.
  var form = document.getElementById('contact-form');
  if (!form) return;
  form.hidden = false;
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var f = form.elements;
  var to = (document.querySelector('.contact-email-text') || {}).textContent;
  to = to ? to.trim() : '';
  var MAX = 1500;

  // ---------- copy buttons ----------
  var copyMail = document.querySelector('[data-copy-mail]');
  var note = document.querySelector('[data-copy-note]');
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text);
    return Promise.reject(new Error('no clipboard'));
  }
  function flash(btn, done, label) {
    var old = label;
    btn.textContent = done;
    window.setTimeout(function () { btn.textContent = old; }, 2000);
  }
  if (copyMail && navigator.clipboard && navigator.clipboard.writeText) {
    copyMail.hidden = false;
    copyMail.addEventListener('click', function () {
      copyText(to).then(function () {
        flash(copyMail, 'Copied ✓', 'Copy email');
        if (note) note.textContent = 'Email address copied';
      });
    });
  }

  // ---------- topic chips ----------
  var topics = Array.prototype.slice.call(form.querySelectorAll('.cf-topic'));
  topics.forEach(function (chip) {
    chip.setAttribute('aria-pressed', 'false');
    chip.addEventListener('click', function () {
      var on = chip.classList.contains('is-on');
      topics.forEach(function (c) { c.classList.remove('is-on'); c.setAttribute('aria-pressed', 'false'); });
      if (on) { f.subject.value = ''; check(f.subject, true); return; }
      chip.classList.add('is-on');
      chip.setAttribute('aria-pressed', 'true');
      f.subject.value = chip.getAttribute('data-topic');
      check(f.subject, true);
      (f.message.value ? f.message : (f.name.value ? f.email.value ? f.message : f.email : f.name)).focus();
    });
  });
  f.subject.addEventListener('input', function () {
    topics.forEach(function (c) {
      var same = c.getAttribute('data-topic') === f.subject.value;
      c.classList.toggle('is-on', same);
      c.setAttribute('aria-pressed', same ? 'true' : 'false');
    });
  });

  // ---------- live checks ----------
  var MESSAGES = {
    name: 'Please enter your name.',
    email: 'Please enter a valid email address.',
    subject: 'Please add a subject.',
    message: 'Please write your message.'
  };
  function valid(el) {
    var v = el.value.trim();
    if (!v) return false;
    if (el.name === 'email') return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v);
    return true;
  }
  function check(el, quiet) {
    var field = el.closest('.cf-field');
    var err = document.getElementById('cf-' + el.name + '-err');
    var ok = valid(el);
    var touched = el.value.length > 0 || !quiet;
    field.classList.toggle('is-valid', ok);
    field.classList.toggle('is-bad', !ok && !quiet);
    if (err) { err.hidden = ok || quiet; err.textContent = ok || quiet ? '' : MESSAGES[el.name]; }
    el.setAttribute('aria-invalid', !ok && !quiet ? 'true' : 'false');
    return ok && touched;
  }
  ['name', 'email', 'subject', 'message'].forEach(function (n) {
    var el = f[n];
    el.addEventListener('blur', function () { check(el, !el.value && true); });
    el.addEventListener('input', function () {
      var field = el.closest('.cf-field');
      if (field.classList.contains('is-bad') || field.classList.contains('is-valid')) check(el, !field.classList.contains('is-bad'));
      else if (valid(el) && n !== 'email') field.classList.add('is-valid');
    });
  });

  // ---------- message box: grows with the text, counts characters ----------
  var count = document.getElementById('cf-count');
  function grow() {
    var t = f.message;
    t.style.height = 'auto';
    var h = Math.max(t.scrollHeight + 2, 130);
    t.style.height = Math.min(h, 380) + 'px';
    t.style.overflowY = h > 380 ? 'auto' : 'hidden';
    if (count) {
      count.textContent = t.value.length + ' / ' + MAX;
      count.classList.toggle('is-near', t.value.length > MAX * 0.9);
    }
  }
  f.message.addEventListener('input', grow);
  grow();

  // ---------- send ----------
  var result = form.querySelector('.cf-result');
  var resultText = form.querySelector('.cf-result-text');
  var submit = form.querySelector('.cf-submit');
  var copyMsg = form.querySelector('[data-copy-message]');
  var copyMail2 = form.querySelector('[data-copy-mail-2]');
  var composed = '';
  function compose() {
    return 'Subject: ' + f.subject.value.trim() + '\n\nName: ' + f.name.value.trim() + '\nEmail: ' + f.email.value.trim() + '\n\n' + f.message.value.trim();
  }
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var firstBad = null;
    ['name', 'email', 'subject', 'message'].forEach(function (n) {
      if (!check(f[n], false) && !firstBad) firstBad = f[n];
    });
    if (firstBad) { firstBad.focus(); return; }
    var body = 'Name: ' + f.name.value.trim() + '\nEmail: ' + f.email.value.trim() + '\n\n' + f.message.value.trim();
    composed = compose();
    var href = 'mailto:' + to + '?subject=' + encodeURIComponent(f.subject.value.trim()) + '&body=' + encodeURIComponent(body);
    submit.classList.add('is-busy');
    submit.querySelector('.cf-submit-label').textContent = 'Opening your email app…';
    window.location.href = href;
    window.setTimeout(function () {
      submit.classList.remove('is-busy');
      submit.querySelector('.cf-submit-label').textContent = 'Open email to send';
      resultText.textContent = 'Your email app should open now. If it does not, write to ' + to + '.';
      result.hidden = false;
      if (!reduce && result.scrollIntoView) result.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }, 1200);
  });
  var canCopy = navigator.clipboard && navigator.clipboard.writeText;
  copyMsg.hidden = !canCopy;
  copyMail2.hidden = !canCopy;
  if (canCopy) {
    copyMsg.addEventListener('click', function () { copyText(composed || compose()).then(function () { flash(copyMsg, 'Copied ✓', 'Copy message'); }); });
    copyMail2.addEventListener('click', function () { copyText(to).then(function () { flash(copyMail2, 'Copied ✓', 'Copy email'); }); });
  }

  // ---------- entrance ----------
  if (reduce || !('IntersectionObserver' in window)) return;
  var items = document.querySelectorAll('.cf-card, .side-card');
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0.05 });
  Array.prototype.forEach.call(items, function (el, i) {
    el.classList.add('reveal-up');
    el.style.transitionDelay = Math.min(i, 4) * 90 + 'ms';
    io.observe(el);
  });
  window.setTimeout(function () {
    Array.prototype.forEach.call(document.querySelectorAll('.contact-page .reveal-up:not(.is-in)'), function (el) {
      if (el.getBoundingClientRect().top < window.innerHeight) el.classList.add('is-in');
    });
  }, 1500);
})();
