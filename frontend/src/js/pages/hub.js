(function () {
  'use strict';
  // Progressive enhancement: every category remains a normal link without JavaScript.
  var directory = document.querySelector('[data-category-directory]');
  if (directory) {
    var tools = directory.querySelector('.directory-tools');
    var search = directory.querySelector('#category-search');
    var filters = directory.querySelectorAll('[data-category-filter]');
    var categories = directory.querySelectorAll('[data-category-search]');
    var grid = directory.querySelector('.directory-grid');
    var count = directory.querySelector('#category-count');
    var noCategories = directory.querySelector('.directory-empty');
    var active = 'all';
    var normalize = function (value) { return value.toLowerCase().replace(/&/g, ' and ').replace(/[^a-z0-9]+/g, ' ').trim(); };
    function updateCategories() {
      var terms = normalize(search.value).split(' ').filter(Boolean);
      var shown = 0;
      Array.prototype.forEach.call(categories, function (item) {
        var text = normalize(item.getAttribute('data-category-search'));
        var matches = (active === 'all' || item.getAttribute('data-category-state') === active) && terms.every(function (term) { return text.indexOf(term) !== -1; });
        item.hidden = !matches;
        if (matches) shown += 1;
      });
      grid.classList.toggle('is-filtered', shown !== categories.length);
      noCategories.hidden = shown !== 0;
      Array.prototype.forEach.call(filters, function (button) { button.setAttribute('aria-pressed', String(button.getAttribute('data-category-filter') === active)); });
      count.textContent = shown === categories.length ? 'Showing all ' + shown + ' categories' : shown + (shown === 1 ? ' category' : ' categories') + ' found';
    }
    Array.prototype.forEach.call(filters, function (button) {
      button.addEventListener('click', function () { active = button.getAttribute('data-category-filter'); updateCategories(); });
    });
    search.addEventListener('input', updateCategories);
    directory.querySelector('[data-category-reset]').addEventListener('click', function () {
      active = 'all'; search.value = ''; updateCategories(); search.focus();
    });
    tools.hidden = false;
    updateCategories();
  }
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
    if (live) live.textContent = q ? shown + (shown === 1 ? ' guide shown' : ' guides shown') : '';
  });
})();
