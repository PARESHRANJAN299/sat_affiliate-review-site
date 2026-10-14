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