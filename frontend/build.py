#!/usr/bin/env python3
"""Static site builder.

Reads the split source in src/, bundles and minifies CSS/JS once per page,
renders every page through the shared template, and writes the deployable
site to dist/ (HTML, sitemap.xml, robots.txt, _headers, assets/).

Usage:
    python3 build.py            build into dist/
    python3 build.py --serve    build, then serve dist/ at http://localhost:8000

Standard library only.
"""
import datetime
import urllib.parse
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import watches  # noqa: E402
SRC = ROOT / "src"
DIST = ROOT / "dist"

CONFIG = json.loads((SRC / "site.config.json").read_text(encoding="utf-8"))
CATEGORIES = json.loads((SRC / "categories.json").read_text(encoding="utf-8"))["categories"]
CONFIG["categories"] = [{"label": c["name"], "url": c["url"], "slug": c["slug"]} for c in CATEGORIES]

# Included in every page's CSS/JS bundle, in this order.
ALWAYS_CSS = [
    "base/variables", "base/reset",
    "base/icons", "layout/container", "layout/section", "layout/header", "layout/footer", "layout/search", "layout/to-top",
]
# Loaded after component/page CSS so they win the cascade.
LAST_CSS = ["base/accessibility", "base/print"]
ALWAYS_JS = ["core/main", "core/menu", "core/search-lite", "core/to-top"]

TITLE_MAX = 60
DESCRIPTION_MAX = 160

warnings = []
errors = []


# ---------- helpers ----------

def read(path):
    return Path(path).read_text(encoding="utf-8")


def render(template, ctx):
    """Replace {{name}} placeholders; unknown names are a build error."""
    def sub(m):
        key = m.group(1)
        if key not in ctx:
            errors.append(f"unknown placeholder {{{{{key}}}}}")
            return m.group(0)
        return str(ctx[key])
    return re.sub(r"\{\{(\w+)\}\}", sub, template)


def esc(value):
    return html.escape(value, quote=True)


def logo_html(text):
    """Animated wordmark: one span per letter (styled in layout/header.css)."""
    letters = "".join(f'<span style="--i:{i}">{esc(c)}</span>' for i, c in enumerate(text))
    return f'<span class="logo-mark" aria-hidden="true">{letters}</span>'


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


TAG_HUE = {"Badminton": 215, "Yoga": 160, "Home gym": 22, "Fitness": 340, "Running": 195, "Cricket": 135, "Recovery": 280}
TAG_ART = {
    "Badminton": '<ellipse cx="38" cy="24" rx="13" ry="18" transform="rotate(35 38 24)"/><path d="M29 38 L11 56M33 18 L45 30M28 26 L40 36"/>',
    "Yoga": '<circle cx="20" cy="40" r="12"/><circle cx="20" cy="40" r="5"/><path d="M20 28 H54 V52 H20"/>',
    "Home gym": '<rect x="5" y="24" width="8" height="16" rx="2"/><rect x="13" y="19" width="7" height="26" rx="2"/><path d="M20 32 H44"/><rect x="44" y="19" width="7" height="26" rx="2"/><rect x="51" y="24" width="8" height="16" rx="2"/>',
    "Fitness": '<rect x="7" y="42" width="7" height="16" rx="3"/><rect x="50" y="42" width="7" height="16" rx="3"/><path d="M10 42 C10 6 54 6 54 42"/>',
    "Running": '<path d="M6 42 V30 Q20 30 27 21 L35 27 Q46 29 58 38 V47 H6 Z"/><path d="M6 47 H58M30 33 L36 38M36 30 L42 35"/>',
    "Cricket": '<rect x="24" y="6" width="15" height="34" rx="3" transform="rotate(28 31 23)"/><path d="M37 42 L52 58"/><circle cx="14" cy="50" r="5"/>',
    "Recovery": '<ellipse cx="13" cy="32" rx="6" ry="13"/><path d="M13 19 H51 M13 45 H51"/><ellipse cx="51" cy="32" rx="6" ry="13"/>',
}
DEFAULT_ART = '<circle cx="32" cy="32" r="18"/><path d="M32 18 V46 M18 32 H46"/>'


def tag_art(tag):
    hue = TAG_HUE.get(tag, 215)
    shape = TAG_ART.get(tag, DEFAULT_ART)
    return (f'<div class="article-art" style="--hue:{hue}" aria-hidden="true">'
            f'<svg viewBox="0 0 64 64" focusable="false">{shape}</svg></div>')


def article_cards(articles):
    featured = len(articles) == 1
    cards = []
    for a in articles:
        info = a["article"]
        search = esc(f'{a["title"]} {info["tag"]} {info["category"]} {info["summary"]}'.lower())
        art = "        " + tag_art(info["tag"]) + "\n"
        cards.append(
            f'      <div class="article-card" data-search="{search}">\n' + art +
            '        <div class="article-body">\n'
            f'          <span class="tag">{esc(info["tag"])}</span>\n'
            f'          <h3>{esc(a["title"])}</h3>\n'
            f'          <p>{esc(info["summary"])}</p>\n'
            f'          <a href="{a["url"]}" class="read-link">Read the guide<span class="visually-hidden">: {esc(a["title"])}</span> <svg class="ic" aria-hidden="true"><use href="#i-arrow"/></svg></a>\n'
            '        </div>\n'
            '      </div>')
    cls = "article-grid is-featured" if featured else "article-grid"
    return f'    <div class="{cls}">\n' + "\n".join(cards) + "\n    </div>"


def category_sections(articles):
    """Home page: one section per enabled category that has articles."""
    out = []
    for cat in CONFIG.get("categories", []):
        if cat.get("enabled") is False:
            continue
        items = sorted([a for a in articles if a["article"]["category"] == cat["label"]],
                       key=lambda a: not a.get("featured"))
        if not items:
            continue
        out.append(
            '<section class="section">\n  <div class="container">\n'
            f'    <div class="section-head"><h2>{esc(cat["label"])}</h2>'
            f'<a class="see-all" href="{cat["url"]}">See all {esc(cat["label"])} guides \u2192</a></div>\n'
            + article_cards(items[:6]) + '\n  </div>\n</section>')
    return "\n\n".join(out)


def slugify_heading(text, seen):
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"
    slug, n = base, 2
    while slug in seen:
        slug, n = f"{base}-{n}", n + 1
    seen.add(slug)
    return slug


def decorate(content):
    """Give h2 headings and ranked product h3 headings ids; return (content, table-of-contents html)."""
    seen = set(re.findall(r'\sid="([^"]+)"', content))
    entries = []

    def add_ids(m):
        if m.group(0).startswith("<h2"):
            if 'data-toc="skip"' in m.group(1):
                return m.group(0)
            level, attrs, inner, prefix = 1, m.group(1), m.group(2), ""
        else:
            level, attrs, inner, prefix = 2, "", m.group(4), m.group(3)
        text = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        slug = slugify_heading(text, seen)
        entries.append((level, text, slug))
        tag = "h2" if level == 1 else "h3"
        return f'{prefix}<{tag}{attrs} id="{slug}">{inner}</{tag}>'

    # one pass over both patterns keeps the table of contents in document order
    pattern = re.compile(r'<h2([^>]*)>(.*?)</h2>|(<span class="rank">.*?</span>\s*)<h3>(.*?)</h3>', re.S)
    content = pattern.sub(add_ids, content)

    items, i = [], 0
    while i < len(entries):
        _, text, slug = entries[i]
        kids, j = [], i + 1
        while j < len(entries) and entries[j][0] == 2:
            kids.append(f'<li><a href="#{entries[j][2]}">{esc(entries[j][1])}</a></li>')
            j += 1
        sub = "<ol>" + "".join(kids) + "</ol>" if kids else ""
        items.append(f'<li><a href="#{slug}">{esc(text)}</a>{sub}</li>')
        i = j
    toc = ('<nav class="toc-col" aria-label="On this page"><details class="toc" open><summary>On this page</summary>'
           "<ol>" + "".join(items) + "</ol></details></nav>") if entries else ""
    return content, toc


def share_html(canonical, title):
    text = urllib.parse.quote(f"{title} {canonical}")
    return ('<div class="share"><span class="share-label">Share this guide:</span>'
            f'<a class="btn btn-outline btn-small" href="https://wa.me/?text={text}" target="_blank" rel="noopener noreferrer">WhatsApp</a>'
            '<button type="button" class="btn btn-outline btn-small" data-share hidden>Copy link</button>'
            '<span class="visually-hidden" role="status" aria-live="polite" data-share-status></span></div>')


CATEGORY_ICON = {
    "watches": '<circle cx="12" cy="12" r="5.5"/><path d="M12 9.5V12l1.6 1.4"/><path d="M9 6.6 9.6 2.8h4.8L15 6.6M9 17.4l.6 3.8h4.8l.6-3.8"/>',
    "sports": '<path d="M6.5 6.5v11M17.5 6.5v11M3.5 9v6M20.5 9v6M6.5 12h11"/>',
    "beauty": '<rect x="7" y="13" width="10" height="8" rx="1.5"/><path d="M9 13V8.5L14.5 4v9"/><path d="M18 5.5l1.6-1.6M19.5 9H22"/>',
    "home": '<path d="M4 11h16v6a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3z"/><path d="M2 11h2M20 11h2"/><path d="M7.5 11a4.5 4.5 0 0 1 9 0"/><path d="M12 4.5v2"/>',
    "clothing": '<path d="M8.5 3 3 5.5 4.6 10H7.5v10.5h9V10h2.9L21 5.5 15.5 3a3.6 3.6 0 0 1-7 0z"/>',
}


