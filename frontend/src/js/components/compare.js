(function () {
  'use strict';
  // "Compare two rackets": reads the comparison table, so it can never disagree with it.
  var root = document.querySelector('.compare-tool');
  var table = document.querySelector('table.compare-table');
  if (!root || !table) return;
  var heads = Array.prototype.map.call(table.querySelectorAll('thead th'), function (th) { return th.textContent.trim(); });
  var rows = Array.prototype.map.call(table.querySelectorAll('tbody tr'), function (tr) {
    return Array.prototype.map.call(tr.children, function (c) { return c.textContent.trim(); });
  });
  var a = root.querySelector('select[name="compare-a"]');
  var b = root.querySelector('select[name="compare-b"]');
  var out = root.querySelector('.compare-out');
  rows.forEach(function (r, i) {
    [a, b].forEach(function (sel, k) {
      var o = document.createElement('option');
      o.value = String(i);
      o.textContent = r[0];
      sel.appendChild(o);
    });
  });
  a.value = '0';
  b.value = rows.length > 1 ? '1' : '0';
  function cell(text, cls) {
    var d = document.createElement('div');
    if (cls) d.className = cls;
    d.textContent = text;
    return d;
  }
  function render() {
    var ra = rows[Number(a.value)];
    var rb = rows[Number(b.value)];
    out.innerHTML = '';
    out.appendChild(cell(ra[0]));
    out.appendChild(cell(rb[0]));
    for (var i = 1; i < heads.length; i++) {
      out.appendChild(cell(heads[i], 'row-label'));
      out.appendChild(cell(ra[i]));
      out.appendChild(cell(rb[i]));
    }
  }
  root.hidden = false;
  a.addEventListener('change', render);
  b.addEventListener('change', render);
  render();
})();
