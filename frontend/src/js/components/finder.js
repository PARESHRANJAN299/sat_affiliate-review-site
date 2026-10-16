(function () {
  'use strict';
  // "Find your racket": a tiny rule-based helper. It only repeats what the guide already says.
  var root = document.querySelector('.finder');
  if (!root) return;
  var out = root.querySelector('.finder-result');
  var picks = {
    arcsaber: { id: 'yonex-arcsaber-11-play', name: 'Yonex Arcsaber 11 Play' },
    perfly: { id: 'decathlon-perfly-br-100-set-starter', name: 'Decathlon Perfly BR 100 Set Starter' },
    astrox: { id: 'yonex-astrox-99-pro', name: 'Yonex Astrox 99 Pro' }
  };
  function choose(level, want) {
    if (level === 'new' && want === 'cost') {
      return ['perfly', 'Compare this beginner-labelled two-racket set for occasional games. Check the current pack price and whether its published 105 g weight feels comfortable.'];
    }
    if (level === 'new') {
      return ['arcsaber', 'Compare its published 4U weight and medium flex. Try the grip and confirm whether strings are included.'];
    }
    if (level === 'strong' && want === 'power') {
      return ['astrox', 'Compare this head-heavy, extra-stiff option with your current racket. Verify the model generation and stringing requirements.'];
    }
    if (level === 'regular' && want === 'power') {
      return ['arcsaber', 'Start by comparing its 4U specification and medium flex. SAT has not measured smash performance against the other options.'];
    }
    return ['arcsaber', 'A medium-flex graphite option to compare for regular play. Fit and feel need a try-on, rather than a specification alone.'];
  }
  function value(name) {
    var el = root.querySelector('input[name="' + name + '"]:checked');
    return el ? el.value : null;
  }
  function update() {
    var level = value('finder-level');
    var want = value('finder-want');
    Array.prototype.forEach.call(document.querySelectorAll('.product-block.is-match'), function (b) {
      b.classList.remove('is-match');
    });
    if (!level || !want) { out.innerHTML = ''; return; }
    var r = choose(level, want);
    var pick = picks[r[0]];
    out.innerHTML = '<strong></strong><p></p><a class="read-link"></a>';
    out.querySelector('strong').textContent = 'We suggest: ' + pick.name;
    out.querySelector('p').textContent = r[1] + ' This is a starting point, not a test result.';
    var link = out.querySelector('a');
    link.href = '#' + pick.id;
    link.textContent = 'Jump to this pick';
    var heading = document.getElementById(pick.id);
    if (heading && heading.closest('.product-block')) heading.closest('.product-block').classList.add('is-match');
  }
  root.hidden = false;
  root.addEventListener('change', update);
})();