CATEGORY_ICON.update({
    "skin-care": '<path d="M10 3h4v4h-4zM9 7h6v3H9zM8.5 10h7l-.7 10a1 1 0 0 1-1 1h-3.6a1 1 0 0 1-1-1z"/>',
    "hair-care": '<rect x="3" y="6" width="18" height="5.5" rx="1.5"/><path d="M6 11.5v7M9 11.5v7M12 11.5v7M15 11.5v7M18 11.5v7"/>',
    "makeup": '<rect x="7" y="13" width="10" height="8" rx="1.5"/><path d="M9 13V8.5L14.5 4v9"/><path d="M18 5.5l1.6-1.6M19.5 9H22"/>',
    "mens-grooming": '<rect x="4" y="3.5" width="16" height="5.5" rx="1.5"/><path d="M12 9v12M10 21h4M8 6.2h8"/>',
    "bath-body": '<circle cx="9" cy="13.5" r="5.5"/><circle cx="17.5" cy="7.5" r="3"/><circle cx="18.5" cy="17" r="2"/>',
    "sun-care": '<circle cx="12" cy="12" r="4"/><path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1"/>',
    "badminton-rackets": '<ellipse cx="14.5" cy="9.5" rx="5" ry="6.5" transform="rotate(-35 14.5 9.5)"/><path d="M10.6 13.4 4 20M12 6.5l5 5M9.8 9.2l5 5"/>',
    "cricket-bats": '<rect x="11" y="2.5" width="5" height="12.5" rx="1.5" transform="rotate(35 13.5 8.7)"/><path d="M10.5 14.5 5 20"/><circle cx="18.5" cy="18.5" r="2"/>',
    "footballs": '<circle cx="12" cy="12" r="9"/><path d="M12 8.2l3.4 2.4-1.3 4H9.9l-1.3-4z"/><path d="M12 8.2V3M15.4 10.6l4.8-1.6M14.1 14.6l3 4M9.9 14.6l-3 4M8.6 10.6 3.8 9"/>',
    "sports-shoes": '<path d="M3 17v-4.5c2.8 0 4.8-1.8 6-4l3 1.8c2.2 1.3 5 2.4 9 4.2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 17.5h18M12 10l1.6 2.2"/>',
    "sports-bags": '<rect x="3" y="8" width="18" height="11" rx="3"/><path d="M8 8V6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18M12 12v2"/>',
    "dumbbells": '<path d="M6.5 6.5v11M17.5 6.5v11M3.5 9v6M20.5 9v6M6.5 12h11"/>',
    "resistance-bands": '<ellipse cx="9" cy="12" rx="6" ry="3.5" transform="rotate(-20 9 12)"/><ellipse cx="15" cy="12" rx="6" ry="3.5" transform="rotate(20 15 12)"/>',
    "yoga-mats": '<circle cx="7.5" cy="14" r="3.5"/><circle cx="7.5" cy="14" r="1"/><path d="M7.5 10.5H20v7H7.5"/>',
    "skipping-ropes": '<rect x="3" y="3" width="3.5" height="7" rx="1.7"/><rect x="17.5" y="14" width="3.5" height="7" rx="1.7"/><path d="M4.7 10C4.7 20 12 22 12 12S19.3 4 19.3 14"/>',
    "gym-gloves": '<path d="M7 11V6a1.5 1.5 0 0 1 3 0v4M10 10V4.5a1.5 1.5 0 0 1 3 0V10M13 10V5.5a1.5 1.5 0 0 1 3 0V12"/><path d="M7 11c-1.6-1-3.2.6-2.1 2.2L8 18c1.4 2.4 3.4 3 6 3 3 0 5-2 5-5v-3.5a1.5 1.5 0 0 0-3 0"/>',
    "hand-grippers": '<path d="M7 20c-3-3-3.5-9 1-13l3 2.2M17 20c3-3 3.5-9-1-13l-3 2.2"/><path d="M9.5 5.5h5M8 20h2M14 20h2"/>',
    "foam-rollers": '<rect x="3" y="8" width="18" height="8" rx="4"/><path d="M8 8v8M12 8v8M16 8v8"/>',
    "shaker-bottles": '<path d="M8 3h8v3H8zM9 6l-1 14a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1L15 6"/><path d="M9 11h6"/>',
    "weighing-scales": '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="M8 9.5a4 4 0 0 1 8 0z"/><path d="M12 9.5l1.6-2.2"/>',
    "gen-z-tops": '<path d="M8 4 3 7l1.5 4H8v4h8v-4h3.5L21 7l-5-3a4 4 0 0 1-8 0z"/>',
    "kurtas-kurti-sets": '<path d="M8 3h6l2 3 2 2-1.5 2.5-1.5-.7V15H7v-4.2l-1.5.7L4 8l2-2z"/><path d="M8 15l-1 6M14 15l1 6"/>',
    "home-wear": '<path d="M6 4h12l1 5H5z"/><path d="M5 9l1 11h4l2-7 2 7h4l1-11"/>',
    "night-dresses": '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/>',
    "casual-dresses": '<path d="M9 3h6l-1 6 4 12H6l4-12z"/><path d="M9.5 9h5"/>',
    "jeans-trousers": '<path d="M7 3h10l1 18h-5l-1-9-1 9H6z"/><path d="M7 7h10"/>',
    "coord-sets": '<path d="M8 3h8l1.5 6h-11z"/><path d="M6.5 12h11l2 9h-15z"/>',
    "leggings": '<path d="M8 3h8l1 8-2 10h-3l-1-8-1 8H7L5 11z"/>',
    "t-shirts": '<path d="M8.5 3 3 5.5 4.6 10H7.5v10.5h9V10h2.9L21 5.5 15.5 3a3.6 3.6 0 0 1-7 0z"/>',
    "shirts": '<path d="M9 3 3 6l1.5 4H7v10.5h10V10h2.5L21 6l-6-3-3 3z"/><path d="M12 6v14"/>',
    "jeans": '<path d="M7 3h10l1 18h-5l-1-9-1 9H6z"/><path d="M7 7h10M9 9.5c1 1 2 1 3 0"/>',
    "trousers": '<path d="M7 3h10l1 18h-4.5L12 10l-1.5 11H6z"/>',
    "shorts": '<path d="M6 5h12l1.5 12h-5.5l-2-6-2 6H4.5z"/>',
    "joggers": '<path d="M7 3h10l1 4 1 10-3 4h-2l-1-9-1 9H9l-3-4 1-10z"/><path d="M7 7h10"/>',
    "hoodies-sweatshirts": '<path d="M9 4c0 3 6 3 6 0l4 3 2 7-3 1-1-3v9H7v-9l-1 3-3-1 2-7z"/><path d="M12 8v4"/>',
    "kurtas": '<path d="M9 3h6l2 3 3 3-2 3-2-1v10H8V11l-2 1-2-3 3-3z"/><path d="M12 3v7"/>',
    "innerwear": '<path d="M5 5h14v5c0 3-3 5-7 9-4-4-7-6-7-9z"/>',
    "nightwear": '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5z"/><path d="M17 3v3M15.5 4.5h3"/>',
    "jackets": '<path d="M9 3 4 6l-1 14h5V9M15 3l5 3 1 14h-5V9"/><path d="M9 3l3 3 3-3M12 6v14"/>',
    "pressure-cookers": '<path d="M5 10h14v9a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2z"/><path d="M4 10h16M9 10V7h6v3M12 7V4M3 14h2M19 14h2"/>',
    "mixer-grinders": '<path d="M8 3h8l-1 10H9z"/><rect x="6" y="13" width="12" height="8" rx="2"/><path d="M12 16.5v1"/>',
    "cookware-sets": '<rect x="3" y="11" width="12" height="9" rx="2"/><path d="M15 14h4a2 2 0 0 1 0 4h-4M5 8h8M7 8V6h4v2"/>',
    "air-fryers": '<rect x="5" y="3" width="14" height="18" rx="4"/><circle cx="12" cy="13.5" r="4"/><path d="M8.5 7h7"/>',
    "electric-kettles": '<path d="M6 8h10l1 12H5z"/><path d="M16 11h2a2 2 0 0 1 0 4h-1M6 8l3-4h4l3 4"/>',
    "storage-containers": '<rect x="4" y="9" width="16" height="11" rx="2"/><path d="M5 9V6h14v3M10 14h4"/>',
    "lunch-boxes": '<rect x="3" y="9" width="18" height="10" rx="2"/><path d="M7 9V6h10v3M9 14h6"/>',
    "kitchen-organizers": '<path d="M4 3v18M20 3v18M4 21h16M4 12h16"/><rect x="7" y="6" width="3" height="6"/><rect x="13" y="8" width="4" height="4"/><rect x="8" y="15" width="8" height="6"/>',
    "tawas-frying-pans": '<circle cx="10" cy="12" r="6"/><path d="M16 12h6"/>',
    "cleaning-tools": '<path d="M12 3v11M7 14h10l1 7H6z"/>',
    "storage-organizers": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 12h16M10 8h4M10 16h4"/>',
    "bathroom-accessories": '<path d="M5 21V6a3 3 0 0 1 3-3h4"/><path d="M12 3a5 5 0 0 1 5 5H9a5 5 0 0 1 3-5zM10 12v2M13 12v3M16 12v2"/>',
    "bedsheets-bedding": '<path d="M3 19V7M3 15h18v4M21 15v-3a3 3 0 0 0-3-3h-7v6"/><circle cx="7" cy="11" r="2"/>',
    "pillows-cushions": '<path d="M4 8c4-2 12-2 16 0-1.5 2.5-1.5 5.5 0 8-4 2-12 2-16 0 1.5-2.5 1.5-5.5 0-8z"/>',
    "floor-mats": '<rect x="3" y="8" width="18" height="9" rx="1.5"/><path d="M6 8v9M9 8v9M12 8v9M15 8v9M18 8v9"/>',
    "mosquito-insect-protection": '<ellipse cx="12" cy="13" rx="4" ry="6"/><path d="M12 7V4M8 11 4 9M16 11l4-2M8 15l-4 2M16 15l4 2"/>',
    "kettlebells": '<circle cx="12" cy="15" r="6"/><path d="M8.2 10.4C7 4 17 4 15.8 10.4"/>',
})


def category_icon(c, css_class):
    return (f'<svg class="{css_class}" viewBox="0 0 24 24" focusable="false" aria-hidden="true">'
            f'{CATEGORY_ICON[c["art"]]}</svg>')


def category_art(c):
    if c.get("image"):
        return f'<img src="{esc(c["image"])}" alt="" loading="lazy" width="480" height="360">'
    return category_icon(c, "cat-svg")


def category_cards(current_url=None):
    """Large visual cards for the top-level categories (Shop by Category)."""
    items = []
    for c in CATEGORIES:
        items.append(
            f'      <li><a class="category-card" href="{c["url"]}" style="--hue:{c["hue"]}">'
            f'<span class="category-art" aria-hidden="true">{category_art(c)}</span>'
            f'<span class="category-body"><span class="category-name">{esc(c["name"])}</span>'
            f'<span class="category-desc">{esc(c["description"])}</span>'
            '<span class="category-cta">Explore <svg class="ic" aria-hidden="true"><use href="#i-arrow"/></svg></span></span></a></li>')
    return '<ul class="category-grid">\n' + "\n".join(items) + "\n    </ul>"


