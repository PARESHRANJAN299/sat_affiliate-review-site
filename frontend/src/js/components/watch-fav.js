(function () {
  'use strict';
  // Saved watches on pages that do not load collection.js (a product page's Alternatives cards). Same key and same behaviour as the hearts in
  // collection.js: the heart is remembered in this browser only (localStorage "sat-saved-watches"), and it works for the visit if storage is blocked.
  var saved = [];
  try { saved = JSON.parse(localStorage.getItem('sat-saved-watches') || '[]'); } catch (e) { saved = []; }
  if (!Array.isArray(saved)) saved = [];
  document.querySelectorAll('[data-fav]').forEach(function (heart) {
    heart.setAttribute('aria-pressed', saved.indexOf(heart.dataset.fav) !== -1 ? 'true' : 'false');
    heart.addEventListener('click', function () {
      try { saved = JSON.parse(localStorage.getItem('sat-saved-watches') || '[]'); } catch (e) { /* keep this visit's list */ }
      if (!Array.isArray(saved)) saved = [];
      var i = saved.indexOf(heart.dataset.fav);
      if (i === -1) saved.push(heart.dataset.fav); else saved.splice(i, 1);
      heart.setAttribute('aria-pressed', i === -1 ? 'true' : 'false');
      try { localStorage.setItem('sat-saved-watches', JSON.stringify(saved)); } catch (e) { /* private mode */ }
    });
  });
}());
