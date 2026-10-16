(function () {
  'use strict';
  var footer = document.querySelector('.site-footer');
  if (!footer) return;
  var year = footer.querySelector('[data-footer-year]');
  if (year) year.textContent = String(new Date().getFullYear());
  var groups = footer.querySelectorAll('.footer-group');
  var mobile = window.matchMedia('(max-width: 620px)');
  function syncGroups() {
    Array.prototype.forEach.call(groups, function (group) {
      group.open = !mobile.matches;
      group.querySelector('summary').tabIndex = mobile.matches ? 0 : -1;
    });
  }
  Array.prototype.forEach.call(groups, function (group) {
    group.addEventListener('toggle', function () {
      if (!mobile.matches && !group.open) group.open = true;
    });
  });
  syncGroups();
  mobile.addEventListener('change', syncGroups);

  var copy = footer.querySelector('[data-footer-copy]');
  var email = footer.querySelector('[data-footer-email]');
  var status = footer.querySelector('[data-footer-copy-status]');
  if (!copy || !email || !status || !navigator.clipboard || !window.isSecureContext) return;
  copy.hidden = false;
  var label = copy.querySelector('span');
  var resetTimer;
  copy.addEventListener('click', function () {
    copy.disabled = true;
    clearTimeout(resetTimer);
    navigator.clipboard.writeText(email.textContent.trim()).then(function () {
      label.textContent = 'Copied';
      status.textContent = 'Email address copied.';
    }).catch(function () {
      label.textContent = 'Copy email';
      status.textContent = 'Please select and copy the email address above.';
    }).finally(function () {
      copy.disabled = false;
      resetTimer = setTimeout(function () { label.textContent = 'Copy email'; status.textContent = ''; }, 4000);
    });
  });

  // The statement at the bottom: one slim line that shows its sentences one after another (all visible without a script).
  var box = footer.querySelector('[data-footer-rotator]');
  var lines = box ? Array.prototype.slice.call(box.querySelectorAll('.footer-mission-line')) : [];
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (box && lines.length > 1 && !reduce) {
    var stage = box.querySelector('.footer-mission-stage');
    var dots = document.createElement('div');
    dots.className = 'footer-mission-dots';
    var bar = document.createElement('span');
    bar.className = 'footer-mission-bar';
    bar.setAttribute('aria-hidden', 'true');
    var buttons = lines.map(function (line, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('aria-label', 'Show message ' + (i + 1) + ' of ' + lines.length);
      b.addEventListener('click', function () { show(i); });
      dots.appendChild(b);
      return b;
    });
    var current = 0;
    function measure() {
      box.classList.remove('is-rotating');
      var tallest = 0;
      lines.forEach(function (l) { tallest = Math.max(tallest, l.getBoundingClientRect().height || 0); });
      // lines flow inline while the box is not rotating, so measure each as a block of the stage width
      var width = stage.getBoundingClientRect().width;
      tallest = 0;
      lines.forEach(function (l) {
        var clone = l.cloneNode(true);
        clone.style.cssText = 'position:absolute;visibility:hidden;display:block;left:0;top:0;width:' + width + 'px';
        stage.appendChild(clone);
        tallest = Math.max(tallest, clone.getBoundingClientRect().height);
        stage.removeChild(clone);
      });
      stage.style.minHeight = Math.ceil(tallest) + 'px';
      box.classList.add('is-instant', 'is-rotating');
    }
    function show(i) {
      current = (i + lines.length) % lines.length;
      lines.forEach(function (l, k) {
        l.classList.toggle('is-on', k === current);
        l.setAttribute('aria-hidden', k === current ? 'false' : 'true');
      });
      buttons.forEach(function (b, k) { if (k === current) b.setAttribute('aria-current', 'true'); else b.removeAttribute('aria-current'); });
      // restart the progress line, which also times the next change
      bar.style.animation = 'none';
      void bar.offsetWidth;
      bar.style.animation = '';
    }
    box.appendChild(dots);
    box.appendChild(bar);
    measure();
    show(0);
    setTimeout(function () { box.classList.remove('is-instant'); }, 60);
    bar.addEventListener('animationend', function () { show(current + 1); });
    ['mouseenter', 'focusin'].forEach(function (name) {
      box.addEventListener(name, function () { box.classList.add('is-paused'); });
    });
    var touchTimer;
    box.addEventListener('touchstart', function () {
      box.classList.add('is-paused');
      clearTimeout(touchTimer);
      touchTimer = setTimeout(function () { box.classList.remove('is-paused'); }, 4000);
    }, { passive: true });
    ['mouseleave', 'focusout'].forEach(function (name) {
      box.addEventListener(name, function () { box.classList.remove('is-paused'); });
    });
    var resizeTimer;
    window.addEventListener('resize', function () {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(function () { measure(); show(current); setTimeout(function () { box.classList.remove('is-instant'); }, 60); }, 150);
    });
  }
})();
