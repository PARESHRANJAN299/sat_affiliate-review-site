(function () {
'use strict';
document.documentElement.classList.add('js');
})();
(function () {
'use strict';
var toggle = document.querySelector('.menu-toggle');
var menu = document.getElementById('category-menu');
if (!toggle || !menu) return;
var item = toggle.parentNode;
toggle.setAttribute('role', 'button');
toggle.setAttribute('aria-controls', 'category-menu');
toggle.setAttribute('aria-expanded', 'false');
function setOpen(open) {
menu.classList.toggle('is-open', open);
toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
}
function isOpen() { return menu.classList.contains('is-open'); }
toggle.addEventListener('click', function (event) {
if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
event.preventDefault();
setOpen(!isOpen());
});
toggle.addEventListener('keydown', function (event) {
if (event.key === ' ') {
event.preventDefault();
setOpen(!isOpen());
}
});
document.addEventListener('click', function (event) {
if (!item.contains(event.target)) setOpen(false);
});
item.addEventListener('focusout', function (event) {
if (event.relatedTarget && !item.contains(event.relatedTarget)) setOpen(false);
});
var links = menu.querySelectorAll('a');
item.addEventListener('keydown', function (event) {
var keys = ['ArrowDown', 'ArrowUp', 'Home', 'End'];
if (keys.indexOf(event.key) === -1) return;
var i = Array.prototype.indexOf.call(links, document.activeElement);
if (event.key === 'ArrowDown') {
if (!isOpen()) setOpen(true);
i = i + 1 >= links.length ? 0 : i + 1;
} else if (event.key === 'ArrowUp') {
if (!isOpen()) return;
i = i <= 0 ? links.length - 1 : i - 1;
} else if (!isOpen()) {
return;
} else if (event.key === 'Home') {
i = 0;
} else {
i = links.length - 1;
}
event.preventDefault();
links[i].focus();
});
document.addEventListener('keydown', function (event) {
if (event.key === 'Escape' && isOpen()) {
var hadFocus = item.contains(document.activeElement);
setOpen(false);
if (hadFocus) toggle.focus();
}
});
window.addEventListener('pageshow', function (event) {
if (event.persisted) setOpen(false);
});
})();
(function () {
'use strict';
var links = document.querySelectorAll('a[target="_blank"]');
Array.prototype.forEach.call(links, function (a) {
var rel = (a.getAttribute('rel') || '').split(/\s+/).filter(Boolean);
if (rel.indexOf('noopener') === -1) rel.push('noopener');
a.setAttribute('rel', rel.join(' '));
});
})();
(function () {
'use strict';
var toc = document.querySelector('details.toc');
if (toc && window.matchMedia && window.matchMedia('(max-width: 1099px)').matches) toc.open = false;
if (!('IntersectionObserver' in window)) return;
var links = document.querySelectorAll('.toc a[href^="#"], .pick-bar a[href^="#"]');
var byId = {};
Array.prototype.forEach.call(links, function (a) {
var id = a.getAttribute('href').slice(1);
(byId[id] = byId[id] || []).push(a);
});
var visible = {};
function mark() {
var ids = Object.keys(byId);
var current = null;
for (var i = 0; i < ids.length; i++) {
if (visible[ids[i]]) { current = ids[i]; break; }
}
Array.prototype.forEach.call(links, function (a) {
var on = current && a.getAttribute('href') === '#' + current;
if (a.closest('.pick-bar')) {
if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
} else if (on) {
a.setAttribute('aria-current', 'location');
} else {
a.removeAttribute('aria-current');
}
});
}
var observer = new IntersectionObserver(function (entries) {
entries.forEach(function (e) { visible[e.target.id] = e.isIntersecting; });
mark();
}, { rootMargin: '-80px 0px -55% 0px' });
Object.keys(byId).forEach(function (id) {
var el = document.getElementById(id);
if (el) observer.observe(el);
});
})();
(function () {
'use strict';
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
say('Link copied');
}, function () {
window.prompt('Copy this link', url);
});
} else {
window.prompt('Copy this link', url);
}
});
})();
(function () {
'use strict';
var bar = document.querySelector('.pick-bar');
var sentinel = document.getElementById('picks-start');
if (!bar || !sentinel || !('IntersectionObserver' in window)) return;
bar.hidden = false;
var pastIntro = false;
var atFooter = false;
function update() { bar.classList.toggle('is-visible', pastIntro && !atFooter); }
new IntersectionObserver(function (entries) {
pastIntro = !entries[0].isIntersecting && entries[0].boundingClientRect.top < 0;
update();
}).observe(sentinel);
var footer = document.querySelector('.site-footer');
if (footer) {
new IntersectionObserver(function (entries) {
atFooter = entries[0].isIntersecting;
update();
}).observe(footer);
}
})();
(function () {
'use strict';
var wrap = document.querySelector('.compare-table-wrap');
if (!wrap) return;
function check() {
if (wrap.scrollWidth > wrap.clientWidth + 1) {
wrap.setAttribute('tabindex', '0');
wrap.setAttribute('role', 'region');
wrap.setAttribute('aria-label', 'Racket comparison table');
} else {
wrap.removeAttribute('tabindex');
wrap.removeAttribute('role');
wrap.removeAttribute('aria-label');
}
}
check();
window.addEventListener('resize', check);
})();
(function () {
'use strict';
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