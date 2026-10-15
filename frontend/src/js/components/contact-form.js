(function () {
  'use strict';
  // Builds an email in the visitor's own email app. The site has no server, so nothing is sent from here.
  var form = document.getElementById('contact-form');
  if (!form) return;
  form.hidden = false;
  var status = form.querySelector('.form-status');
  var to = document.querySelector('.contact-email a');
  to = to ? to.textContent.trim() : '';
  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var f = form.elements;
    var body = 'Name: ' + f.name.value + '\nEmail: ' + f.email.value + '\n\n' + f.message.value;
    var href = 'mailto:' + to + '?subject=' + encodeURIComponent(f.subject.value) + '&body=' + encodeURIComponent(body);
    window.location.href = href;
    if (status) status.textContent = 'Your email app should open now. If it does not, write to ' + to + '.';
  });
})();
