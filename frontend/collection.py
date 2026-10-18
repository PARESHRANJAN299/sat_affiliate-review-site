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


def _fieldset(group):
    boxes = ''.join(
        f'<label class="fopt{" is-empty" if not count else ""}"><input type="checkbox" data-group="{esc(group["key"])}" value="{esc(value)}"'
        f'{" checked" if value in group.get("checked", []) else ""}{" disabled" if not count else ""}><span>{esc(label)}</span><small>{count}</small></label>'
        for value, label, count in group['items'] if count or group.get('show_empty'))
    if not boxes:
        return ''
    info = group.get('info')
    # a small round "i" in the row header (the visible text lives in the aria-label, which names the group it explains)
    info_btn = (f'<button type="button" class="cf-info-open" data-info-open="{esc(group["key"])}" aria-haspopup="dialog" aria-label="{esc(info["link"])}" title="{esc(info["link"])}"><span aria-hidden="true">i</span></button>' if info else '')
    return f'<fieldset class="fgroup{" has-info" if info else ""}" data-fgroup="{esc(group["key"])}"><legend>{esc(group["title"])}</legend>{info_btn}<div class="fopts">{boxes}</div></fieldset>'


def _info_layer(group):
    info = group['info']
    paras = ''.join(f'<p>{esc(text)}</p>' for text in info['paragraphs'])
    return (f'<div class="cf-info" data-info="{esc(group["key"])}" role="group" aria-labelledby="cf-info-{esc(group["key"])}" hidden>'
            f'<div class="cf-info-scrim" data-info-close></div><div class="cf-info-card"><i class="cf-grab" aria-hidden="true"></i>'
            f'<div class="cf-info-head"><strong id="cf-info-{esc(group["key"])}">{esc(info["title"])}</strong>'
            '<button type="button" class="cf-x" data-info-close aria-label="Close">\u2715</button></div>'
            f'<div class="cf-info-body">{paras}</div><button type="button" class="btn btn-primary cf-info-ok" data-info-close data-layer-focus>{esc(info.get("ok", "Got it"))}</button></div></div>')


