(function () {
  'use strict';
  // Search box on the Products page: filters the guide cards as you type.
  var box = document.querySelector('.product-search');
  var input = document.getElementById('product-search');
  var empty = document.getElementById('no-results');
  var live = document.getElementById('search-count');
  var cards = document.querySelectorAll('.article-card[data-search]');
  if (!box || !input || !cards.length) return;
  box.hidden = false;
  input.addEventListener('input', function () {
    var q = input.value.trim().toLowerCase();
    var shown = 0;
    Array.prototype.forEach.call(cards, function (card) {
      var match = !q || card.getAttribute('data-search').indexOf(q) !== -1;
      card.hidden = !match;
      if (match) shown += 1;
    });
    if (empty) empty.hidden = shown !== 0;
    if (live) live.textContent = q ? shown + (shown === 1 ? __(' guide shown') : __(' guides shown')) : '';
  });
})();
