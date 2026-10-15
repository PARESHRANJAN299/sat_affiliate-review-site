(function () {
  'use strict';
  // Native disclosure keeps the mobile logo menu usable without JavaScript.
  var menu = document.querySelector('.mobile-site-menu');
  if (!menu) return;
  var trigger = menu.querySelector('summary');
  function close(restoreFocus) {
    if (!menu.open) return;
    menu.open = false;
    if (restoreFocus) trigger.focus();
  }
  document.addEventListener('click', function (event) {
    if (!menu.contains(event.target)) close(false);
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && menu.open) close(menu.contains(document.activeElement));
  });
  menu.addEventListener('focusout', function (event) {
    if (event.relatedTarget && !menu.contains(event.relatedTarget)) close(false);
  });
  menu.addEventListener('click', function (event) {
    if (event.target.closest('a')) close(false);
  });
  menu.addEventListener('toggle', function () {
    if (!menu.open) return;
    var categories = document.getElementById('category-menu');
    var categoryToggle = document.querySelector('.menu-toggle');
    if (categories) categories.classList.remove('is-open');
    if (categoryToggle) categoryToggle.setAttribute('aria-expanded', 'false');
  });
  window.matchMedia('(max-width: 719px)').addEventListener('change', function () { close(false); });
  window.addEventListener('pageshow', function (event) { if (event.persisted) close(false); });
})();

(function () {
  'use strict';
  // "Shop by Category" dropdown. Without JavaScript the toggle is a normal link to /products/.
  var toggle = document.querySelector('.menu-toggle');
  var menu = document.getElementById('category-menu');
  if (!toggle || !menu) return;
  var item = toggle.parentNode;

  toggle.setAttribute('role', 'button');
  toggle.setAttribute('aria-controls', 'category-menu');
  toggle.setAttribute('aria-expanded', 'false');

  function setOpen(open) {
    menu.classList.toggle('is-open', open);
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  function isOpen() { return menu.classList.contains('is-open'); }

  toggle.addEventListener('click', function (event) {
    // Let ctrl/cmd/shift/middle-click open /products/ normally.
    if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
    event.preventDefault();
    setOpen(!isOpen());
  });

  toggle.addEventListener('keydown', function (event) {
    if (event.key === ' ') {
      event.preventDefault();
      setOpen(!isOpen());
    }
  });

  document.addEventListener('click', function (event) {
    if (!item.contains(event.target)) setOpen(false);
  });

  item.addEventListener('focusout', function (event) {
    if (event.relatedTarget && !item.contains(event.relatedTarget)) setOpen(false);
  });

  var links = menu.querySelectorAll('a');
  item.addEventListener('keydown', function (event) {
    var keys = ['ArrowDown', 'ArrowUp', 'Home', 'End'];
    if (keys.indexOf(event.key) === -1) return;
    var i = Array.prototype.indexOf.call(links, document.activeElement);
    if (event.key === 'ArrowDown') {
      if (!isOpen()) setOpen(true);
      i = i + 1 >= links.length ? 0 : i + 1;
    } else if (event.key === 'ArrowUp') {
      if (!isOpen()) return;
      i = i <= 0 ? links.length - 1 : i - 1;
    } else if (!isOpen()) {
      return;
    } else if (event.key === 'Home') {
      i = 0;
    } else {
      i = links.length - 1;
    }
    event.preventDefault();
    links[i].focus();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && isOpen()) {
      var hadFocus = item.contains(document.activeElement);
      setOpen(false);
      if (hadFocus) toggle.focus();
    }
  });

  window.addEventListener('pageshow', function (event) {
    if (event.persisted) setOpen(false);
  });
})();

(function () {
  'use strict';
  // Phone header: dimmed backdrop behind open menus, staggered rows, a one-time hint that the
  // pills open menus, swipe-up to close, and a header that tucks away while reading.
  var header = document.querySelector('.site-header');
  if (!header || !window.matchMedia) return;
  var phone = window.matchMedia('(max-width: 719px)');
  var logoMenu = header.querySelector('.mobile-site-menu');
  var logoTrigger = logoMenu && logoMenu.querySelector('summary');
  var shopToggle = header.querySelector('.menu-toggle');
  var shopMenu = document.getElementById('category-menu');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  header.classList.add('js-smart');

  var backdrop = document.createElement('div');
  backdrop.className = 'nav-backdrop';
  backdrop.setAttribute('aria-hidden', 'true');
  document.body.appendChild(backdrop);

  function stagger(list) {
    for (var i = 0; list && i < list.length; i++) list[i].style.setProperty('--i', i);
  }
  if (shopMenu) stagger(shopMenu.querySelectorAll('.menu-list > li'));
  if (logoMenu) stagger(logoMenu.querySelectorAll('.mobile-site-links li'));

  function anyOpen() {
    return !!((logoMenu && logoMenu.open) || (shopMenu && shopMenu.classList.contains('is-open')));
  }
  function sync() {
    backdrop.classList.toggle('is-on', phone.matches && anyOpen());
    if (anyOpen()) header.classList.remove('is-hidden');
  }
  if (logoMenu) logoMenu.addEventListener('toggle', sync);
  if (shopMenu && window.MutationObserver) {
    new MutationObserver(sync).observe(shopMenu, { attributes: true, attributeFilter: ['class'] });
  }
  if (phone.addEventListener) phone.addEventListener('change', sync);

  // swipe up on an open menu to dismiss it
  var startY = null;
  function swipeClose(panel, close) {
    if (!panel) return;
    panel.addEventListener('touchstart', function (e) { startY = e.touches[0].clientY; }, { passive: true });
    panel.addEventListener('touchend', function (e) {
      if (startY === null) return;
      var dy = e.changedTouches[0].clientY - startY;
      startY = null;
      if (dy < -60) close();
    }, { passive: true });
  }
  swipeClose(shopMenu, function () { if (shopToggle) shopToggle.click(); });
  swipeClose(logoMenu && logoMenu.querySelector('.mobile-site-links'), function () { logoMenu.open = false; });

  // one-time nudge per browser session so people know both pills open menus
  var seen = false;
  try { seen = sessionStorage.getItem('sat-nav-hint') === '1'; } catch (e) { seen = false; }
  if (!seen && !reduce) {
    var targets = [logoTrigger, shopToggle];
    targets.forEach(function (el) { if (el) el.classList.add('hint-ring'); });
    var clear = function () {
      targets.forEach(function (el) { if (el) el.classList.remove('hint-ring'); });
      try { sessionStorage.setItem('sat-nav-hint', '1'); } catch (e) { /* storage unavailable */ }
    };
    setTimeout(clear, 6500);
    header.addEventListener('click', clear, { once: true });
  }

  // hide on scroll down, return on scroll up (phones only, never while a menu is open)
  var lastY = window.pageYOffset || 0;
  var ticking = false;
  function onScroll() {
    ticking = false;
    var y = window.pageYOffset || 0;
    header.classList.toggle('is-scrolled', y > 8);
    if (!phone.matches || anyOpen()) { lastY = y; return; }
    var dy = y - lastY;
    if (y < 80) header.classList.remove('is-hidden');
    else if (dy > 8) header.classList.add('is-hidden');
    else if (dy < -8) header.classList.remove('is-hidden');
    if (Math.abs(dy) > 8) lastY = y;
  }
  window.addEventListener('scroll', function () {
    if (!ticking) { ticking = true; window.requestAnimationFrame(onScroll); }
  }, { passive: true });
  header.addEventListener('focusin', function () { header.classList.remove('is-hidden'); });
  onScroll();
})();