def render_store(cards, groups, *, uid, title, noun='product', plural='products', preset_gender='', preset_from='', premium_json='', genders=None, top_html='', visible=None, page_size=0, grid_note='',
                 panel_top='', after_html='', panel_title='Filters', sizes_json='', sections=None, slots=None):
    """All cards remain accessible without JS; controls enhance the same server-rendered list.
    genders = [(value, label, count)]: rendered as a raised two-part plate where the top_html placeholder <!--segments--> sits.
    The filter panel is always a dialog: a bottom sheet on phones and a side drawer on larger screens.
    sections = [(title, [group keys])]: the filter rows are grouped under labelled sections; a group missing from every section goes to the last one,
    and a section with no group is not drawn. slots = {group key: html}: extra html (the budget rail, a collection strip) placed just before that group's row.
    A group may carry info = {link, title, paragraphs}: a small explanation sheet opened from a link in that group."""
    visible = visible if visible is not None else [True] * len(cards)
    shown = sum(visible)
    card_html = ''.join(card if show else card.replace('<article ', '<article hidden ', 1) for card, show in zip(cards, visible))
    slots = dict(slots or {})
    rows = {group['key']: _fieldset(group) for group in groups}
    if sections:
        order, placed = [], set()
        for sec_title, keys in sections:
            mine = [k for k in keys if k in rows]
            placed.update(mine)
            order.append([sec_title, mine])
        rest = [group['key'] for group in groups if group['key'] not in placed]
        drawn = [entry for entry in order if entry[1]]
        if drawn and rest:
            drawn[-1][1] += rest
        elif rest:
            order.append(['', rest])
    else:
        order = [['', [group['key'] for group in groups]]]
    body = ''
    for sec_title, keys in order:
        inner = ''
        for k in keys:
            inner += slots.pop(k, '') + rows.get(k, '')
        if inner.strip() and sec_title:
            body += f'<section class="cf-sec" data-cf-section="{esc(key(sec_title))}"><h3 class="cf-sec-t">{esc(sec_title)}</h3>{inner}</section>'
        elif inner.strip():
            body += f'<section class="cf-sec">{inner}</section>'
    lead = ''.join(slots.values())   # a slot whose group is not on this page is kept at the top, so nothing is lost
    infos = ''.join(_info_layer(group) for group in groups if group.get('info') and rows.get(group['key']))
    plate = ''
    if genders:
        plate = ('<div class="gender-plate" role="group" aria-label="Watch collection" data-pick=""><i class="gp-thumb" aria-hidden="true"></i>' + ''.join(
            f'<button type="button" data-gender="{esc(g[0])}" aria-pressed="false"><span class="gp-l">{esc(g[1])}</span>'
            f'<small class="gp-c">{g[2]} {"watch" if g[2] == 1 else "watches"}</small></button>' for g in genders) + '</div>')
    top_html = top_html.replace('<!--segments-->', plate)
    controls = ('<div class="collection-controls" data-controls hidden>'
                f'<label class="collection-search"><span class="visually-hidden">Search {esc(plural)}</span><input type="search" data-search placeholder="Search {esc(plural)}" autocomplete="off"></label>'
                f'<button type="button" class="btn btn-outline btn-small collection-filter-open" data-filter-open aria-haspopup="dialog" aria-controls="{esc(uid)}-filters">'
                '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg><span class="fo-l">Filter</span> <span class="fo-n" data-filter-badge></span></button>'
                '<label class="collection-sort"><span>Sort</span> <select data-sort aria-label="Sort"><option value="featured">Featured</option><option value="name">Name A\u2013Z</option><option value="name-desc">Name Z\u2013A</option></select></label></div>')
    head = (f'<header class="collection-head sel-head"><div class="sel-t"><h2 id="{esc(uid)}-title">{esc(title)}</h2>'
            f'<p data-collection-count role="status">{shown} {esc(noun if shown == 1 else plural)}</p></div>{controls}</header>')
    active = '<div class="collection-active" data-active hidden></div>'
    panel = (f'<dialog class="collection-filters" id="{esc(uid)}-filters" aria-labelledby="{esc(uid)}-filter-title" data-filter-panel{f" data-sizes={chr(39)}{esc(sizes_json)}{chr(39)}" if sizes_json else ""}>'
             '<div class="cf-head" data-cf-head><i class="cf-grab" aria-hidden="true"></i>'
             f'<div class="cf-ht"><strong id="{esc(uid)}-filter-title">{esc(panel_title)}</strong><span class="cf-count" data-cf-count>{shown} {"match" if shown == 1 else "matches"}</span></div>'
             '<button type="button" class="linklike cf-reset" data-filter-clear>Reset all</button><button type="button" class="cf-x" data-filter-close aria-label="Close filters">\u2715</button></div>'
             '<div class="cf-body" data-cf-body tabindex="-1"><div class="cf-active" data-cf-active hidden></div><div class="cf-quick" data-cf-quick hidden></div><div class="cf-zero" data-cf-zero hidden></div>'
             + panel_top + lead + body + '</div>'
             f'<div class="cf-foot" data-cf-foot><button type="button" class="btn btn-primary btn-small cf-cta" data-filter-close data-apply-label>Show {shown} {esc(plural if shown != 1 else noun)}</button>'
             '<button type="button" class="btn btn-outline btn-small cf-undo" data-cf-undo hidden>Clear one filter</button></div>'
             + infos + '</dialog>')
    rest_html = ('<div class="watch-grid" data-collection-grid>' + card_html + '</div>'
                 f'<div class="collection-empty" data-empty {"hidden" if shown else ""}><h3>No matching {esc(plural)}</h3><p>Try another search or remove a filter.</p><button type="button" class="btn btn-outline" data-filter-clear>Clear filters</button></div>'
                 '<nav class="collection-pagination" data-pagination aria-label="Product pages" hidden></nav>')
    prem_attr = ' data-premium="' + esc(premium_json) + '"' if premium_json else ''
    opening = (f'<section class="collection" id="{esc(uid)}" data-collection data-noun="{esc(noun)}" data-plural="{esc(plural)}" data-preset-gender="{esc(preset_gender)}" data-preset-from="{esc(preset_from)}"{prem_attr} data-page-size="{page_size}" '
               f'data-top-filters data-store aria-labelledby="{esc(uid)}-title">')
    return (opening + top_html + '<div class="collection-layout">' + panel + '<div class="collection-main">' + head + active + grid_note + rest_html + '</div></div>' + after_html + '</section>')


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