def category_directory(entries=None, grid_id="category-results"):
    """Accessible category directory, generated from the shared category catalogue (or any list of cards)."""
    items = []
    for c in (CATEGORIES if entries is None else entries):
        items.append(
            '<li class="directory-item">'
            f'<a class="directory-card directory-{esc(c["slug"])}" href="{esc(c["url"])}">'
            f'<div class="directory-art">{category_art(c)}</div>'
            f'<div class="directory-body"><h3>{esc(c["name"])}</h3>'
            f'<p>{esc(c["description"])}</p>'
            '<span class="directory-cta">Explore'
            '<svg class="ic" aria-hidden="true"><use href="#i-arrow"/></svg></span></div></a></li>')
    return f'<ul class="directory-grid" id="{grid_id}">' + "\n".join(items) + '</ul>'



def home_video():
    """Optional hero video: used only when src/static/videos/home-hero.mp4 exists (and home-hero.webm / home-hero.jpg if present)."""
    videos = SRC / "static" / "videos"
    mp4 = videos / "home-hero.mp4"
    if not mp4.exists():
        return ""
    sources = []
    if (videos / "home-hero.webm").exists():
        sources.append('<source src="/videos/home-hero.webm" type="video/webm">')
    sources.append('<source src="/videos/home-hero.mp4" type="video/mp4">')
    poster = ' poster="/videos/home-hero.jpg"' if (videos / "home-hero.jpg").exists() else ""
    return ('<video class="home-hero-video" autoplay muted loop playsinline preload="metadata"'
            f'{poster} aria-hidden="true" tabindex="-1">' + "".join(sources) + '</video>')


def home_collage():
    """Home hero background: drifting rows of lifestyle pictures from static/images/home (a video can sit under it)."""
    folder = SRC / "static" / "images" / "home"
    names = sorted(p.name for p in folder.glob("*.jpg")) if folder.exists() else []
    if not names:
        return ""
    rows = [names[k::3] for k in range(3)]
    out = []
    for n, row in enumerate(rows):
        if not row:
            continue
        # the row is written twice so the loop never shows a gap; the copy is hidden from assistive tech
        def tiles(copy):
            return "".join(
                f'<span class="tile"><img src="/images/home/{esc(name)}" alt="" width="320" height="400" '
                f'loading="{"eager" if (n == 0 and not copy) else "lazy"}" decoding="async"></span>'
                for name in row)
        out.append(f'<div class="home-row home-row-{n + 1}"><div class="home-track">{tiles(False)}'
                   f'<span class="home-dup" aria-hidden="true">{tiles(True)}</span></div></div>')
    return '<div class="home-collage">\n      ' + "\n      ".join(out) + "\n    </div>"


def family_url(cat, fam):
    if fam.get("section"):
        return f'{cat["url"]}{fam["section"]}/{fam["slug"]}/'
    return f'{cat["url"]}{fam["slug"]}/'


def family_entries(cat):
    """Family cards in the shape category_directory() expects."""
    sections = {s["slug"]: s for s in cat.get("sections", [])}
    out = []
    for f in cat["families"]:
        out.append({"slug": f["slug"], "name": f["name"], "description": f["description"], "art": f["slug"],
                    "hue": sections.get(f.get("section"), {}).get("hue", cat["hue"]), "image": f.get("image"),
                    "url": family_url(cat, f)})
    return out


PICK_SLOTS = ["Editor's picks", "Best overall", "Best value", "Best for beginners", "Best under budget"]


# ---------- retailers and product data (shared by every category that has product reviews) ----------

PRICE_BANDS = ["Under \u20b9500", "\u20b9500\u2013\u20b91,000", "\u20b91,000\u2013\u20b92,000", "Premium"]
PRICE_NOTE = "Prices may change. Check the retailer for the latest price."
RETAILER_ORDER = ["amazon", "flipkart", "brand_store", "other"]
RETAILER_LABEL = {"amazon": "Amazon", "flipkart": "Flipkart", "brand_store": "Brand website", "other": "Other retailer"}
SLOT_KEYS = {"Best overall": "best_overall", "Best budget pick": "best_budget", "Best value": "best_value",
             "Best for daily use": "best_daily", "Best premium pick": "best_premium", "Best for beginners": "best_beginner", "Best for small homes": "best_small_home",
             "Best for daily wear": "best_daily_wear", "Best for college": "best_college", "Best for office": "best_office",
             "Best for home": "best_home", "Best for night wear": "best_night"}


def load_products(cat_slug):
    folder = SRC / "products" / cat_slug
    items = []
    for p in sorted(folder.glob("*.json")) if folder.exists() else []:
        try:
            items.append(json.loads(read(p)))
        except ValueError as exc:
            errors.append(f"product file {p.name}: {exc}")
    return items


def product_buttons(p):
    """One button per retailer that has a link: Product > Amazon > Flipkart > Brand website > Other retailer.
    Plain links until affiliate_active is set; then rel=sponsored and a disclosure line are added."""
    active = bool(CONFIG.get("affiliate_active"))
    rel = "sponsored nofollow noopener" if active else "nofollow noopener"
    retailers = p.get("retailers") or {}
    out, have_amazon = [], False
    for k, key in enumerate(RETAILER_ORDER):
        url = (retailers.get(key) or {}).get("url", "")
        if not url:
            continue
        have_amazon = have_amazon or key == "amazon"
        verb = "View Product" if k == 0 or not out else ("See Options" if key != "brand_store" else "Visit brand website")
        label = f'{verb} \u00b7 {RETAILER_LABEL[key]}' if len(retailers) > 1 else verb
        cls = "btn-primary" if not out else "btn-outline"
        out.append(f'<a class="btn {cls} btn-small" href="{esc(url)}" target="_blank" rel="{rel}" '
                   f'aria-label="{esc(label)} for {esc(p["name"])} (opens in a new tab)">{esc(label)}</a>')
    if not out:
        if p.get("sample"):
            return ('<span class="btn btn-primary btn-small is-disabled" aria-disabled="true">View Product</span> '
                    '<span class="btn btn-outline btn-small is-disabled" aria-disabled="true">See Options</span> '
                    '<span class="btn btn-outline btn-small is-disabled" aria-disabled="true">Check Availability</span>'), ""
        return '<span class="no-store">Retailer link coming soon.</span>', ""
    note = ""
    if active:
        note = '<p class="cta-note"><strong>Affiliate links.</strong> We may earn a commission if you buy, at no extra cost to you.</p>'
        if CONFIG.get("amazon_associate_approved") and have_amazon:
            note += '<p class="cta-note">As an Amazon Associate I earn from qualifying purchases.</p>'
    return " ".join(out), note


def product_review_html(p):
    """The reusable review template. Every field is optional except name; missing fields are skipped."""
    def lst(items):
        return "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>" if items else ""
    def row(label, value):
        return f'<div><dt>{esc(label)}</dt><dd>{value}</dd></div>' if value else ""
    facts = "".join([
        row("Product type", esc(p.get("product_type", ""))),
        row("Category", esc(p.get("category", ""))),
        row("Material and build", esc(p.get("material", ""))),
        row("Fit", esc(p.get("fit", ""))),
        row("Size range", esc(p.get("size_range", ""))),
        row("Style", esc(p.get("style", ""))),
        row("Occasion", esc(p.get("occasion", ""))),
        row("Size or capacity", esc(p.get("size", ""))),
        row("Best for", esc(p.get("best_for", ""))),
        row("Skin, hair or use case", esc(p.get("suits", ""))),
        row("Price band", esc(p.get("price_band", ""))),
        row("Value for money", esc(p.get("value_for_money", ""))),
        row("Best use case", esc(p.get("best_use_case", ""))),
        row("Who should buy it", esc(p.get("who_should_buy", ""))),
        row("Who should avoid it", esc(p.get("avoid", ""))),
        row("Maintenance and cleaning", esc(p.get("maintenance", ""))),
        row("Care instructions", esc(p.get("care", "")))])
    buttons, note = product_buttons(p)
    sample = '<span class="sample-flag">Sample</span> ' if p.get("sample") else ""
    parts = [f'<article class="beauty-review" id="r-{esc(p["id"])}">',
             f'  <h3>{sample}{esc(p["name"])}</h3>']
    if p.get("brand"):
        parts.append(f'  <p class="review-brand">{esc(p["brand"])}</p>')
    parts.append(f'  <dl class="review-facts">{facts}</dl>')
    if p.get("features"):
        parts.append(f'  <h4>Main features</h4>{lst(p["features"])}')
    if p.get("key_ingredients"):
        parts.append(f'  <h4>Key ingredients</h4>{lst(p["key_ingredients"])}')
    parts.append('  <div class="pros-cons"><div class="pros"><h4>Pros</h4>' + lst(p.get("pros", [])) +
                 '</div><div class="cons"><h4>Cons</h4>' + lst(p.get("cons", [])) + '</div></div>')
    if p.get("how_to_choose"):
        parts.append(f'  <h4>How to choose</h4><p>{esc(p["how_to_choose"])}</p>')
    if p.get("alternatives"):
        parts.append(f'  <h4>Alternatives</h4>{lst(p["alternatives"])}')
    if p.get("final_recommendation"):
        parts.append(f'  <p class="verdict"><strong>Final recommendation:</strong> {esc(p["final_recommendation"])}</p>')
    parts.append(f'  <div class="cta-row">{buttons}</div>{note}')
    parts.append(f'  <p class="cta-note">{esc(PRICE_NOTE)}</p>')
    if p.get("sources") and not p.get("sample"):
        items = "".join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="nofollow noopener">{esc(s["label"])}</a></li>' for s in p["sources"])
        parts.append(f'  <details class="watch-sources"><summary>Pages we read</summary><ul>{items}</ul></details>')
    parts.append('</article>')
    return "\n".join(parts)


