"""Progressively enhanced collections shared by category landing pages."""
import html
import json
import re
from collections import Counter


def esc(value):
    return html.escape(str(value), quote=True)


def key(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')


def render(cards, groups, *, uid, title, noun='product', plural='products', preset_gender='', genders=None, top_html='', visible=None, page_size=0, grid_note=''):
    """All cards remain accessible without JS; controls enhance the same server-rendered list."""
    visible = visible if visible is not None else [True] * len(cards)
    shown = sum(visible)
    card_html = ''.join(card if show else card.replace('<article ', '<article hidden ', 1) for card, show in zip(cards, visible))
    fields = []
    for group in groups:
        boxes = ''.join(
            f'<label class="fopt{" is-empty" if not count else ""}"><input type="checkbox" data-group="{esc(group["key"])}" value="{esc(value)}"'
            f'{" checked" if value in group.get("checked", []) else ""}{" disabled" if not count else ""}><span>{esc(label)}</span><small>{count}</small></label>'
            for value, label, count in group['items'] if count or group.get('show_empty'))
        if boxes:
            fields.append(f'<fieldset class="fgroup"><legend>{esc(group["title"])}</legend>{boxes}</fieldset>')
    segments = ''
    if genders:
        segments = '<div class="collection-segments" role="group" aria-label="Watch collection">' + ''.join(
            f'<button type="button" data-gender="{esc(value)}" aria-pressed="false">{esc(label)}</button>'
            for value, label in genders) + '</div>'
    return (
        f'<section class="collection" id="{esc(uid)}" data-collection data-noun="{esc(noun)}" data-plural="{esc(plural)}" data-preset-gender="{esc(preset_gender)}" data-page-size="{page_size}" {"data-top-filters" if top_html else ""} aria-labelledby="{esc(uid)}-title">'
        + top_html + f'<header class="collection-head"><div><h2 id="{esc(uid)}-title">{esc(title)}</h2>'
        f'<p data-collection-count role="status">{shown} {esc(noun if shown == 1 else plural)}</p></div></header>'
        '<div class="collection-controls" data-controls hidden>' + segments +
        f'<label class="collection-search"><span class="visually-hidden">Search {esc(plural)}</span><input type="search" data-search placeholder="Search {esc(plural)}" autocomplete="off"></label>'
        + f'<button type="button" class="btn btn-outline btn-small collection-filter-open" data-filter-open aria-haspopup="dialog" aria-controls="{esc(uid)}-filters">Filters <span data-filter-badge></span></button>' +
        '<label class="collection-sort">Sort <select data-sort><option value="featured">Featured</option><option value="name">Name A–Z</option><option value="name-desc">Name Z–A</option></select></label></div>'
        '<div class="collection-active" data-active hidden></div><div class="collection-layout">'
        f'<dialog class="collection-filters" id="{esc(uid)}-filters" aria-labelledby="{esc(uid)}-filter-title" data-filter-panel>'
        f'<div class="cf-head"><strong id="{esc(uid)}-filter-title">Filter by</strong><button type="button" data-filter-close aria-label="Close filters">✕</button></div>' + ''.join(fields) +
        f'<div class="cf-foot"><button type="button" class="linklike" data-filter-clear>Clear all</button><button type="button" class="btn btn-primary btn-small" data-filter-close>Show {esc(plural)}</button></div></dialog>'
        '<div class="collection-main">' + grid_note + '<div class="watch-grid" data-collection-grid>' + card_html + '</div>'
        f'<div class="collection-empty" data-empty {"hidden" if shown else ""}><h3>No matching {esc(plural)}</h3><p>Try another search or remove a filter.</p><button type="button" class="btn btn-outline" data-filter-clear>Clear filters</button></div>'
        '<nav class="collection-pagination" data-pagination aria-label="Product pages" hidden></nav></div></div></section>')


def price_slider(steps, group="budget", title="Price", dual=False):
    """Stepped price-band slider (no prices are shown or stored). steps = [(value, label, short label, watches whose own band it is)], lowest band first.
    dual=False: one handle, Any price then Up to each band (home page). dual=True: a From handle and a To handle plus one-tap ranges such as
    "Rs 2,000 - Rs 3,000", which show only watches whose own band lies in that range. Hidden until the script enables it."""
    if len(steps) < 2:
        return ''
    most = max(count for *_, count in steps) or 1
    bars = '<span class="price-bar-gap"></span>' + ''.join(
        f'<span data-price-bar style="height:{max(10, round(100 * count / most))}%"></span>' for *_, count in steps)
    ticks = '<span>Any</span>' + ''.join(f'<span>{esc(short)}</span>' for _, _, short, _ in steps)
    data = json.dumps([[value, label, count] for value, label, _, count in steps], ensure_ascii=False)
    head = f'<div class="price-slider-head"><h2 class="wd-label">{esc(title)}</h2>' + ('' if dual else '<output data-price-label>Any price</output>') + '</div>'
    if dual:
        n = len(steps)
        controls = ('<div class="price-ranges" role="group" aria-label="Quick price ranges" data-price-ranges></div>'
                    '<details class="price-fine"><summary>Fine-tune range <output data-price-label>Any price</output></summary>'
                    f'<div class="price-bars" aria-hidden="true">{bars}</div>'
                    '<div class="price-track" data-price-track>'
                    f'<input type="range" class="price-lo" min="0" max="{n}" step="1" value="0" aria-label="Lowest price band">'
                    f'<input type="range" class="price-hi" min="0" max="{n}" step="1" value="{n}" aria-label="Highest price band"></div>'
                    f'<div class="price-ticks" aria-hidden="true">{ticks}</div></details>')
    else:
        controls = (f'<div class="price-bars" aria-hidden="true">{bars}</div>'
                    f'<input type="range" min="0" max="{len(steps)}" step="1" value="0" aria-label="Maximum price band" aria-valuetext="Any price">'
                    f'<div class="price-ticks" aria-hidden="true">{ticks}</div>')
    return (f'<div class="price-slider{" price-dual" if dual else ""}" data-price-slider data-group="{esc(group)}" data-steps="{esc(data)}" hidden>'
            + head + controls + '</div>')


def groups(items, specs):
    """Filter counts come from the published catalogue, never placeholder stock."""
    result = []
    for field, title in specs:
        counts = Counter()
        labels = {}
        for item in items:
            values = item.get(field, [])
            if isinstance(values, str):
                values = [values]
            for label in set(values):
                if label:
                    counts[key(label)] += 1
                    labels[key(label)] = label
        result.append({'key': field, 'title': title, 'items': [(value, labels[value], count) for value, count in sorted(counts.items(), key=lambda x: labels[x[0]].casefold())]})
    return result


def card(item):
    attrs = ' '.join(f'data-{field}="{esc(" ".join(key(v) for v in (values if isinstance(values, list) else [values])))}"' for field, values in item.get('filters', {}).items())
    media = f'<div class="watch-media"><img src="{esc(item["image"])}" alt="" loading="lazy" width="480" height="360"></div>' if item.get('image') else ''
    return (f'<article class="watch-card" {attrs} data-name="{esc(item["name"])}">{media}<div class="watch-body">'
            f'<p class="watch-brand">{esc(item.get("label", "Buying advice"))}</p>'
            f'<h3 class="watch-model"><a href="{esc(item["url"])}">{esc(item["name"])}</a></h3>'
            f'<p class="watch-verdict">{esc(item["description"])}</p>'
            f'<div class="watch-actions"><a class="btn btn-outline btn-small" href="{esc(item["url"])}">{esc(item.get("action", "Read buying advice"))} &rarr;</a></div></div></article>')
