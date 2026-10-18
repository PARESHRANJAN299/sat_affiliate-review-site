"""Reusable card renderers for the Watches pages: the one place card HTML is written.

Every card is built from normalized data (see Watches.published_collections(), active_brands(), intent_cards()), never typed out where it is used.
Three levels give the page its hierarchy:

    primary    budget collections, curated collections, featured guides (largest, strongest border, art)
    secondary  brands and shopper intents (medium)
    compact    chips, quick links and menu rows (smallest)

One card is one link. A collection is always named by its canonical display_title, so the menu, the hub, the popular block and the related
links can never disagree; the short_label is for compact chips only.
"""
import html


def esc(value):
    return html.escape(str(value), quote=True)


def watches_text(count):
    return f'{count} {"watch" if count == 1 else "watches"}'


def collection_card(c, level="primary", cta="Explore", art=""):
    """A collection (a published, indexable page): title, live count, one descriptive sentence and an arrow. c is a normalized collection."""
    art_html = f'<span class="card-art" aria-hidden="true">{art}</span>' if art else ""
    return (f'<a class="card card-{level} col-card" href="{esc(c["href"])}"><strong class="card-title">{esc(c.get("heading") or c["display_title"])}</strong>'
            f'<span class="card-count">{watches_text(c["count"])}</span><small class="card-sub">{esc(c["description"])}</small>'
            f'<span class="card-go">{esc(cta)} <i aria-hidden="true">&rarr;</i></span>{art_html}</a>')


AFFILIATE_ATTRS = 'target="_blank" rel="sponsored nofollow noopener" data-no-paid-label="1"'


def hero_link(aff):
    """The whole hero background opens the owner's Amazon link in a new tab (the Men and Women buttons sit above it and keep working)."""
    label = esc(aff["label"]) + " (paid link)"
    return f'<a class="lx-hero-link" href="{esc(aff["url"])}" {AFFILIATE_ATTRS} aria-label="{label}" title="{label}"></a>'


def budget_card(t, art="", aff=None):
    """A shopper price tier (see Watches.budget_discovery): eyebrow, amount, live count, participating brands, art. One link per card. With the owner's Amazon
    link set, the card opens it in a new tab and does nothing on the page itself (no scrolling, no filter); a tier whose own SEO page is published still opens
    that page. The accessible name is the visible text plus the full heading, and says when the card opens Amazon."""
    redirect = bool(aff) and not t.get("has_page")
    href, attrs = (aff["url"], " " + AFFILIATE_ATTRS) if redirect else (t["href"], "")
    note = f'<span class="visually-hidden"> (opens an Amazon search for {esc(aff.get("search") or "watches")}, paid link)</span>' if redirect else ""
    return (f'<a class="card card-primary lx-budget tier-{t["tier"]}" href="{esc(href)}"{attrs}><span class="b-under">{esc(t["eyebrow"])}</span>'
            f'<strong>{esc(t["amount"])}</strong><span class="b-cap">{watches_text(t["count"])}</span><span class="b-brand">{esc(t["brand_line"].upper())}</span>'
            f'<span class="card-go">Explore watches <i aria-hidden="true">&rarr;</i></span><span class="visually-hidden">: {esc(t.get("heading") or t["display_title"])}</span>{note}'
            f'<span class="b-art" aria-hidden="true">{art}</span></a>')


def brand_card(slug, name, count):
    return (f'<a class="card card-secondary lx-brandtile" href="/watches/brands/{esc(slug)}/" data-brand-tile="{esc(slug)}" aria-current="false">'
            f'<strong>{esc(name.upper())}</strong><small>{watches_text(count)}</small></a>')


def intent_card(title, text, href, intent, icon):
    return (f'<a class="card card-secondary lx-intent" href="{esc(href)}" data-intent="{esc(intent)}"><span class="lx-i-ico" aria-hidden="true">{icon}</span>'
            f'<span class="lx-i-t"><strong>{esc(title)}</strong><small>{esc(text)}</small><span class="lx-i-go">Explore <i aria-hidden="true">&rarr;</i></span></span></a>')


def feature_card(kicker, title, text, href, cta, art=""):
    """A featured destination that is not a collection (the buying guide, Find your fit)."""
    art_html = f'<span class="lx-mart" aria-hidden="true">{art}</span>' if art else ""
    return (f'<a class="card card-primary lx-mcard lx-mlink" href="{esc(href)}"><p class="lx-mk">{esc(kicker)}</p><h3>{esc(title)}</h3><p>{esc(text)}</p>'
            f'<span class="lx-mcta">{esc(cta)} <i aria-hidden="true">&rarr;</i></span>{art_html}</a>')


def quick_link(text, href, count=None):
    """A compact link such as a count chip in the menu."""
    n = f'<em>{count}</em>' if count is not None else ""
    return f'<a class="card card-compact" href="{esc(href)}"><span>{esc(text)}</span>{n}</a>'


def menu_row(c):
    """A collection as a compact row in the category menu."""
    if c.get("kind"):   # a price tier states its live count and its leading brands
        names = c.get("brands", [])
        sub = watches_text(c["count"]) + (" \u00b7 " + ", ".join(names[:2]) + (f" +{len(names) - 2}" if len(names) > 2 else "") if names else "")
    else:
        sub = c["description"]
    return (f'<a class="card card-compact mega-card" href="{esc(c["href"])}"><strong>{esc(c["display_title"])}</strong><small>{esc(sub)}</small>'
            '<span class="mega-go">Explore <i aria-hidden="true">&rarr;</i></span></a>')
