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
      return ['perfly', __('The cheapest way to try the sport. Fine for casual games, and you will likely outgrow it.')];
    }
    if (level === 'new') {
      return ['arcsaber', __('Light and forgiving, so it is easy to improve with.')];
    }
    if (level === 'strong' && want === 'power') {
      return ['astrox', __('Built for hard smashes. It is stiff and heavy at the top, so it suits players with solid technique.')];
    }
    if (level === 'regular' && want === 'power') {
      return ['arcsaber', __('Balanced and light, a good fit for regular play. The Astrox has more smash power, but it is made for strong players.')];
    }
    return ['arcsaber', __('Balanced and light, a good all-round choice for regular play.')];
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
    out.querySelector('strong').textContent = __('We suggest: {name}', { name: pick.name });
    out.querySelector('p').textContent = r[1] + ' ' + __('This is a starting point, not a test result.');
    var link = out.querySelector('a');
    link.href = '#' + pick.id;
    link.textContent = __('Jump to this pick');
    var heading = document.getElementById(pick.id);
    if (heading && heading.closest('.product-block')) heading.closest('.product-block').classList.add('is-match');
  }
  root.hidden = false;
  root.addEventListener('change', update);
})();
