(function () {
  'use strict';
  var root = document.querySelector('[data-fashion-detail]');
  if (!root) return;
  var status = root.querySelector('[data-product-status]');
  var url = root.dataset.canonical;
  var title = root.dataset.shareTitle;
  var thumbs = root.querySelector('[data-gallery-thumbnails]');
  if (thumbs) {
    thumbs.hidden = false;
    thumbs.querySelectorAll('[data-gallery-image]').forEach(function (button) {
      button.addEventListener('click', function () {
        root.querySelector('[data-main-product-image]').src = button.dataset.galleryImage;
        thumbs.querySelectorAll('button').forEach(function (item) { item.setAttribute('aria-pressed', String(item === button)); });
      });
    });
  }
  var copy = root.querySelector('[data-copy-product]'); copy.hidden = false;
  copy.addEventListener('click', async function () {
    try { await navigator.clipboard.writeText(url); status.textContent = 'Product link copied.'; }
    catch (error) {
      status.replaceChildren(); var input = document.createElement('input'); input.type = 'text'; input.readOnly = true;
      input.value = url; input.setAttribute('aria-label', 'Product link to copy'); status.appendChild(input); input.select();
    }
  });
  var share = root.querySelector('[data-share-product]');
  if (navigator.share) {
    share.hidden = false;
    share.addEventListener('click', async function () {
      try { await navigator.share({title:title, url:url}); } catch (error) { if (error.name !== 'AbortError') status.textContent = 'Use WhatsApp or copy the product link.'; }
    });
  }
  var save = root.querySelector('[data-save-product]');
  var key = 'sat-fashion-saved-v1'; var saved = [];
  try { var stored = JSON.parse(localStorage.getItem(key) || '[]'); if (Array.isArray(stored)) saved = stored.filter(function (id) {return typeof id === 'string';}); } catch (error) { saved = []; }
  function paint() {
    var selected = saved.indexOf(root.dataset.productId) !== -1;
    save.setAttribute('aria-pressed', String(selected)); save.setAttribute('aria-label', selected ? 'Remove saved product' : 'Save this product');
  }
  save.hidden = false; paint();
  save.addEventListener('click', function () {
    var id = root.dataset.productId; var selected = saved.indexOf(id) !== -1;
    saved = saved.filter(function (item) {return item !== id;}); if (!selected) saved.push(id);
    try { localStorage.setItem(key, JSON.stringify(saved)); paint(); status.textContent = selected ? 'Product removed from saved items.' : 'Product saved on this device.'; }
    catch (error) { status.textContent = 'Your browser could not save this product.'; }
  });
})();
