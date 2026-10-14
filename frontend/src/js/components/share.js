(function () {
  'use strict';
  // Reveals a "Copy link" button; uses the phone share sheet when there is one.
  var button = document.querySelector('[data-share]');
  if (!button) return;
  var status = document.querySelector('[data-share-status]');
  button.hidden = false;
  button.addEventListener('click', function () {
    var url = location.origin + location.pathname;
    if (navigator.share) {
      navigator.share({ title: document.title, url: url }).catch(function () {});
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () {
        if (status) status.textContent = 'Link copied';
      });
    } else {
      window.prompt('Copy this link', url);
    }
  });
})();