def product_table_html(products, caption):
    rows = []
    for p in products:
        buttons, _ = product_buttons(p)
        rows.append(
            f'<tr role="row"><th scope="row" role="rowheader">{esc(p["name"])}</th>'
            f'<td role="cell" data-label="Type">{esc(p.get("product_type", ""))}</td>'
            f'<td role="cell" data-label="Best for">{esc(p.get("best_for", ""))}</td>'
            f'<td role="cell" data-label="Price band">{esc(p.get("price_band", ""))}</td>'
            f'<td role="cell" data-label="Value">{esc(p.get("value_for_money", ""))}</td>'
            f'<td role="cell" data-label="Links">{buttons}</td></tr>')
    head = "".join(f'<th scope="col" role="columnheader">{h}</th>' for h in ["Product", "Type", "Best for", "Price band", "Value", "Links"])
    return ('<div class="compare-table-wrap"><table class="compare-table" role="table">'
            f'<caption class="visually-hidden">{esc(caption)}</caption><thead><tr role="row">{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def beauty_family_body(cat, f, products, sibling_cards):
    slots = f.get("slots") or cat.get("pick_slots", [])
    by_slot = {p.get("slot"): p for p in products if p.get("slot")}
    slot_html = []
    for label in slots:
        p = by_slot.get(SLOT_KEYS.get(label, ""))
        if p:
            slot_html.append(f'<li class="pick-slot is-filled"><span class="pick-slot-label">{esc(label)}</span>'
                             f'<a href="#r-{esc(p["id"])}"><strong>{esc(p["name"])}</strong></a></li>')
        else:
            slot_html.append(f'<li class="pick-slot"><span class="pick-slot-label">{esc(label)}</span>'
                             '<span class="pick-slot-state">Being researched</span></li>')
    needs = "".join(f'<li><strong>{esc(n["name"])}.</strong> {esc(n["text"])}</li>' for n in f.get("needs", []))
    tips = "".join(f'<li><strong>{esc(h)}.</strong> {esc(x)}</li>' for h, x in f["tips"])
    faqs = "".join(
        f'<details class="faq-item"><summary><h3>{esc(q["q"])}</h3><span class="faq-chev" aria-hidden="true"></span></summary><p>{esc(q["a"])}</p></details>'
        for q in f["faqs"])
    sec_names = {s["slug"]: s["name"] for s in cat.get("sections", [])}
    kicker = sec_names.get(f.get("section"), cat["name"])
    planned = ""
    if f.get("planned_guides"):
        items = "".join(f'<li><span>{esc(g["title"])}</span><span class="planned-tag">Planned</span></li>' for g in f["planned_guides"])
        planned = ('    <h2>Guides we plan to write</h2>\n    <p class="family-note">These are not written yet. Each one will use the same buying-guide template: picks, comparison, buying guide and FAQs.</p>\n'
                   f'    <ul class="planned-list">{items}</ul>\n')
    bands = "".join(f'<span class="band">{esc(b)}</span>' for b in cat.get("price_bands", PRICE_BANDS))
    if products:
        picks = ('<h2>Our picks</h2>\n<ul class="pick-slots">' + "".join(slot_html) + '</ul>\n'
                 '<h2>Comparison</h2>\n' + product_table_html(products, f["h1"]) + '\n'
                 '<h2>Reviews</h2>\n' + "\n".join(product_review_html(p) for p in products))
        status = '<p class="family-status"><strong>How we picked these:</strong> we read the maker\'s and the shops\' pages. We have not tested these products ourselves. Read <a href="/how-we-pick/">how we pick</a>.</p>'
    else:
        picks = ('<h2>Our picks</h2>\n<ul class="pick-slots">' + "".join(slot_html) + '</ul>\n'
                 '<h2>Comparison</h2>\n<div class="empty-state"><p>A comparison table appears here once the first picks are added.</p></div>')
        status = (f'<p class="family-status"><strong>{esc(cat.get("pending_note", "Picks coming soon."))}</strong> '
                  'We add a product only after we have read the maker\'s page and the shop listings. Read <a href="/how-we-pick/">how we pick</a>.</p>')
    affiliate = ('We have no approved affiliate accounts yet, and this page earns us nothing today. If that changes, we will say so here first.'
                 if not CONFIG.get("affiliate_active") else
                 'Some links on this page are affiliate links. We may earn a commission if you buy, at no extra cost to you.')
    return (
        '<section class="section">\n  <div class="container content-page family-page">\n'
        '    {{breadcrumb}}\n'
        f'    <p class="family-kicker">{esc(kicker)}</p>\n    <h1>{esc(f["h1"])}</h1>\n    <p class="lead">{esc(f["intro"])}</p>\n'
        f'    {status}\n'
        f'    <h2>Start with what you need</h2>\n    <ul class="family-tips">{needs}</ul>\n'
        f'    {picks}\n'
        f'    <h2>Buying guide</h2>\n    <ul class="family-tips">{tips}</ul>\n'
        f'    <p class="family-note">Typical price bands we use: <span class="band-list">{bands}</span> {esc(PRICE_NOTE)}</p>\n'
        f'    <h2>Common questions</h2>\n{faqs}\n'
        f'    <aside class="medical-note"><svg class="ic" aria-hidden="true"><use href="#i-info"/></svg><p>{esc(f["caution"])}</p></aside>\n'
        f'{planned}'
        f'    <h2>{esc(cat.get("more_label", "More guides"))}</h2>\n    <ul class="related-links">{sibling_cards}</ul>\n'
        f'    <aside class="affiliate-box" id="affiliate-note"><svg class="ic" aria-hidden="true"><use href="#i-info"/></svg>'
        f'<p><strong>Affiliate disclosure.</strong> {esc(affiliate)} <a href="/affiliate-disclosure/">Read the full disclosure</a>.</p></aside>\n'
        '  </div>\n</section>')


def beauty_pages(cat):
    entries = family_entries(cat)
    all_products = load_products(cat["slug"])
    min_index = 3
    pages = []
    sections = cat.get("sections", [])
    if sections:
        blocks = []
        for s in sections:
            sec_entries = [e for e, f in zip(entries, cat["families"]) if f.get("section") == s["slug"]]
            blocks.append(
                f'<section class="family-section family-section-{esc(s["slug"])}" id="{esc(s["slug"])}" aria-labelledby="{esc(s["slug"])}-title" style="--hue:{s["hue"]}">\n'
                f'  <div class="family-section-head"><h2 id="{esc(s["slug"])}-title">{esc(s["name"])}</h2>'
                f'<span class="family-count">{len(sec_entries)} product types</span></div>\n'
                f'  <p class="family-section-blurb">{esc(s["blurb"])}</p>\n  {category_directory(sec_entries, grid_id=s["slug"] + "-results")}\n</section>')
        cards_html = "\n".join(blocks)
    else:
        cards_html = f'<div class="family-cards family-cards-3">{category_directory(entries, grid_id="family-results")}</div>'
    body = (
        '<section class="section">\n  <div class="container content-page family-page">\n'
        '    {{breadcrumb}}\n'
        f'    <h1>{esc(cat["name"])}</h1>\n    <p class="lead">{esc(cat.get("tagline") or cat["description"])}</p>\n'
        f'    {cards_html}\n'
        f'    <p class="family-note">{esc(PRICE_NOTE)} This section is general information, not medical advice.</p>\n'
        '  </div>\n</section>')
    pages.append({
        "url": cat["url"], "title": f'{cat["name"]} Buying Guides for India',
        "description": cat.get("landing_meta") or f'{cat["name"]} buying guides for Indian shoppers.',
        "css": ["buttons", "breadcrumb", "content-page", "category-directory", "families"], "js": [],
        "breadcrumbs": [["Shop by Category", "/products/"], [cat["name"], cat["url"]]],
        "updated": "2026-10-16", "_slug": cat["slug"], "_body": body})
    for f in cat["families"]:
        url = family_url(cat, f)
        products = [p for p in all_products if p.get("family") == f["slug"]]
        sib = "".join(f'<li><a href="{esc(e["url"])}">{esc(e["name"])}</a></li>' for e, g in zip(entries, cat["families"]) if e["slug"] != f["slug"] and g.get("section") == f.get("section"))
        sib += f'<li><a href="{esc(cat["url"])}">All {esc(cat["name"])}</a></li>'
        pages.append({
            "url": url, "title": f["h1"], "description": f["meta"],
            "css": ["buttons", "breadcrumb", "content-page", "faq", "compare-table", "product-block", "watches", "families"], "js": [],
            "noindex": len(products) < min_index,
            "breadcrumbs": [["Shop by Category", "/products/"], [cat["name"], cat["url"]], [f["name"], url]],
            "updated": "2026-10-16", "_slug": f'{cat["slug"]}-{f["slug"]}',
            "_body": beauty_family_body(cat, f, products, sib)})
    sample_path = SRC / "products" / "_sample" / f'{cat["slug"]}-sample.json'
    sample = json.loads(read(sample_path)) if sample_path.exists() else None
    if sample:
        body = (
            '<section class="section">\n  <div class="container content-page family-page">\n'
            '    {{breadcrumb}}\n    <h1>Review template preview</h1>\n'
            '    <p class="lead">This page shows the review template with <strong>sample content</strong>. It is not a real product and nothing here is a recommendation.</p>\n'
            f'    {product_review_html(sample)}\n  </div>\n</section>')
        pages.append({
            "url": f'{cat["url"]}review-template/', "title": f'{cat["name"]} Review Template Preview',
            "description": "Sample content showing the review template. Not a real product.",
            "css": ["buttons", "breadcrumb", "content-page", "product-block", "watches", "families"], "js": [], "noindex": True,
            "breadcrumbs": [["Shop by Category", "/products/"], [cat["name"], cat["url"]], ["Review template", f'{cat["url"]}review-template/']],
            "updated": "2026-10-16", "_slug": f'{cat["slug"]}-review-template', "_body": body})
    return pages


def family_pages():
    """Landing page for each category that has product families, plus one page per family."""
    pages = []
    note_slots = "".join(
        f'<li class="pick-slot"><span class="pick-slot-label">{esc(s)}</span><span class="pick-slot-state">Being researched</span></li>'
        for s in PICK_SLOTS)
    for cat in CATEGORIES:
        if not cat.get("families"):
            continue
        if cat.get("template") in ("beauty", "reviews"):
            pages.extend(beauty_pages(cat))
            continue
        sections = cat.get("sections", [])
        entries = family_entries(cat)
        by_section = {s["slug"]: [e for e, f in zip(entries, cat["families"]) if f["section"] == s["slug"]] for s in sections}
        blocks = []
        for s in sections:
            cards = category_directory(by_section[s["slug"]], grid_id=f'{s["slug"]}-results')
            blocks.append(
                f'<section class="family-section family-section-{esc(s["slug"])}" id="{esc(s["slug"])}" aria-labelledby="{esc(s["slug"])}-title" style="--hue:{s["hue"]}">\n'
                f'  <div class="family-section-head"><h2 id="{esc(s["slug"])}-title">{esc(s["name"])}</h2>'
                f'<span class="family-count">{len(by_section[s["slug"]])} product types</span></div>\n'
                f'  <p class="family-section-blurb">{esc(s["blurb"])}</p>\n  {cards}\n</section>')
        body = (
            '<section class="section">\n  <div class="container content-page family-page">\n'
            '    {{breadcrumb}}\n'
            f'    <h1>{esc(cat["name"])}</h1>\n'
            f'    <p class="lead">{esc(cat.get("tagline") or cat["description"])}</p>\n'
            + "\n".join(blocks) +
            '\n  </div>\n</section>')
        pages.append({
            "url": cat["url"], "title": f'{cat["name"]} Buying Guides for India',
            "description": f'Browse sports and fitness product types, from {cat["families"][0]["name"].lower()} to {cat["families"][-1]["name"].lower()}. Buying guides for Indian shoppers.',
            "css": ["buttons", "breadcrumb", "content-page", "category-directory", "families"], "js": [],
            "breadcrumbs": [["Shop by Category", "/products/"], [cat["name"], cat["url"]]],
            "updated": "2026-10-16", "_slug": cat["slug"], "_body": body})
        sec_names = {s["slug"]: s["name"] for s in sections}
        for f in cat["families"]:
            url = family_url(cat, f)
            tips = "".join(f'<li><strong>{esc(h)}.</strong> {esc(x)}</li>' for h, x in f["tips"])
            faqs = "".join(
                f'<details class="faq-item"><summary><h3>{esc(q["q"])}</h3><span class="faq-chev" aria-hidden="true"></span></summary><p>{esc(q["a"])}</p></details>'
                for q in f["faqs"])
            others = [e for e, g in zip(entries, cat["families"]) if g["section"] == f["section"] and g["slug"] != f["slug"]][:4]
            related = "".join(f'<li><a href="{esc(e["url"])}">{esc(e["name"])}</a></li>' for e in others)
            body = (
                '<section class="section">\n  <div class="container content-page family-page">\n'
                '    {{breadcrumb}}\n'
                f'    <p class="family-kicker">{esc(sec_names.get(f["section"], ""))}</p>\n'
                f'    <h1>{esc(f["h1"])}</h1>\n    <p class="lead">{esc(f["intro"])}</p>\n'
                '    <p class="family-status"><strong>Picks coming soon.</strong> We add a product only after we have read the maker\'s page and the shop listings. '
                'Read <a href="/how-we-pick/">how we pick</a>.</p>\n'
                f'    <h2>Our picks</h2>\n    <ul class="pick-slots">{note_slots}</ul>\n'
                '    <h2>Comparison</h2>\n    <div class="empty-state"><p>A comparison table appears here once the first picks are added.</p></div>\n'
                f'    <h2>Buying guide</h2>\n    <ul class="family-tips">{tips}</ul>\n'
                f'    <h2>Common questions</h2>\n{faqs}\n'
                f'    <h2>More {esc(sec_names.get(f["section"], "").lower())} guides</h2>\n    <ul class="related-links">{related}'
                f'<li><a href="{esc(cat["url"])}">All {esc(cat["name"])}</a></li></ul>\n'
                '    <aside class="affiliate-box" id="affiliate-note"><svg class="ic" aria-hidden="true"><use href="#i-info"/></svg>'
                '<p><strong>Affiliate disclosure.</strong> We have no approved affiliate accounts yet, and this page earns us nothing today. '
                'If that changes, we will say so here first. <a href="/affiliate-disclosure/">Read the full disclosure</a>.</p></aside>\n'
                '  </div>\n</section>')
            pages.append({
                "url": url, "title": f["h1"], "description": f["meta"],
                "css": ["buttons", "breadcrumb", "content-page", "faq", "watches", "families"], "js": [], "noindex": True,
                "breadcrumbs": [["Shop by Category", "/products/"], [cat["name"], cat["url"]], [f["name"], url]],
                "updated": "2026-10-16", "_slug": f'{cat["slug"]}-{f["section"]}-{f["slug"]}', "_body": body})
    return pages


def faq_items():
    items = json.loads(read(SRC / "pages" / "about" / "faq.json"))
    for it in items:
        text = it["a_affiliate"] if CONFIG.get("affiliate_active") and it.get("a_affiliate") else it["a"]
        it["html"] = text.replace("{{contact_email}}", esc(CONFIG["contact_email"]))
    return items


def about_faq():
    rows = []
    for n, it in enumerate(faq_items(), 1):
        rows.append(
            f'<details class="faq-item" id="{esc(it["id"])}">'
            f'<summary><span class="faq-num" aria-hidden="true">{n:02d}</span>'
            f'<span class="faq-q">{esc(it["q"])}</span><span class="faq-plus" aria-hidden="true"></span></summary>'
            f'<div class="faq-a"><p>{it["html"]}</p></div></details>')
    return ('<section class="about-faq" id="faq" aria-labelledby="faq-title">\n'
            '<h2 id="faq-title">Frequently Asked Questions</h2>\n'
            '<div class="faq-list">' + "".join(rows) + '</div>\n</section>')


def home_category_strip():
    """Compact one-row category shortcuts for the home page (the full cards live on /products/)."""
    items = []
    for c in CATEGORIES:
        thumb = c.get("thumb") or c.get("image")
        pic = (f'<img src="{esc(thumb)}" alt="" width="40" height="40" loading="lazy">' if thumb
               else category_icon(c, "home-cat-ic"))
        items.append(f'<li><a class="home-cat" href="{esc(c["url"])}" style="--hue:{c["hue"]}">'
                     f'<span class="home-cat-pic" aria-hidden="true">{pic}</span>'
                     f'<span class="home-cat-name">{esc(c["name"])}</span></a></li>')
    return '<ul class="home-cat-strip">' + "".join(items) + '</ul>'


def about_cover_cards():
    items = []
    for c in CATEGORIES:
        items.append(
            f'<li><a class="cover-card" href="{esc(c["url"])}" style="--hue:{c["hue"]}">'
            f'<span class="cover-art" aria-hidden="true">{category_art(c)}</span>'
            f'<span class="cover-body"><span class="cover-name">{esc(c["name"])}</span>'
            '<svg class="ic cover-go" aria-hidden="true"><use href="#i-arrow"/></svg></span></a></li>')
    return '<ul class="cover-grid">' + "".join(items) + '</ul>'


def category_placeholder_pages():
    pages = []
    for c in CATEGORIES:
        if c["status"] != "placeholder":
            continue
        body = (
            '<section class="section">\n  <div class="container content-page">\n'
            '    {{breadcrumb}}\n'
            f'    <h1>{esc(c["name"])}</h1>\n    <p class="lead">{esc(c["description"])}</p>\n'
            '    <div class="empty-state"><p><strong>Category content coming soon.</strong></p>'
            '<p><a href="/products/">Back to Shop by Category</a></p></div>\n'
            '  </div>\n</section>')
        pages.append({
            "url": c["url"], "title": c["name"], "description": c["description"],
            "css": ["buttons", "breadcrumb", "content-page", "watches"], "js": [], "noindex": True,
            "breadcrumbs": [["Shop by Category", "/products/"], [c["name"], c["url"]]],
            "updated": "2026-10-16", "_slug": c["slug"], "_body": body,
        })
    return pages


def category_chips(current_url):
    items = [{"label": "All products", "url": "/products/"}] + [
        c for c in CONFIG.get("categories", [])]
    links = []
    for item in items:
        cur = ' aria-current="page"' if item["url"] == current_url else ""
        links.append(f'<a class="chip" href="{item["url"]}"{cur}>{esc(item["label"])}</a>')
    return '<nav class="chips" aria-label="Product categories">' + "".join(links) + "</nav>"


def affiliate_disclosure_body():
    """Disclosure text follows the real status (affiliate_active, amazon_associate_approved in site.config.json)."""
    if not CONFIG.get("affiliate_active"):
        return (
            '    <p class="lead">SAT is currently not earning commissions from the product links displayed on this website.</p>\n'
            '    <p>Some links may direct users to third-party retailers, brand websites or shopping platforms. SAT does not currently receive compensation when users visit or purchase through these links.</p>\n'
            '    <h2>What may change</h2>\n'
            '    <p>In the future, SAT may participate in affiliate programs, including Amazon Associates and other retailer or brand affiliate programs.</p>\n'
            '    <p>If affiliate links are introduced:</p>\n'
            '    <ul>\n'
            '      <li>they will be clearly disclosed</li>\n'
            '      <li>SAT may earn a commission from qualifying purchases</li>\n'
            '      <li>this will not increase the price paid by the customer</li>\n'
            '      <li>editorial recommendations should remain independent</li>\n'
            '    </ul>\n'
            '    <h2>Questions</h2>\n'
            '    <p>Write to <a href="mailto:' + esc(CONFIG["contact_email"]) + '">' + esc(CONFIG["contact_email"]) + '</a>.</p>')
    amazon = ('    <p>As an Amazon Associate I earn from qualifying purchases.</p>\n'
              if CONFIG.get("amazon_associate_approved") else "")
    return (
        '    <p class="lead">Some links on this website are affiliate links.</p>\n'
        '    <p>If you buy through an affiliate link, SAT may earn a commission from qualifying purchases. This does not increase the price you pay, and editorial recommendations remain independent.</p>\n'
        + amazon +
        '    <p>Affiliate links are marked near the links. Questions: <a href="mailto:' + esc(CONFIG["contact_email"]) + '">' + esc(CONFIG["contact_email"]) + '</a>.</p>')


def human_date(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def minify_css(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    css = re.sub(r"\s+", " ", css)
    css = re.sub(r"\s*([{};,>])\s*", r"\1", css)
    css = re.sub(r":\s+", ":", css)
    css = css.replace(";}", "}")
    return css.strip()


def minify_js(js):
    lines = []
    for line in js.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def write_asset(kind, key, content):
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:8]
    name = f"{key}.{digest}.{kind}"
    out = DIST / "assets" / kind / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return f"/assets/{kind}/{name}"


def bundle(kind, names, key):
    parts = []
    for name in names:
        path = SRC / kind / f"{name}.{kind}"
        if not path.exists():
            errors.append(f"missing {kind} source: {path.relative_to(ROOT)}")
            continue
        parts.append(read(path))
    joined = "\n".join(parts)
    if kind == "css" and re.search(r"(?<![\w-])content\s*:(?!\s*([\"']{2}\s*[;}]|attr\(|counter\())|url\(", joined):
        errors.append(f"{key}: the CSS minifier is not string-aware; avoid content: and url( or upgrade it")
    return write_asset(kind, key, minify_css(joined) if kind == "css" else minify_js(joined))


_MENU_ARTICLES = []
SHOP = [None]
SEARCH_URL = [""]
SEARCH_ASSETS = {"js": "", "css": ""}


def short_title(title):
    return re.sub(r"\s*\(\d{4}\)\s*$", "", title)


def menu_icon(c):
    if c.get("thumb"):
        return f'<img class="menu-img" src="{esc(c["thumb"])}" alt="" loading="lazy" width="80" height="80">'
    return category_icon(c, "menu-ic")


def category_menu(item, current_url=None):
    """'Shop by Category' dropdown: a compact list with small colour icons, built from categories.json
    and the articles. The toggle still links to /products/ without JavaScript."""
    def cur(url):
        return ' aria-current="page"' if url == current_url else ""

    rows = []
    for c in CATEGORIES:
        n = sum(1 for a in _MENU_ARTICLES if a["article"]["category"] == c["name"])
        if c["status"] == "placeholder":
            n = 0
        families = c.get("families") or []
        meta = (f"{len(families)} product types" if families else
                (f"{n} guides" if n > 1 else ("1 guide" if n == 1 else "Coming soon")))
        if families:
            n = len(families)
        soon = "" if n else " is-soon"
        rows.append(
            f'            <li><a class="menu-row" href="{c["url"]}" style="--hue:{c["hue"]}"{cur(c["url"])}>'
            f'<span class="menu-tile" aria-hidden="true">{menu_icon(c)}</span>'
            f'<span class="menu-text"><span class="menu-name">{esc(c["name"])}</span>'
            f'<span class="menu-meta{soon}">{meta}</span></span>'
            '<span class="chev" aria-hidden="true">\u203a</span></a></li>')
    return (
        '        <li class="has-menu">\n'
        f'          <a href="{item["url"]}" class="menu-toggle"{cur(item["url"])}>'
        f'{esc(item["label"])} <span class="caret" aria-hidden="true">\u25be</span></a>\n'
        '          <div class="category-menu" id="category-menu">\n'
        '            <ul class="menu-list">\n' + "\n".join(rows) + '\n            </ul>\n'
        f'            <a class="menu-all" href="/products/"{cur("/products/")}>View all categories '
        '<svg class="ic" aria-hidden="true"><use href="#i-arrow"/></svg></a>\n'
        '          </div>\n'
        '        </li>')


def link_list(items, current_url=None, mobile_split=False):
    lines = []
    for item in items:
        if item.get("enabled") is False:
            continue
        if item.get("menu") == "categories":
            lines.append(category_menu(item, current_url))
            continue
        cur = ' aria-current="page"' if item["url"] == current_url else ""
        mobile_class = ' class="mobile-secondary"' if mobile_split and item["url"] != "/" else ""
        lines.append(f'        <li{mobile_class}><a href="{item["url"]}"{cur}>{esc(item["label"])}</a></li>')
    return "\n".join(lines)


def breadcrumb_html(crumbs):
    if not crumbs:
        return ""
    items = ['<a href="/">Home</a>']
    for i, (name, url) in enumerate(crumbs):
        if i == len(crumbs) - 1:
            items.append(f'<span aria-current="page">{esc(name)}</span>')
        else:
            items.append(f'<a href="{url}">{esc(name)}</a>')
    return '<nav class="breadcrumb" aria-label="Breadcrumb">' + " / ".join(items) + "</nav>"


def json_ld(blocks):
    if not blocks:
        return ""
    out = []
    for block in blocks:
        data = json.dumps(block, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
        out.append(f'<script type="application/ld+json">{data}</script>')
    return "\n".join(out) + "\n"


def structured_data(meta, canonical, title):
    site = CONFIG["site_url"].rstrip("/")
    blocks = []
    org = {"@type": "Organization", "name": CONFIG["site_name"], "url": site + "/"}
    if meta.get("schema") == "home":
        blocks.append({"@context": "https://schema.org", "@type": "WebSite",
                       "name": CONFIG["site_name"], "url": site + "/", "publisher": org})
    crumbs = meta.get("breadcrumbs")
    if crumbs:
        items = [{"@type": "ListItem", "position": 1, "name": "Home", "item": site + "/"}]
        for i, (name, url) in enumerate(crumbs, start=2):
            items.append({"@type": "ListItem", "position": i, "name": name, "item": site + url})
        blocks.append({"@context": "https://schema.org", "@type": "BreadcrumbList",
                       "itemListElement": items})
    if meta.get("schema") == "article":
        blocks.append({
            "@context": "https://schema.org", "@type": "Article",
            "headline": meta["title"], "description": meta["description"],
            "datePublished": meta.get("published", meta["updated"]),
            "dateModified": meta["updated"],
            "author": org, "publisher": org,
            "mainEntityOfPage": canonical,
        })
    return blocks


# ---------- build ----------

STORES = {
    "Amazon": "https://www.amazon.in/s?k=",
    "Flipkart": "https://www.flipkart.com/search?q=",
    "Decathlon": "https://www.decathlon.in/search?Ntt=",
    "Puma": "https://in.puma.com/in/en/search?q=",
}


def render_guide(g, related=()):
    """Body HTML for a guide in src/guides/<slug>/guide.json (same layout as the hand-written article)."""
    picks = g["picks"]
    ids = [slugify_heading(p["name"], set()) for p in picks]
    cols = g["columns"]

    quick = "\n".join(
        f'      <li><a href="#{ids[i]}"><span class="qp-rank">{esc(p["label"])}</span>'
        f'<strong>{esc(p["name"])}</strong><span class="qp-for">{esc(p["cells"][0])}</span></a></li>'
        for i, p in enumerate(picks))

    head = "".join(f'<th scope="col" role="columnheader">{esc(c)}</th>' for c in ["Pick"] + cols + ["Price level"])
    rows = []
    for p in picks:
        cells = "".join(f'<td role="cell" data-label="{esc(c)}">{esc(v)}</td>' for c, v in zip(cols, p["cells"]))
        rows.append(f'          <tr role="row"><th scope="row" role="rowheader">{esc(p["name"])}</th>{cells}'
                    f'<td role="cell" data-label="Price level">{esc(p["tier"])}</td></tr>')
    table = ('    <div class="compare-table-wrap">\n      <table class="compare-table" role="table">\n'
             '        <caption class="visually-hidden">Comparison of three picks</caption>\n'
             f'        <thead><tr role="row">{head}</tr></thead>\n        <tbody>\n' + "\n".join(rows) +
             '\n        </tbody>\n      </table>\n    </div>')

    blocks = []
    for p in picks:
        buttons = []
        for k, store in enumerate(p["stores"]):
            q = urllib.parse.quote_plus(p["search_query"])
            cls = "btn-primary" if k == 0 else "btn-outline"
            buttons.append(
                f'<a href="{STORES[store]}{q}" class="btn {cls} btn-small" target="_blank" rel="nofollow noopener" '
                f'aria-label="Search on {store} for {esc(p["name"])} (opens in a new tab)">Search on {store} '
                '<svg class="ic" aria-hidden="true"><use href="#i-external"/></svg></a>')
        if buttons:
            cta_html = " ".join(buttons)
            cta_note = '      <p class="cta-note">Opens a search on the shop. We do not sell products or take payments.</p>\n'
        else:
            cta_html = '<span class="no-store">No shop link: we could not confirm it is on sale in India right now.</span>'
            cta_note = ""
        paras = "\n".join(f"      <p>{esc(x)}</p>" for x in p["paragraphs"])
        good = "".join(f"<li>{esc(x)}</li>" for x in p["good"])
        bad = "".join(f"<li>{esc(x)}</li>" for x in p["not_good"])
        blocks.append(
            '    <div class="product-block">\n'
            f'      <span class="rank">{esc(p["label"])}</span>\n'
            f'      <h3>{esc(p["name"])}</h3>\n'
            f'      <p class="verdict">Verdict: {esc(p["verdict"])}</p>\n'
            f'{paras}\n'
            '      <div class="pros-cons">\n'
            f'        <div class="pros"><h4>Good</h4><ul>{good}</ul></div>\n'
            f'        <div class="cons"><h4>Not so good</h4><ul>{bad}</ul></div>\n'
            '      </div>\n'
            '      <div class="cta-row">\n'
            f'        <span class="price-tag">{esc(p["tier"])} <span class="approx">(check the price at the shop)</span></span>\n'
            f'        {cta_html}\n'
            '      </div>\n'
            + cta_note +
            '    </div>')

    choose = "\n".join(f'    <p><strong>{esc(c["heading"])}.</strong> {esc(c["text"])}</p>' for c in g["choose"])
    faq = "\n".join(
        f'      <details class="faq-item"><summary><h3>{esc(f["q"])}</h3><span class="faq-chev" aria-hidden="true"></span></summary>'
        f'<p>{esc(f["a"])}</p></details>' for f in g["faq"])
    sources = "\n".join(
        f'      <li><a href="{esc(s["url"])}" target="_blank" rel="nofollow noopener">{esc(s["label"])}</a></li>'
        for s in g.get("sources", []))
    rel_html = "\n".join(
        f'      <li><a href="{r["url"]}"><strong>{esc(r["title"])}</strong><span>{esc(r["summary"])}</span></a></li>'
        for r in related)
    bar = "\n".join(f'  <a href="#{ids[i]}">{esc(" ".join(p["name"].split()[:2]))}</a>' for i, p in enumerate(picks))

    top = (
        '<div class="read-progress" aria-hidden="true"></div>\n'
        '<section class="section">\n'
        '  <div class="container content-page content-article">\n'
        '    {{breadcrumb}}\n'
        f'    <h1>{esc(g["title"])}</h1>\n'
        '    <p class="updated">Last updated: {{updated_human}} · {{read_time}}</p>\n'
        '    {{share}}\n\n'
        f'    <p class="lead">{esc(g["lead"])}</p>\n\n'
        '    <aside class="method-note">\n'
        '      <svg class="ic" aria-hidden="true"><use href="#i-info"/></svg>\n'
        "      <p><strong>How we picked these:</strong> we read the maker and shop details and what buyers say online. We have not tested these products ourselves yet. Details can change from seller to seller, so check the listing before you pay. The buttons below open each shop's own search page. These three are a short list for different needs, not a ranking of every product. Budget, Mid-range and Premium are our own rough judgement, not based on prices. Read <a href=\"/how-we-pick/\">how we pick</a>.</p>\n"
        '    </aside>\n\n'
        f'    <ol class="quick-picks">\n{quick}\n    </ol>\n\n'
        '    <div class="article-layout">\n      {{toc}}\n      <div class="article-main">\n'
        f'{table}\n\n'
        '    <section class="compare-tool" aria-labelledby="compare-title" hidden>\n'
        '      <h2 id="compare-title" data-toc="skip">Compare two picks</h2>\n'
        '      <p>Pick any two. The details come from the table above.</p>\n'
        '      <div class="pickers">\n'
        '        <div><label for="compare-a">First pick</label><select id="compare-a" name="compare-a"></select></div>\n'
        '        <div><label for="compare-b">Second pick</label><select id="compare-b" name="compare-b"></select></div>\n'
        '      </div>\n'
        '      <div class="compare-out" aria-live="polite"></div>\n'
        '    </section>\n\n'
        '    <h2>Our three picks</h2>\n    <span id="picks-start"></span>\n\n')
    bottom = (
        f'\n\n    <h2>How to choose</h2>\n{choose}\n\n'
        f'    <h2>Common questions</h2>\n{faq}\n\n'
        '    <h2>More buying guides</h2>\n'
        f'    <ul class="related-list">\n{rel_html}\n    </ul>\n\n'
        '    <h2>Sources we used</h2>\n'
        '    <p>Pages we read, checked on {{updated_human}}. Shops change listings often, so details may differ when you look.</p>\n'
        f'    <ul class="source-list">\n{sources}\n    </ul>\n'
        '      </div>\n    </div>\n  </div>\n</section>\n\n'
        f'<nav class="pick-bar" aria-label="Jump to a pick" hidden>\n{bar}\n  <a href="#main">Top</a>\n</nav>\n')
    return top + "\n\n".join(blocks) + bottom


def load_guides():
    raw = []
    gdir = SRC / "guides"
    for gp in (sorted(gdir.glob("*/guide.json")) if gdir.exists() else []):
        g = json.loads(read(gp))
        name = gp.parent.name
        for key in ("published", "slug", "title", "tag", "summary", "description", "lead", "columns", "picks"):
            if key not in g:
                errors.append(f"guide {name}: missing {key}")
        if errors:
            continue
        if len(g["picks"]) != 3:
            errors.append(f"guide {name}: needs exactly 3 picks")
        names = [p["name"] for p in g["picks"]]
        if len(set(names)) != len(names):
            errors.append(f"guide {name}: duplicate pick names")
        for p in g["picks"]:
            for s in p["stores"]:
                if s not in STORES:
                    errors.append(f"guide {name}: unknown store {s!r}")
            if len(p["cells"]) != len(g["columns"]):
                errors.append(f"guide {name}: {p['name']} has wrong number of table cells")
        raw.append(g)

    def url_of(g):
        return f"/{slugify(g['tag']).replace('_', '-')}/{g['slug']}/"

    guides = []
    for g in raw:
        url = url_of(g)
        siblings = [o for o in raw if o is not g and o["tag"] == g["tag"]]
        others = [o for o in raw if o is not g and o["tag"] != g["tag"]]
        related = [{"url": url_of(o), "title": re.sub(r"\s*\(\d{4}\)\s*$", "", o["title"]), "summary": o["summary"]}
                   for o in (siblings + others)[:4]]
        short = re.sub(r"\s*\(\d{4}\)\s*$", "", g["title"])
        guides.append({
            "url": url, "title": g["title"], "description": g["description"],
            "css": ["buttons", "breadcrumb", "content-page", "compare-table", "product-block", "faq", "toc",
                    "quick-picks", "method-note", "share", "pick-bar", "tools", "guide-extras"],
            "js": ["outbound-links", "toc", "share", "pick-bar", "table-scroll", "compare"],
            "page_css": "article", "og_type": "article", "schema": "article", "toc": True, "share": True,
            "breadcrumbs": [["Shop by Category", "/products/"], ["Sports & Fitness", "/sports-fitness/"], [short, url]],
            "published": g["published"], "updated": g.get("updated", g["published"]),
            "featured": bool(g.get("featured")),
            "article": {"category": "Sports & Fitness", "tag": g["tag"], "summary": g["summary"]},
            "_slug": f"guides/{g['slug']}", "_body": render_guide(g, related),
        })
    return guides


def load_pages():
    pages = []
    for meta_path in sorted((SRC / "pages").rglob("page.json")):
        meta = json.loads(read(meta_path))
        body_path = meta_path.with_name("index.html")
        if not body_path.exists():
            errors.append(f"{meta_path.relative_to(ROOT)}: no index.html next to page.json")
            continue
        meta["_slug"] = meta_path.parent.relative_to(SRC / "pages").as_posix()
        meta["_body"] = read(body_path)
        pages.append(meta)
    pages.extend(load_guides())
    pages.extend(category_placeholder_pages())
    pages.extend(family_pages())
    shop = watches.Watches(SRC, CONFIG)
    SHOP[0] = shop
    errors.extend(shop.errors)
    warnings.extend(shop.warnings)
    pages.extend(shop.pages())
    return pages


def output_path(meta):
    if meta.get("output"):
        return DIST / meta["output"]
    return DIST / meta["url"].strip("/") / "index.html"


def build_page(meta, base, header_t, footer_t, year, articles):
    site_url = CONFIG["site_url"].rstrip("/")
    canonical = site_url + meta["url"]
    title = f'{meta["title"]} — {CONFIG["site_name"]}' if not meta.get("title_full") else meta["title"]
    if len(title) > TITLE_MAX:
        warnings.append(f'{meta["_slug"]}: title is {len(title)} chars (aim for <= {TITLE_MAX})')
    if len(meta["description"]) > DESCRIPTION_MAX:
        warnings.append(f'{meta["_slug"]}: description is {len(meta["description"])} chars (aim for <= {DESCRIPTION_MAX})')

    key = meta["_slug"].replace("/", "-")
    css_names = ALWAYS_CSS + [f"components/{n}" for n in meta.get("css", [])]
    if meta.get("page_css"):
        css_names.append(f'pages/{meta["page_css"]}')
    css_names += LAST_CSS
    js_names = ALWAYS_JS + [f"components/{n}" for n in meta.get("js", [])]
    if meta.get("page_js"):
        js_names.append(f'pages/{meta["page_js"]}')
    css_href = bundle("css", css_names, key)
    js_src = bundle("js", js_names, key)

    base_ctx = {
        "site_name": esc(CONFIG["site_name"]), "contact_email": esc(CONFIG["contact_email"]),
        "logo_primary": esc(CONFIG["logo_primary"]),
        "logo_html": logo_html(CONFIG["logo_primary"]),
        "affiliate_disclosure_body": affiliate_disclosure_body(),
        "affiliate_note": ("Some links on this site are affiliate links. We may earn a commission from qualifying purchases, at no extra cost to you. See our Affiliate Disclosure."
                           if CONFIG.get("affiliate_active") else
                           "SAT does not currently earn commissions from product links. If this changes, affiliate relationships will be clearly disclosed."),
        "year": year, "updated_human": human_date(meta["updated"]),
        "search_index_url": SEARCH_URL[0],
        "search_js_url": SEARCH_ASSETS["js"], "search_css_url": SEARCH_ASSETS["css"],
    }
    article_ctx = {
        "articles_all": article_cards(articles),
        "articles_latest": article_cards(articles[:3]),
        "category_chips": category_chips(meta["url"]),
        "category_cards": category_cards(meta["url"]),
        "about_cover_cards": about_cover_cards(),
        "about_faq": about_faq(),
        "home_category_strip": home_category_strip(),
        "home_collage": home_collage(),
        "home_video": home_video(),
        "category_directory": category_directory(),
        "category_sections": category_sections(articles),
        "toc": "@@TOC@@" if meta.get("toc") else "",
        "share": share_html(canonical, meta["title"]) if meta.get("share") else "",
        "read_time": "@@READ@@",
        "body_class": ("theme-" + meta["theme"]) if meta.get("theme") else "",
    }
    for cat in {a["article"]["category"] for a in articles}:
        in_cat = [a for a in articles if a["article"]["category"] == cat]
        article_ctx["articles_" + slugify(cat)] = article_cards(in_cat)
        groups = []
        for tag in sorted({a["article"]["tag"] for a in in_cat}):
            groups.append('<div class="tag-group"><h2>' + esc(tag) + '</h2>\n'
                          + article_cards([a for a in in_cat if a["article"]["tag"] == tag]) + '\n</div>')
        article_ctx["groups_" + slugify(cat)] = "\n".join(groups)
    content = render(meta["_body"], {**base_ctx, **article_ctx, "breadcrumb": breadcrumb_html(meta.get("breadcrumbs"))})
    toc_html = ""
    if meta.get("toc"):
        content, toc_html = decorate(content)
    content = content.replace("@@TOC@@", toc_html)
    words = len(re.sub(r"<[^>]+>", " ", content).split())
    content = content.replace("@@READ@@", f"{max(1, round(words / 200))} min read")
    header = render(header_t, {
        **base_ctx,
        "nav_items": link_list(CONFIG["nav"], meta["url"], mobile_split=True),
        "mobile_nav_items": link_list(
            [item for item in CONFIG["nav"] if item["url"] != "/" and item.get("menu") != "categories"],
            meta["url"]),
    })
    footer = render(footer_t, {**base_ctx,
                               "footer_site_items": link_list(CONFIG["footer_site"], meta["url"]),
                               "footer_category_items": link_list([{"label": c["name"], "url": c["url"]} for c in CATEGORIES], meta["url"]),
                               "footer_legal_items": link_list(CONFIG["footer_legal"], meta["url"])})
    page = render(base, {
        **base_ctx,
        "language": CONFIG["language"], "locale": CONFIG["locale"],
        "title": esc(title), "description": esc(meta["description"]),
        "canonical": canonical,
        "canonical_tag": "" if meta.get("noindex") else f'<link rel="canonical" href="{canonical}">\n',
        "og_url_tag": "" if meta.get("noindex") else f'<meta property="og:url" content="{canonical}">\n',
        "verification_tag": (f'<meta name="google-site-verification" content="{esc(CONFIG["google_site_verification"])}">\n'
                             if CONFIG.get("google_site_verification") else ""),
        "robots_tag": '<meta name="robots" content="noindex, follow">\n' if meta.get("noindex") else "",
        "og_type": meta.get("og_type", "website"),
        "css_href": css_href, "js_src": js_src,
        "body_class": ("theme-" + meta["theme"]) if meta.get("theme") else "",
        "jsonld": json_ld(structured_data(meta, canonical, title)),
        "header": header, "content": content, "footer": footer,
    })
    out = output_path(meta)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")


def write_sitemap(pages):
    site_url = CONFIG["site_url"].rstrip("/")
    entries = []
    for meta in pages:
        if meta.get("noindex"):
            continue
        entries.append(f'  <url>\n    <loc>{site_url}{meta["url"]}</loc>\n    <lastmod>{meta["updated"]}</lastmod>\n  </url>')
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(entries) + "\n</urlset>\n")
    (DIST / "sitemap.xml").write_text(xml, encoding="utf-8")


# ---------- site search: a static index the browser searches by itself ----------

SEARCH_SKIP = {"/", "/contact/", "/privacy-policy/", "/terms/", "/copyright/", "/affiliate-disclosure/",
               "/search/", "/watches/preview/", "/404/"}
SEARCH_PAGES = {"/about/", "/how-we-pick/", "/products/"}
SEARCH_KEYWORDS = {
    "popular": ["watch under 2000", "women watch under 3000", "men watch under 6000", "badminton racket", "yoga mat",
                "dumbbells", "running shoes", "sunscreen", "air fryer", "pressure cooker", "men t-shirts", "kurti sets"],
    "watches": ["watch under 2000", "women watch under 3000", "men watch under 6000", "men watch under 10000",
                "analog watch", "titan watch", "casio watch", "fastrack watch", "leather strap watch",
                "metal strap watch", "formal watch", "minimal watch"],
    "sports-fitness": ["badminton racket", "cricket bat", "football", "sports shoes", "sports bag", "dumbbells",
                       "resistance bands", "yoga mat", "skipping rope", "gym gloves", "foam roller", "shaker bottle"],
    "beauty-personal-care": ["skin care", "hair care", "makeup", "men grooming", "bath body", "sunscreen"],
    "home-kitchen": ["pressure cooker", "mixer grinder", "cookware set", "air fryer", "electric kettle", "storage containers",
                     "lunch box", "kitchen organizer", "frying pan", "bedsheets", "pillows", "floor mats"],
    "clothing-accessories": ["men t-shirts", "shirts", "jeans", "kurti sets", "joggers", "hoodies", "jackets",
                             "leggings", "co-ord sets", "night dress", "casual dresses", "shorts"],
}
SEARCH_SHORT = {"watches": "Watches", "sports-fitness": "Sports", "beauty-personal-care": "Beauty",
                "home-kitchen": "Home", "clothing-accessories": "Clothing"}


def search_keyword_groups():
    groups = [{"id": "popular", "label": "Popular", "hue": 22, "q": SEARCH_KEYWORDS["popular"]}]
    for c in CATEGORIES:
        if SEARCH_KEYWORDS.get(c["slug"]):
            groups.append({"id": c["slug"], "label": SEARCH_SHORT.get(c["slug"], c["name"]), "name": c["name"],
                           "hue": c["hue"], "url": c["url"], "q": SEARCH_KEYWORDS[c["slug"]]})
    return groups


def price_band_max(label):
    """Upper limit in rupees of a product price band, or None for open-ended bands."""
    label = label or ""
    nums = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]*", label)]
    if not nums or "premium" in label.lower():
        return None
    return max(nums)


def search_entries(pages):
    cat_by_url = {c["url"]: c for c in CATEGORIES}
    fam_by_url = {}
    for c in CATEGORIES:
        for f in c.get("families", []):
            fam_by_url[family_url(c, f)] = (c, f)
    out = []

    def add(**e):
        if not e.get("m"):
            under = re.search(r"Under \u20b9([\d,]+)", e.get("t", ""))
            if under:
                e["m"] = int(under.group(1).replace(",", ""))
        out.append({k: v for k, v in e.items() if v not in (None, "", False)})

    for meta in pages:
        url = meta["url"]
        if url in SEARCH_SKIP:
            continue
        title = html.unescape(meta["title"])
        desc = html.unescape(meta["description"])
        soon = bool(meta.get("noindex"))
        if meta.get("article"):
            add(t=title, u=url, k="Guide", c=meta["article"]["category"], d=desc, x=meta["article"].get("tag", ""))
        elif url in cat_by_url:
            c = cat_by_url[url]
            add(t=c["name"], u=url, k="Category", c=c["name"], d=c["description"], h=c["hue"], s=soon)
        elif url in fam_by_url:
            c, f = fam_by_url[url]
            add(t=title, u=url, k="Product type", c=c["name"], d=f["description"], x=f["name"], s=soon)
        elif url.startswith("/watches/"):
            m = re.fullmatch(r"/watches/(men|women)/(?:under-(\d+)/)?", url)
            if m:
                g = m.group(1)
                add(t=title, u=url, k="Watch list", c="Watches", d=desc, g=g, m=int(m.group(2)) if m.group(2) else None,
                    x=f"watch watches wristwatch {g}", s=soon)
            elif url.startswith("/watches/brands/"):
                add(t=title, u=url, k="Brand", c="Watches", d=desc, x="watch watches wristwatch brand", s=soon)
            elif url.startswith("/watches/style/"):
                add(t=title, u=url, k="Style", c="Watches", d=desc, x="watch watches wristwatch style", s=soon)
            elif url == "/watches/guide/":
                add(t=title, u=url, k="Guide", c="Watches", d=desc, x="watch watches wristwatch buying guide")
        elif url in SEARCH_PAGES:
            add(t=title, u=url, k="Page", d=desc)

    for it in faq_items():
        add(t=it["q"], u="/about/#" + it["id"], k="FAQ", c="About", d=re.sub(r"<[^>]+>", "", it["html"]), x="faq question")
    shop = SHOP[0]
    if shop is not None:
        for p in shop.products:
            if p.get("sample"):
                continue
            brand = shop.brands[p["brand"]]["name"]
            styles = " ".join(shop.styles[st]["label"] for st in p["styles"])
            add(t=f'{brand} {p["model"]}', u=shop.review_url(p), k="Product", c="Watches", d=p["verdict"],
                g=shop.primary_gender(p), m=shop.budgets[p["budget"]].get("max"),
                x=f'watch watches wristwatch {" ".join(p["gender"])} {styles} {p.get("strap", "")} {p.get("best_for", "")}')
    for cat in CATEGORIES:
        for p in load_products(cat["slug"]):
            if p.get("sample") or not p.get("name"):
                continue
            fam = next((f for f in cat.get("families", []) if f["slug"] == p.get("family")), None)
            if not fam:
                continue
            add(t=p["name"], u=f'{family_url(cat, fam)}#r-{p["id"]}', k="Product", c=cat["name"],
                d=p.get("best_for", ""), m=price_band_max(p.get("price_band")),
                x=" ".join([p.get("brand", ""), p.get("product_type", ""), fam["name"], p.get("suits", "")]))
    return out


def write_search_index(pages):
    payload = {"v": 1, "ex": SEARCH_KEYWORDS["popular"][:4], "kw": search_keyword_groups(), "e": search_entries(pages)}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    name = f"search-index.{digest}.json"
    (DIST / name).write_text(text, encoding="utf-8")
    SEARCH_URL[0] = "/" + name
    return len(payload["e"])


def write_robots():
    site_url = CONFIG["site_url"].rstrip("/")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n", encoding="utf-8")


def write_headers():
    (DIST / "_headers").write_text(
        "/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n\n"
        "/search-index.*\n  Cache-Control: public, max-age=31536000, immutable\n\n"
        "/videos/*\n  Cache-Control: public, max-age=86400\n\n"
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n",
        encoding="utf-8")


def check_affiliate_rel():
    """When affiliate links are live, every outbound shop link must say sponsored."""
    if not CONFIG.get("affiliate_active"):
        return
    for page in DIST.rglob("*.html"):
        for m in re.finditer(r'<a [^>]*target="_blank"[^>]*>', page.read_text(encoding="utf-8")):
            if "sponsored" not in m.group(0) and "wa.me" not in m.group(0) and 'data-source="1"' not in m.group(0):
                errors.append(f"{page.relative_to(DIST).as_posix()}: affiliate_active is true but a shop link lacks rel=sponsored")


def check_links():
    """Every root-relative href/src must resolve to a built file; '#' links are errors."""
    for page in DIST.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        rel = page.relative_to(DIST).as_posix()
        ids = re.findall(r'\sid="([^"]+)"', text)
        for dup in {i for i in ids if ids.count(i) > 1}:
            errors.append(f"{rel}: duplicate id {dup!r}")
        for m in re.finditer(r'href="#([^"]+)"', text):
            if m.group(1) not in ids:
                errors.append(f"{rel}: link to missing section #{m.group(1)}")
        for m in re.finditer(r'(?:href|src)="([^"]*)"', text):
            url = m.group(1)
            if url in ("#", ""):
                errors.append(f"{rel}: empty link ({url or 'empty'!r})")
            elif url.startswith("/") and not url.startswith("//"):
                target = url.split("#")[0].split("?")[0]
                path = DIST / target.lstrip("/")
                if not (path.is_file() or (path / "index.html").is_file()):
                    errors.append(f"{rel}: broken internal link {url}")


def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    base = read(SRC / "templates" / "base.html")
    header_t = read(SRC / "partials" / "header.html")
    footer_t = read(SRC / "partials" / "footer.html")
    year = datetime.date.today().year

    pages = load_pages()
    for meta in pages:
        minimum = meta.get("hub_min_articles")
        if minimum:
            cat = meta.get("hub_category")
            count = sum(1 for p in pages if p.get("article") and (not cat or p["article"]["category"] == cat))
            if count < minimum:
                meta["noindex"] = True
    articles = sorted((p for p in pages if p.get("article")),
                      key=lambda p: p.get("published", p["updated"]), reverse=True)
    _MENU_ARTICLES[:] = articles
    write_search_index(pages)
    SEARCH_ASSETS["js"] = bundle("js", ["components/search"], "search")
    SEARCH_ASSETS["css"] = bundle("css", ["components/search-panel"], "search")
    for meta in pages:
        build_page(meta, base, header_t, footer_t, year, articles)
    static = SRC / "static"
    if static.exists():
        shutil.copytree(static, DIST, dirs_exist_ok=True)
    folders = sorted({"/" + p["url"].strip("/").split("/")[0] + "/" for p in pages if p.get("article")})
    existing = {p["url"] for p in pages}
    extra = [f + " /sports-fitness/ 301" for f in folders if f not in existing]
    section_redirects = [f'{c["url"]}{s["slug"]}/ {c["url"]}#{s["slug"]} 301'
                         for c in CATEGORIES if c.get("families") for s in c.get("sections", [])]
    extra = extra + section_redirects
    redirects = DIST / "_redirects"
    base_redirects = redirects.read_text(encoding="utf-8").rstrip("\n").splitlines() if redirects.exists() else []
    known = {line.split()[0] for line in base_redirects if line.strip()}
    redirects.write_text("\n".join(base_redirects + [e for e in extra if e.split()[0] not in known]) + "\n", encoding="utf-8")
    write_sitemap(pages)
    write_robots()
    write_headers()
    check_links()
    check_affiliate_rel()

    for w in warnings:
        print("warning:", w)
    for e in errors:
        print("ERROR:", e)
    print(f"built {len(pages)} pages into {DIST.relative_to(ROOT)}/ "
          f"({len(warnings)} warnings, {len(errors)} errors)")
    return not errors


def serve():
    import functools
    import http.server
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIST))
    print("serving http://localhost:8000 (Ctrl+C to stop)")
    http.server.ThreadingHTTPServer(("", 8000), handler).serve_forever()


if __name__ == "__main__":
    ok = build()
    if not ok:
        sys.exit(1)
    if "--serve" in sys.argv:
        serve()
