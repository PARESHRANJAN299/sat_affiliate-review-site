"""Progressively enhanced collections shared by category landing pages."""
import html
import json
import re
from collections import Counter


def esc(value):
    return html.escape(str(value), quote=True)


def key(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')


def render(cards, groups, *, uid, title, noun='product', plural='products', preset_gender='', genders=None, top_html='', visible=None, page_size=0, grid_note='', panel_top='', after_html='', tips_html='', controls_html='', main_toolbar=False):
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
            fields.append(f'<fieldset class="fgroup" data-fgroup="{esc(group["key"])}"><legend>{esc(group["title"])}</legend><div class="fopts">{boxes}</div></fieldset>')
    segments = ''
    if genders:
        segments = '<div class="collection-segments" role="group" aria-label="Watch collection">' + ''.join(
            f'<button type="button" data-gender="{esc(value)}" aria-pressed="false">{esc(label)}</button>'
            for value, label in genders) + '</div>'
    in_hero = '<!--segments-->' in top_html
    top_html = top_html.replace('<!--segments-->', segments)
    if in_hero:
        segments = ''
    head = (f'<header class="collection-head"><div><h2 id="{esc(uid)}-title">{esc(title)}</h2>'
            f'<p data-collection-count role="status">{shown} {esc(noun if shown == 1 else plural)}</p></div></header>')
    controls = ('<div class="collection-controls" data-controls hidden>' + segments + controls_html +
                f'<label class="collection-search"><span class="visually-hidden">Search {esc(plural)}</span><input type="search" data-search placeholder="Search {esc(plural)}" autocomplete="off"></label>'
                + f'<button type="button" class="btn btn-outline btn-small collection-filter-open" data-filter-open aria-haspopup="dialog" aria-controls="{esc(uid)}-filters">Filters <span data-filter-badge></span></button>' +
                '<label class="collection-sort"><span>Sort</span> <select data-sort aria-label="Sort"><option value="featured">Featured</option><option value="name">Name A–Z</option><option value="name-desc">Name Z–A</option></select></label></div>')
    active = '<div class="collection-active" data-active hidden></div>'
    panel = (f'<dialog class="collection-filters" id="{esc(uid)}-filters" aria-labelledby="{esc(uid)}-filter-title" data-filter-panel>'
             f'<div class="cf-head"><strong id="{esc(uid)}-filter-title">Filters</strong><button type="button" data-filter-close aria-label="Close filters">✕</button></div>' + panel_top + ''.join(fields) +
             f'<div class="cf-foot"><button type="button" class="linklike" data-filter-clear>Clear all</button><button type="button" class="btn btn-primary btn-small" data-filter-close data-apply-label>Show {shown} {esc(plural if shown != 1 else noun)}</button></div></dialog>')
    rest = ('<div class="watch-grid" data-collection-grid>' + card_html + tips_html + '</div>'
            f'<div class="collection-empty" data-empty {"hidden" if shown else ""}><h3>No matching {esc(plural)}</h3><p>Try another search or remove a filter.</p><button type="button" class="btn btn-outline" data-filter-clear>Clear filters</button></div>'
            '<nav class="collection-pagination" data-pagination aria-label="Product pages" hidden></nav>')
    opening = (f'<section class="collection" id="{esc(uid)}" data-collection data-noun="{esc(noun)}" data-plural="{esc(plural)}" data-preset-gender="{esc(preset_gender)}" data-page-size="{page_size}" '
               f'{"data-top-filters" if top_html else ""} aria-labelledby="{esc(uid)}-title">')
    if main_toolbar:   # the heading, filter bar and active filters sit above the watches, inside the same column as the list
        return (opening + top_html + '<div class="collection-layout">' + panel + '<div class="collection-main">' + head + controls + active + grid_note + rest + '</div></div>' + after_html + '</section>')
    return (opening + top_html + head + controls + active + '<div class="collection-layout">' + panel + '<div class="collection-main">' + grid_note + rest + '</div></div>' + after_html + '</section>')


def render_store(cards, groups, *, uid, title, noun='product', plural='products', preset_gender='', preset_from='', premium_json='', genders=None, top_html='', visible=None, page_size=0, grid_note='',
                 panel_top='', after_html='', panel_title='Filters', sizes_json=''):
    """All cards remain accessible without JS; controls enhance the same server-rendered list.
    genders = [(value, label, count)]: rendered as a raised two-part plate where the top_html placeholder <!--segments--> sits.
    The filter panel is always a dialog: a bottom sheet on phones and a side drawer on larger screens."""
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
            fields.append(f'<fieldset class="fgroup" data-fgroup="{esc(group["key"])}"><legend>{esc(group["title"])}</legend><div class="fopts">{boxes}</div></fieldset>')
    plate = ''
    if genders:
        plate = ('<div class="gender-plate" role="group" aria-label="Watch collection" data-pick=""><i class="gp-thumb" aria-hidden="true"></i>' + ''.join(
            f'<button type="button" data-gender="{esc(g[0])}" aria-pressed="false"><span class="gp-l">{esc(g[1])}</span>'
            f'<small class="gp-c">{g[2]} {"watch" if g[2] == 1 else "watches"}</small></button>' for g in genders) + '</div>')
    top_html = top_html.replace('<!--segments-->', plate)
    controls = ('<div class="collection-controls" data-controls hidden>'
                f'<label class="collection-search"><span class="visually-hidden">Search {esc(plural)}</span><input type="search" data-search placeholder="Search {esc(plural)}" autocomplete="off"></label>'
                '<label class="collection-sort"><span>Sort</span> <select data-sort aria-label="Sort"><option value="featured">Featured</option><option value="name">Name A\u2013Z</option><option value="name-desc">Name Z\u2013A</option></select></label>'
                f'<button type="button" class="btn btn-outline btn-small collection-filter-open" data-filter-open aria-haspopup="dialog" aria-controls="{esc(uid)}-filters">'
                '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg>Filter <span data-filter-badge></span></button></div>')
    head = (f'<header class="collection-head sel-head"><div class="sel-t"><h2 id="{esc(uid)}-title">{esc(title)}</h2>'
            f'<p data-collection-count role="status">{shown} {esc(noun if shown == 1 else plural)}</p></div>{controls}</header>')
    active = '<div class="collection-active" data-active hidden></div>'
    panel = (f'<dialog class="collection-filters" id="{esc(uid)}-filters" aria-labelledby="{esc(uid)}-filter-title" data-filter-panel{f" data-sizes={chr(39)}{esc(sizes_json)}{chr(39)}" if sizes_json else ""}>'
             f'<div class="cf-head"><div class="cf-ht"><strong id="{esc(uid)}-filter-title">{esc(panel_title)}</strong><span class="cf-count" data-cf-count>{shown} {esc(plural if shown != 1 else noun)}</span></div>'
             '<button type="button" class="linklike cf-reset" data-filter-clear>Reset</button><button type="button" class="cf-x" data-filter-close aria-label="Close filters">\u2715</button></div>'
             + panel_top + ''.join(fields) +
             f'<div class="cf-foot"><button type="button" class="linklike" data-filter-clear>Clear</button><button type="button" class="btn btn-primary btn-small" data-filter-close data-apply-label>Show {shown} {esc(plural if shown != 1 else noun)}</button></div></dialog>')
    rest = ('<div class="watch-grid" data-collection-grid>' + card_html + '</div>'
            f'<div class="collection-empty" data-empty {"hidden" if shown else ""}><h3>No matching {esc(plural)}</h3><p>Try another search or remove a filter.</p><button type="button" class="btn btn-outline" data-filter-clear>Clear filters</button></div>'
            '<nav class="collection-pagination" data-pagination aria-label="Product pages" hidden></nav>')
    prem_attr = ' data-premium="' + esc(premium_json) + '"' if premium_json else ''
    opening = (f'<section class="collection" id="{esc(uid)}" data-collection data-noun="{esc(noun)}" data-plural="{esc(plural)}" data-preset-gender="{esc(preset_gender)}" data-preset-from="{esc(preset_from)}"{prem_attr} data-page-size="{page_size}" '
               f'data-top-filters data-store aria-labelledby="{esc(uid)}-title">')
    return (opening + top_html + '<div class="collection-layout">' + panel + '<div class="collection-main">' + head + active + grid_note + rest + '</div></div>' + after_html + '</section>')


def price_slider(steps, group="budget", title="Budget"):
    """Stepped budget rail ("show watches under this amount", cumulative like the existing Under X bands). No prices are shown or stored.
    steps = [(value, label, short label, watches whose own band it is)], lowest band first; they come from the category's price-band configuration,
    so any category can pass its own bands. Hidden until the script enables it."""
    if len(steps) < 2:
        return ''
    data = json.dumps([[value, label, count] for value, label, _, count in steps], ensure_ascii=False)
    nodes = '<button type="button" class="sr-step" data-step="-1" aria-pressed="true"><i class="sr-dot"></i><span>Any</span></button>' + ''.join(
        f'<button type="button" class="sr-step" data-step="{i}" aria-pressed="false"><i class="sr-dot"></i><span>{esc(short)}</span></button>' for i, (_, _, short, _) in enumerate(steps))
    return (f'<div class="price-slider price-bands" data-price-slider data-group="{esc(group)}" data-steps="{esc(data)}" style="--n:{len(steps) + 1}" hidden>'
            f'<div class="price-slider-head"><h2 class="wd-label">{esc(title)}</h2><button type="button" class="sr-now" data-price-clear aria-label="Clear budget"><span data-price-help>Any price</span></button></div>'
            f'<div class="sr-wrap"><b class="sr-tip" aria-hidden="true" data-price-tip></b><div class="sr-rail" role="group" aria-label="Maximum {esc(title.lower())}">{nodes}</div></div>'
            '<output class="visually-hidden" data-price-label>Any price</output></div>')


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
