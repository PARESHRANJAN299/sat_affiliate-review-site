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
    "layout/container", "layout/section", "layout/header", "layout/footer",
]
# Loaded after component/page CSS so they win the cascade.
LAST_CSS = ["base/accessibility", "base/print"]
ALWAYS_JS = ["core/main"]

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


def article_cards(articles):
    cards = []
    for a in articles:
        info = a["article"]
        cards.append(
            '      <div class="article-card">\n'
            f'        <span class="tag">{esc(info["tag"])}</span>\n'
            f'        <h3>{esc(a["title"])}</h3>\n'
            f'        <p>{esc(info["summary"])}</p>\n'
            f'        <a href="{a["url"]}" class="read-link">Read the guide \u2192</a>\n'
            '      </div>')
    return '    <div class="article-grid">\n' + "\n".join(cards) + "\n    </div>"


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
    if kind == "css" and re.search(r"(?<![\w-])content\s*:(?!\s*[\"']{2}\s*[;}])|url\(", joined):
        errors.append(f"{key}: the CSS minifier is not string-aware; avoid content: and url( or upgrade it")
    return write_asset(kind, key, minify_css(joined) if kind == "css" else minify_js(joined))


def link_list(items, current_url=None):
    lines = []
    for item in items:
        if item.get("enabled") is False:
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
        "year": year, "updated_human": human_date(meta["updated"]),
    }
    article_ctx = {
        "articles_all": article_cards(articles),
        "articles_latest": article_cards(articles[:3]),
        "category_chips": category_chips(meta["url"]),
    }
    for cat in {a["article"]["category"] for a in articles}:
        article_ctx["articles_" + slugify(cat)] = article_cards([a for a in articles if a["article"]["category"] == cat])
    content = render(meta["_body"], {**base_ctx, **article_ctx, "breadcrumb": breadcrumb_html(meta.get("breadcrumbs"))})
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


def check_links():
    """Every root-relative href/src must resolve to a built file; '#' links are errors."""
    for page in DIST.rglob("*.html"):
        text = page.read_text(encoding="utf-8")
        rel = page.relative_to(DIST).as_posix()
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
    articles = sorted((p for p in pages if p.get("article")),
                      key=lambda p: p.get("published", p["updated"]), reverse=True)
    for meta in pages:
        build_page(meta, base, header_t, footer_t, year, articles)
    static = SRC / "static"
    if static.exists():
        shutil.copytree(static, DIST, dirs_exist_ok=True)
    write_sitemap(pages)
    write_robots()
    write_headers()
    check_links()

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
