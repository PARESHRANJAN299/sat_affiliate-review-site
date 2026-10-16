"""Shared product-first collection block used by the Watches page and by the category pages.

The caller renders each product card (it carries data-brand, data-gender and one data-<group> attribute per filter group).
This module builds the header, the Men's/Women's switch, the sort box, the filter panel and the grid wrapper. Filtering, sorting and the
phone bottom sheet run in src/js/components/watch-collection.js; without JavaScript the preset products stay visible.
"""
import html


def esc(value):
    return html.escape(str(value), quote=True)


def render(cards, groups, *, default_title, noun="product", plural="products", preset_gender="", preset_brand="", genders=None,
           reset_label="", see_all_html="", note_html="", sort_options=None):
    """cards: [(card_html, visible_by_default)]; groups: [{"key","title","items":[(value,label,count)],"checked":[values]}];
    genders: [(slug,label)] for the switch, or None."""
    sort_options = sort_options or [("featured", "Featured"), ("name", "Name A to Z")]
    body = []
    for card, visible in cards:
        body.append(card if visible else card.replace("<article ", "<article hidden ", 1))
    panel = ""
    for g in groups:
        boxes = "".join(
            f'<label class="fopt"><input type="checkbox" data-group="{esc(g["key"])}" value="{esc(v)}" data-label="{esc(label)}"'
            f'{" checked" if v in g.get("checked", ()) else ""}> <span>{esc(label)}</span> <em>{n}</em></label>'
            for v, label, n in g["items"])
        panel += f'<fieldset class="fgroup"><legend>{esc(g["title"])}</legend>{boxes}</fieldset>'
    seg = ""
    if genders:
        btns = "".join(
            f'<button type="button" class="seg-btn" data-gender="{esc(s)}" aria-pressed="{"true" if s == preset_gender else "false"}">{esc(l)}</button>'
            for s, l in genders)
        seg = f'<div class="seg" role="group" aria-label="Show" data-seg hidden>{btns}</div>'
    reset = f'<button type="button" class="linklike" data-reset hidden>{esc(reset_label)}</button>' if reset_label else ""
    sorts = "".join(f'<option value="{esc(v)}">{esc(l)}</option>' for v, l in sort_options)
    return (
        f'<div class="collection" data-collection data-default-title="{esc(default_title)}" data-preset-gender="{esc(preset_gender)}" '
        f'data-preset-brand="{esc(preset_brand)}" data-noun="{esc(noun)}" data-plural="{esc(plural)}">\n'
        '  <div class="collection-head">\n'
        f'    <div><h2 data-collection-title>{esc(default_title)}</h2><p class="collection-sub" data-collection-count aria-live="polite"></p></div>\n'
        f'    {seg}\n  </div>\n'
        '  <div class="collection-bar" data-collection-bar hidden>\n'
        '    <button type="button" class="btn btn-outline btn-small collection-filter-open" data-filter-open aria-controls="collection-filters" aria-expanded="false">Filters <span data-filter-badge></span></button>\n'
        f'    <label class="collection-sort">Sort <select data-sort>{sorts}</select></label>\n'
        f'    {reset}\n  </div>\n'
        '  <div class="collection-layout">\n'
        '    <aside class="collection-filters" id="collection-filters" data-filter-panel aria-label="Filters" hidden>\n'
        '      <div class="cf-head"><strong>Filters</strong><button type="button" class="sheet-close" data-filter-close>Close</button></div>\n'
        f'      {panel}\n'
        '      <div class="cf-foot"><button type="button" class="btn btn-outline btn-small" data-filter-clear>Clear all</button>'
        f'<button type="button" class="btn btn-primary btn-small" data-filter-close>Show {esc(plural)}</button></div>\n'
        '    </aside>\n'
        '    <div class="collection-main">\n'
        '      <div class="watch-grid" data-watch-grid>\n' + "\n".join(body) + '\n      </div>\n'
        f'      <p class="empty-filter" data-filter-empty hidden>No {esc(plural)} match these filters. <button type="button" class="linklike" data-filter-clear>Clear filters</button></p>\n'
        f'      <div class="collection-foot">{see_all_html}</div>\n'
        f'      {note_html}\n'
        '    </div>\n  </div>\n</div>\n<div class="filter-scrim" data-filter-scrim hidden></div>')
