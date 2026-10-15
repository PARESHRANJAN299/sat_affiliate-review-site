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