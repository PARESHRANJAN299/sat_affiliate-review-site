(function () {
  'use strict';
  var footer = document.querySelector('.site-footer');
  if (!footer) return;
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
})();
