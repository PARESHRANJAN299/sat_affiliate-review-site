(function () {
  'use strict';
  // Lets CSS know scripting is available.
  document.documentElement.classList.add('js');
  // Text shown by scripts goes through __() so Hindi and Tamil pages can swap it (window.SATI18N is set on those pages).
  // __('Show {n} more', { n: 12 })
  window.__ = function (text, vars) {
    var out = (window.SATI18N && window.SATI18N[text]) || text;
    if (vars) for (var k in vars) if (Object.prototype.hasOwnProperty.call(vars, k)) out = out.split('{' + k + '}').join(vars[k]);
    return out;
  };
})();
