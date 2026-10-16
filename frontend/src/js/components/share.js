(function () {
  'use strict';
  // Reveals a "Copy link" button; uses the phone share sheet when there is one.
  var button = document.querySelector('[data-share]');
  if (!button) return;
  var status = document.querySelector('[data-share-status]');
  button.hidden = false;
  function say(text) {
    if (!status) return;
    status.textContent = '';
    window.setTimeout(function () { status.textContent = text; }, 50);
    window.setTimeout(function () { status.textContent = ''; }, 4000);
  }
  button.addEventListener('click', function () {
    var url = location.origin + location.pathname;
    if (navigator.share) {
      navigator.share({ title: document.title, url: url }).catch(function () {});
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () {
        say(__('Link copied'));
      }, function () {
        window.prompt(__('Copy this link'), url);
      });
    } else {
      window.prompt(__('Copy this link'), url);
    }
  });
})();
