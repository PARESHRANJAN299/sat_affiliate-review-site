(function () {
  'use strict';
  // Opens external retailer links in a new tab safely.
  var links = document.querySelectorAll('a[target="_blank"]');
  Array.prototype.forEach.call(links, function (a) {
    var rel = (a.getAttribute('rel') || '').split(/\s+/).filter(Boolean);
    if (rel.indexOf('noopener') === -1) rel.push('noopener');
    a.setAttribute('rel', rel.join(' '));
  });
})();
