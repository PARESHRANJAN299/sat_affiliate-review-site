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
SRC = ROOT / "src"
DIST = ROOT / "dist"

CONFIG = json.loads((SRC / "site.config.json").read_text(encoding="utf-8"))

# Included in every page's CSS/JS bundle, in this order.
ALWAYS_CSS = [
    "base/variables", "base/reset",
    "base/icons", "layout/container", "layout/section", "layout/header", "layout/footer",
]
# Loaded after component/page CSS so they win the cascade.
LAST_CSS = ["base/accessibility", "base/print"]
ALWAYS_JS = ["core/main", "core/menu"]

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


def category_chips(current_url):
    items = [{"label": "All products", "url": "/products/"}] + [
        c for c in CONFIG.get("categories", []) if c.get("enabled") is not False]
    links = []
    for item in items:
        cur = ' aria-current="page"' if item["url"] == current_url else ""
        links.append(f'<a class="chip" href="{item["url"]}"{cur}>{esc(item["label"])}</a>')
    return '<nav class="chips" aria-label="Product categories">' + "".join(links) + "</nav>"


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


def category_menu(item, current_url=None):
    """Amazon-style 'Shop by Category' dropdown; the toggle still links to /products/ without JavaScript."""
    cats = [{"label": "All products", "url": "/products/"}] + [
        c for c in CONFIG.get("categories", []) if c.get("enabled") is not False]
    def cur(url):
        return ' aria-current="page"' if url == current_url else ""
    rows = "\n".join(
        f'              <li><a href="{c["url"]}"{cur(c["url"])}>{esc(c["label"])} <span class="chev" aria-hidden="true">\u203a</span></a></li>'
        for c in cats)
    return (
        '        <li class="has-menu">\n'
        f'          <a href="{item["url"]}" class="menu-toggle"{cur(item["url"])}>'
        f'{esc(item["label"])} <span class="caret" aria-hidden="true">\u25be</span></a>\n'
        '          <div class="category-menu" id="category-menu">\n'
        f'            <p class="category-menu-title">{esc(item["label"])}</p>\n'
        '            <ul>\n' + rows + '\n            </ul>\n'
        '            <p class="category-menu-note">More categories are planned.</p>\n'
        '          </div>\n'
        '        </li>')


def link_list(items, current_url=None):
    lines = []
    for item in items:
        if item.get("enabled") is False:
            continue
        if item.get("menu") == "categories":
            lines.append(category_menu(item, current_url))
            continue
        cur = ' aria-current="page"' if item["url"] == current_url else ""
        lines.append(f'        <li><a href="{item["url"]}"{cur}>{esc(item["label"])}</a></li>')
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
        "affiliate_note": ("Some links on this site are affiliate links. We may earn a commission if you buy, at no extra cost to you."
                           if CONFIG.get("affiliate_active") else
                           "No ads. Our links go to shop search pages and earn us nothing yet. See the Affiliate Disclosure."),
        "year": year, "updated_human": human_date(meta["updated"]),
    }
    article_ctx = {
        "articles_all": article_cards(articles),
        "articles_latest": article_cards(articles[:3]),
        "category_chips": category_chips(meta["url"]),
        "category_sections": category_sections(articles),
        "toc": "@@TOC@@" if meta.get("toc") else "",
        "share": share_html(canonical, meta["title"]) if meta.get("share") else "",
        "read_time": "@@READ@@",
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
    header = render(header_t, {**base_ctx, "nav_items": link_list(CONFIG["nav"], meta["url"])})
    footer = render(footer_t, {**base_ctx,
                               "footer_site_items": link_list(CONFIG["footer_site"], meta["url"]),
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


def write_robots():
    site_url = CONFIG["site_url"].rstrip("/")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {site_url}/sitemap.xml\n", encoding="utf-8")


def write_headers():
    (DIST / "_headers").write_text(
        "/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n\n"
        "/*\n  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n",
        encoding="utf-8")


def check_affiliate_rel():
    """When affiliate links are live, every outbound shop link must say sponsored."""
    if not CONFIG.get("affiliate_active"):
        return
    for page in DIST.rglob("*.html"):
        for m in re.finditer(r'<a [^>]*target="_blank"[^>]*>', page.read_text(encoding="utf-8")):
            if "sponsored" not in m.group(0) and "wa.me" not in m.group(0):
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
    for meta in pages:
        build_page(meta, base, header_t, footer_t, year, articles)
    static = SRC / "static"
    if static.exists():
        shutil.copytree(static, DIST, dirs_exist_ok=True)
    folders = sorted({"/" + p["url"].strip("/").split("/")[0] + "/" for p in pages if p.get("article")})
    existing = {p["url"] for p in pages}
    extra = [f + " /sports-fitness/ 301" for f in folders if f not in existing]
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
