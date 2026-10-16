"""Watches section: pages generated from data (src/watches/*).

Everything is driven by three kinds of files, so new brands, budgets, styles, products
and shops can be added without touching this code:

    src/watches/config.json     genders, budgets, brands, styles
    src/watches/merchants.json  shops (Amazon, Flipkart, brand store, other)
    src/watches/products/*.json one file per watch (see src/watches/README.md)

With no products, collection pages link to buying advice and remain noindex.
A collection becomes indexable once it has at least `min_products_to_index` watches.
Standard library only (Python 3.9+).
"""
import html
import re
import collection
import json
import math
import urllib.parse
from pathlib import Path


def esc(value):
    return html.escape(str(value), quote=True)


# ---------- artwork (inline SVG, no photos) ----------

def watch_art(css_class="watch-art"):
    ticks = []
    for i in range(12):
        angle = math.radians(i * 30)
        inner = 44 if i % 3 == 0 else 47
        x1 = 100 + inner * math.sin(angle)
        y1 = 120 - inner * math.cos(angle)
        x2 = 100 + 52 * math.sin(angle)
        y2 = 120 - 52 * math.cos(angle)
        ticks.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    return (
        f'<svg class="{css_class}" viewBox="0 0 200 240" aria-hidden="true" focusable="false">'
        '<path d="M78 0 h44 l4 62 h-52 z"/><path d="M74 178 h52 l-4 62 h-44 z"/>'
        '<circle cx="100" cy="120" r="64"/><circle cx="100" cy="120" r="56"/>'
        '<rect x="164" y="113" width="9" height="14" rx="2"/>'
        + "".join(ticks) +
        '<path d="M100 120 L100 88"/><path d="M100 120 L124 132"/><circle cx="100" cy="120" r="2.5"/>'
        '</svg>')


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"watches: cannot read {path}: {exc}")


class Watches:
    def __init__(self, src, site_config):
        base = Path(src) / "watches"
        self.config = read_json(base / "config.json")
        self.merchants = read_json(base / "merchants.json")
        self.site = site_config
        self.errors = []
        self.warnings = []
        self._check_config()

        self.budgets = {b["slug"]: b for b in self.config["budgets"]}
        self.brands = {b["slug"]: b for b in self.config["brands"]}
        self.styles = {s["slug"]: s for s in self.config["styles"]}
        self.genders = {g["slug"]: g for g in self.config["genders"]}
        self.min_index = self.config.get("min_products_to_index", 3)
        self.config_updated = self.config.get("updated", "2026-10-15")
        self.affiliate_active = bool(site_config.get("affiliate_active"))

        raw = [read_json(p) for p in sorted((base / "products").glob("*.json"))]
        self.samples = [read_json(p) for p in sorted((base / "_sample").glob("*.json"))]
        if self.samples:
            self.brands["sample"] = {"name": "Sample brand", "slug": "sample", "genders": ["men"], "line": "Classic"}
        self.products = []
        for p in raw:
            self._validate(p)
            ok, why = self._ready(p)
            if ok:
                self.products.append(p)
            else:
                self.warnings.append(f"watch {p.get('id', '?')}: not shown ({why})")
        self.products.sort(key=lambda p: (p.get("rank", 999), p["id"]))
        if self.affiliate_active:
            amazon = self.merchants.get("amazon")
            if amazon is not None and not amazon.get("affiliate_value"):
                # one place for the ID: amazon_tracking_id in site.config.json
                amazon["affiliate_value"] = (site_config.get("amazon_tracking_id") or "").strip()
            for key, info in self.merchants.items():
                # Flipkart has no affiliate ID yet; its links stay plain (still rel=sponsored)
                if info.get("search") and key == "amazon" and not info.get("affiliate_value"):
                    self.errors.append(f"affiliate_active is true but merchant {key!r} has no affiliate_value (set amazon_tracking_id in site.config.json)")

    # ---------- validation ----------

    def _check_config(self):
        for key in ("genders", "budgets", "brands", "styles"):
            items = self.config.get(key)
            if not isinstance(items, list) or not items:
                self.errors.append(f"watches config: {key} must be a non-empty list")
                continue
            slugs = [i.get("slug") for i in items]
            if None in slugs or len(set(slugs)) != len(slugs):
                self.errors.append(f"watches config: {key} needs unique slugs")
        if self.errors:
            raise SystemExit("watches: " + "; ".join(self.errors))

    def _validate(self, p):
        pid = p.get("id", "?")
        missing = [k for k in ("id", "brand", "model", "gender", "styles", "verdict") if k not in p]
        if missing:
            self.errors.append(f"watch {pid}: missing {', '.join(missing)}")
            return
        if p["brand"] not in self.brands:
            self.errors.append(f"watch {pid}: unknown brand {p['brand']!r}")
        if p.get("budget") is not None and p["budget"] not in self.budgets:
            self.errors.append(f"watch {pid}: unknown budget {p['budget']!r}")
        for g in p["gender"]:
            if g not in self.genders:
                self.errors.append(f"watch {pid}: unknown gender {g!r}")
        for s in p["styles"]:
            if s not in self.styles:
                self.errors.append(f"watch {pid}: unknown style {s!r}")
        for m in p.get("merchants", {}):
            if m not in self.merchants:
                self.errors.append(f"watch {pid}: unknown merchant {m!r}")
            url = p["merchants"][m].get("url", "")
            parts = urllib.parse.urlsplit(url)
            if url and (parts.scheme != "https" or not parts.hostname or parts.username or parts.password):
                self.errors.append(f"watch {pid}: merchant {m!r} needs an HTTPS product URL")

    @staticmethod
    def _ready(p):
        if p.get("draft"):
            return False, "draft"
        for key in ("paragraphs", "good", "not_good", "sources"):
            if not p.get(key):
                return False, f"missing {key}"
        return True, ""

    # ---------- shops and affiliate links ----------

    def merchant_links(self, p):
        """List of dicts {label, href, direct}. A product link wins; otherwise a shop search link."""
        out = []
        brand = self.brands[p["brand"]]["name"]
        query = urllib.parse.quote_plus(p.get("query") or f'{brand} {p["model"]} watch')
        listed = p.get("merchants") or {}
        have_direct = any(entry.get("url") for entry in listed.values())
        for key, info in self.merchants.items():
            entry = listed.get(key) or {}
            url = entry.get("url", "")
            direct = bool(url)
            if not url and not have_direct and info.get("search") and (key in listed or key in ("amazon", "flipkart")):
                url = info["search"] + query
            if not url:
                continue
            # Preserve supplied product links exactly, including Amazon's own tracking parameters.
            if not direct and self.affiliate_active and info.get("affiliate_value"):
                parts = urllib.parse.urlsplit(url)
                pairs = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
                         if k != info["affiliate_param"]]
                pairs.append((info["affiliate_param"], info["affiliate_value"]))
                url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path,
                                               urllib.parse.urlencode(pairs), parts.fragment))
            out.append({"label": info["label"], "href": url, "direct": direct})
        return out

    def rel(self):
        return "sponsored nofollow noopener" if self.affiliate_active else "nofollow noopener"

    @staticmethod
    def verb(link):
        return "View on" if link["direct"] else "Search on"

    def check_price(self, p, small=True, include_more=True):
        links = self.merchant_links(p)
        if not links or p.get("sample"):
            return ""
        size = " btn-small" if small else ""
        first = links[0]
        primary = (f'<a class="btn btn-primary{size}" href="{esc(first["href"])}" target="_blank" rel="{self.rel()}" '
                   f'aria-label="{self.verb(first)} {esc(first["label"])} for {esc(p["model"])} (opens in a new tab)">'
                   f'{self.verb(first)} {esc(first["label"])} '
                   '<svg class="ic" aria-hidden="true"><use href="#i-external"/></svg></a>')
        more = ""
        if len(links) > 1 and include_more:
            items = "".join(
                f'<li><a href="{esc(l["href"])}" target="_blank" rel="{self.rel()}" '
                f'aria-label="{self.verb(l)} {esc(l["label"])} for {esc(p["model"])} (opens in a new tab)">'
                f'{esc(l["label"])}</a></li>' for l in links[1:])
            more = f'<details class="more-shops"><summary>More shops</summary><ul>{items}</ul></details>'
        return primary + more

    def has_search_links(self, products):
        return any(not l["direct"] for p in products for l in self.merchant_links(p))

    def cta_note(self, p=None):
        return ""

    # ---------- small components ----------

    def band_label(self, p):
        return self.budgets[p["budget"]]["label"] if p.get("budget") else "Check current price at the retailer"

    @staticmethod
    def primary_gender(p):
        return p["gender"][0]

    def review_url(self, p):
        return f'/watches/products/{p["id"]}/'

    def style_chips(self, p):
        return "".join(f'<li>{esc(self.styles[s]["label"])}</li>' for s in p["styles"])

    def media(self, p):
        if p.get("image"):
            return (f'<img src="{esc(p["image"])}" alt="{esc(self.brands[p["brand"]]["name"])} {esc(p["model"])}" '
                    'loading="lazy" width="480" height="480">')
        return ('<div class="watch-photo-slot watch-spec-preview"><span class="watch-preview-label">Model reference</span>'
                f'<strong>{esc(p.get("model_code", p["model"]))}</strong>'
                f'<span>{esc(p.get("movement", "Analog watch"))}</span>'
                '<span>See product photos at the retailer</span></div>')

    def card(self, p, local=False):
        brand = self.brands[p["brand"]]["name"]
        href = f'#r-{p["id"]}' if local else self.review_url(p)
        band = self.budgets[p["budget"]]["label"] if p.get("budget") in self.budgets else ""
        if p.get("image"):
            media = f'<a class="watch-media" href="{esc(href)}" tabindex="-1" aria-hidden="true">{self.media(p)}</a>'
        else:
            media = (f'<a class="watch-media watch-tile" href="{esc(href)}" tabindex="-1" aria-hidden="true">{watch_art("tile-art")}'
                     f'<span class="tile-brand">{esc(brand)}</span>' + (f'<span class="tile-band">{esc(band)}</span>' if band else "") + '</a>')
        specs = p.get("card_specs") or " · ".join(str(value) for value in (p.get("dial_style"), p.get("strap")) if value)
        return (
            f'<article class="watch-card" data-id="{esc(p["id"])}" data-name="{esc(brand + " " + p["model"])}" data-brand="{esc(p["brand"])}" '
            f'data-gender="{esc(" ".join(p["gender"]))}" data-style="{esc(" ".join(p["styles"]))}" data-budget="{esc(p.get("budget") or "unlisted")}" data-styles="{esc(" ".join(p["styles"]))}" '
            f'data-purpose="{esc(" ".join(p.get("purpose", [])))}" data-water="{esc(self.water_bucket(p))}" data-case="{esc(p.get("case_material", ""))}">'
            + media + '<div class="watch-body">'
            f'<p class="watch-brand">{esc(brand)}</p><h3 class="watch-model"><a href="{esc(href)}">{esc(p["model"])}</a></h3>'
            f'<p class="watch-card-specs">{esc(specs)}</p><p class="watch-verdict">{esc(p["verdict"])}</p>'
            f'<div class="watch-product-bottom"><a class="watch-detail-link" href="{esc(href)}">Product details &rarr;</a>'
            f'<div class="watch-actions">{self.check_price(p, include_more=False)}</div></div></div></article>')

    def grid(self, products, local=False):
        return '<div class="watch-grid" data-watch-grid>\n' + "\n".join(self.card(p, local) for p in products) + "\n</div>"

    def table(self, products, caption="Watch comparison"):
        head = ["Product", "Brand", "Budget list", "Dial style", "Strap material", "Case size",
                "Water resistance", "Best for", "Check Price"]
        ths = "".join(f'<th scope="col" role="columnheader">{h}</th>' for h in head)
        rows = []
        for p in products:
            cells = [
                ("Brand", self.brands[p["brand"]]["name"]), ("Budget list", self.band_label(p)),
                ("Dial style", p.get("dial_style", "Not listed")), ("Strap material", p.get("strap", "Not listed")),
                ("Case size", f'{p["case_size_mm"]} mm' if p.get("case_size_mm") else "Not listed"),
                ("Water resistance", p.get("water_resistance", "Not listed")),
                ("Best for", "Sample" if p.get("sample") else (p.get("best_for") or "Not listed")),
            ]
            tds = "".join(f'<td role="cell" data-label="{esc(l)}">{esc(v)}</td>' for l, v in cells)
            cta = self.check_price(p) or "Not available"
            rows.append(f'<tr role="row" data-id="{esc(p["id"])}"><th scope="row" role="rowheader">{esc(p["model"])}</th>{tds}'
                        f'<td role="cell" data-label="Check Price">{cta}</td></tr>')
        return ('<div class="compare-table-wrap"><table class="compare-table watch-table" role="table">'
                f'<caption class="visually-hidden">{esc(caption)}</caption>'
                f'<thead><tr role="row">{ths}</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')

    def review(self, p):
        brand = self.brands[p["brand"]]["name"]
        good = "".join(f"<li>{esc(x)}</li>" for x in p.get("good", []))
        bad = "".join(f"<li>{esc(x)}</li>" for x in p.get("not_good", []))
        specs = [("Dial style", p.get("dial_style")), ("Strap", p.get("strap")),
                 ("Case size", f'{p["case_size_mm"]} mm' if p.get("case_size_mm") else None),
                 ("Water resistance", p.get("water_resistance"))]
        dl = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in specs if v)
        sample = p.get("sample")
        label = ""
        if sample:
            label = '<span class="rank">Sample</span>'
        elif p.get("best_for"):
            label = f'<span class="rank">{esc(p["best_for"])}</span>'
        sources = ""
        if p.get("sources") and not sample:
            items = "".join(
                f'<li><a href="{esc(s["url"])}" data-source="1" target="_blank" rel="nofollow noopener" '
                f'aria-label="{esc(s["label"])} (opens in a new tab)">{esc(s["label"])}</a></li>' for s in p["sources"])
            sources = f'<details class="watch-sources"><summary>Pages we read</summary><ul>{items}</ul></details>'
        paras = "".join(f"<p>{esc(x)}</p>" for x in p.get("paragraphs", []))
        return (
            f'<div class="watch-review" id="r-{esc(p["id"])}" data-id="{esc(p["id"])}">\n'
            + (f'  <div class="watch-review-media">{self.media(p)}</div>\n' if p.get("image") else '') +
            '  <div class="watch-review-body">\n'
            f'    {label}\n    <h3>{esc(brand)} {esc(p["model"])}</h3>\n'
            f'    <p class="verdict">Verdict: {esc(p["verdict"])}</p>\n    {paras}\n'
            f'    <dl class="spec-list">{dl}</dl>\n'
            f'    <div class="pros-cons"><div class="pros"><h4>Good</h4><ul>{good}</ul></div>'
            f'<div class="cons"><h4>Not so good</h4><ul>{bad}</ul></div></div>\n'
            f'    <div class="cta-row">{self.check_price(p, small=False)}</div>\n    {self.cta_note(p)}\n    {sources}\n'
            '  </div>\n</div>')

    # ---------- filters (inline chips on desktop, bottom sheet on phones) ----------

    def filter_ui(self):
        chips = "".join(
            f'<button type="button" class="chip" data-filter="{esc(s["slug"])}" data-group="{esc(s.get("group", "style"))}" aria-pressed="false">{esc(s["label"])}</button>'
            for s in self.config["styles"])
        return (
            '<div class="filter-bar" data-filters hidden>\n'
            '  <button type="button" class="btn btn-outline btn-small filter-open" data-sheet-open>Filters <span data-filter-badge></span></button>\n'
            f'  <div class="filters-inline" role="group" aria-label="Filter watches">{chips}'
            '<button type="button" class="chip chip-clear" data-filter-clear>Clear</button></div>\n'
            '  <p class="filter-count" role="status" aria-live="polite" data-filter-count></p>\n'
            '</div>\n'
            '<p class="empty-filter" data-filter-empty hidden>No watches match these filters. '
            '<button type="button" class="linklike" data-filter-clear>Clear filters</button></p>\n'
            '<dialog class="sheet" data-sheet aria-labelledby="sheet-title">\n'
            '  <div class="sheet-head"><h2 id="sheet-title">Filters</h2>'
            '<button type="button" class="sheet-close" data-sheet-close>Close</button></div>\n'
            f'  <div class="sheet-chips" role="group" aria-label="Filter watches">{chips}</div>\n'
            '  <div class="sheet-foot"><button type="button" class="btn btn-outline" data-filter-clear>Clear</button>'
            '<button type="button" class="btn btn-primary" data-sheet-close>Show watches</button></div>\n'
            '</dialog>')

    # ---------- shared text ----------

    def affiliate_box(self, products=()):
        return ""  # Full explanation is in the footer; retailer buttons carry a compact paid-link label.

    def method_note(self):
        return ('<aside class="method-note"><svg class="ic" aria-hidden="true"><use href="#i-info"/></svg>'
                "<p><strong>Our research:</strong> we compare published manufacturer specifications. We have not tested these watches ourselves. "
                "Check the exact model, current price and seller policies at the retailer. "
                'Read <a href="/how-we-pick/">how we pick</a>.</p></aside>')

    def empty_state(self, what, level="h2"):
        return (f'<div class="empty-state"><{level}>Choose a watch with confidence</{level}>'
                "<p>Compare case size, movement, strap and warranty before choosing a model. "
                "This page offers selection advice rather than a product shortlist.</p>"
                '<p><a href="/watches/guide/">Read the watch buying guide</a> &middot; '
                '<a href="/sports-fitness/#guides">Explore published sports and fitness guides</a></p></div>')

    SIZE = {
        "men": "Many men's dress watches have a case of about 36 to 42 mm. Pick by wrist size: a smaller case suits a slim wrist.",
        "women": "Many women's dress watches have a case of about 24 to 34 mm. A smaller case looks neat on a slim wrist, while a slightly larger one is easier to read.",
    }

    def short_guide(self, gender=None, budget=None):
        size = self.SIZE.get(gender, "Match the case size to your wrist, not to a trend.")
        expect = self.budgets[budget]["expect"] if budget else "Set a budget first, then compare dial, strap and warranty within it."
        return ('<h2>Buying guide</h2>\n'
                f'<p><strong>What to expect from this budget.</strong> {esc(expect)}</p>\n'
                f'<p><strong>Case size.</strong> {esc(size)}</p>\n'
                '<p>For quartz versus automatic, strap choice, glass and water resistance, read our <a href="/watches/guide/">full watch buying guide</a>.</p>')

    def faq(self, gender=None, budget=None, products=()):
        size = self.SIZE.get(gender, "Match the case size to your wrist, not to a trend.")
        expect = self.budgets[budget]["expect"] if budget else "That depends on the budget. Compare dial, strap and warranty within it."
        who = {"men": "men", "women": "women"}.get(gender, "most people")
        qa = [
            ("What should I expect from a watch in this budget?", expect),
            (f"What case size suits {who}?", size),
            ("How do I tell a real watch from a fake?", "Buy from the brand's own store or an authorised seller. Be careful with listings that are far cheaper than others, and check the warranty card."),
        ]
        if products:
            if self.has_search_links(products):
                qa.append(("Why do the buttons say Search on a shop?", "Prices and stock change often, so we do not copy them here. The button opens the shop's search page so you can see today's price."))
            else:
                qa.append(("Why do the buttons say Check Price?", "Prices change often, so we do not copy them here. The button opens the shop so you can see today's price."))
        else:
            qa.append(("Is a classic watch the same as an analog watch?", "Mostly yes. Analog means the time is shown with hands. Classic describes the look: a simple round dial, clear markers and a plain strap."))
        items = "".join(
            f'<details class="faq-item"><summary><h3>{esc(q)}</h3><span class="faq-chev" aria-hidden="true"></span></summary><p>{esc(a)}</p></details>'
            for q, a in qa)
        return f'<h2>Common questions</h2>\n{items}'

    @staticmethod
    def related(links):
        if not links:
            return ""
        items = "".join(f'<li><a href="{esc(h)}">{esc(t)}</a></li>' for t, h in links)
        return f'<h2>More watch guides</h2>\n<ul class="related-links">{items}</ul>'

    def updated(self, products):
        dates = [p.get("updated", self.config_updated) for p in products]
        return max(dates) if dates else self.config_updated

    # ---------- page assembly ----------

    def _meta(self, url, title, description, body, crumbs, products, noindex=None, js=True):
        meta = {
            "url": url, "title": title, "description": description,
            "css": ["buttons", "breadcrumb", "content-page", "compare-table", "faq", "product-block",
                    "category-chips", "method-note", "watches"],
            "js": ["watch-filters"] if js else [],
            "theme": "watches", "breadcrumbs": crumbs, "updated": self.updated(products),
            "_slug": ("watches" + url.rstrip("/").replace("/watches", "").replace("/", "-")),
            "_body": body,
        }
        meta["noindex"] = (len(products) < self.min_index) if noindex is None else noindex
        return meta

    def _picks_block(self, products):
        has_rank = any("rank" in p for p in products)
        out = ('<h2>Our top picks</h2>\n' if has_rank else '<h2>Watches in this list</h2>\n') + self.grid(products[:3], local=True)
        if len(products) > 3:
            out += '\n<h2>More watches</h2>\n' + self.grid(products[3:], local=True)
        return out

    def _listing_body(self, h1, intro, products, what, gender=None, budget=None, related=()):
        if products:
            sections = (self._picks_block(products) + '\n<h2>Compare</h2>\n' + self.table(products, h1) +
                        '\n<h2>Reviews</h2>\n' + "\n".join(self.review(p) for p in products))
            filters, note = self.filter_ui(), self.method_note()
        else:
            sections, filters, note = self.empty_state(what), "", ""
        return (
            '<section class="section">\n  <div class="container content-page watch-page">\n'
            f'    {{{{breadcrumb}}}}\n    <h1>{esc(h1)}</h1>\n    <p class="lead">{esc(intro)}</p>\n'
            f'    {note}\n    {filters}\n    {sections}\n    {self.short_guide(gender, budget)}\n'
            f'    {self.faq(gender, budget, products)}\n    {self.related(related)}\n    {self.affiliate_box(products)}\n  </div>\n</section>')

    def _sibling_links(self, gender=None, budget=None, brand=None, style=None):
        links = []
        if gender:
            for b in self.config["budgets"]:
                if b["slug"] != budget:
                    links.append((f'{self.genders[gender]["label"]} watches {b["label"].lower()}', f"/watches/{gender}/{b['slug']}/"))
            other = [g for g in self.genders if g != gender][0]
            if budget:
                links.append((f'{self.genders[other]["label"]} watches {self.budgets[budget]["label"].lower()}', f"/watches/{other}/{budget}/"))
        for b in self.config["brands"][:4]:
            if b["slug"] != brand:
                links.append((f'{b["name"]} watches', f'/watches/brands/{b["slug"]}/'))
        for s in self.config["styles"][:3]:
            if s["slug"] != style:
                links.append((f'{s["label"]} watches', f'/watches/style/{s["slug"]}/'))
        links.append(("Watch buying guide", "/watches/guide/"))
        return links

    PURPOSES = [("casual", "Casual Wear"), ("formal", "Formal Wear"), ("swimming", "Swimming"), ("hiking", "Hiking"), ("running", "Running")]
    WATER = [("up-to-29", "Up to 29 m", 0, 29), ("30-40", "30 to 40 m", 30, 40), ("41-51", "41 to 51 m", 41, 51), ("52-plus", "52 m and above", 52, 10 ** 6)]
    CASES = [("alloy-steel", "Alloy Steel"), ("brass", "Brass"), ("metal", "Metal"), ("plastic", "Plastic"), ("polycarbonate", "Polycarbonate"),
             ("resin", "Resin"), ("stainless-steel", "Stainless Steel")]

    @staticmethod
    def water_metres(p):
        """Depth in metres from the stated water resistance ("50 m", "5 ATM", "10 ATM"); None when it is not stated."""
        text = str(p.get("water_resistance", ""))
        m = re.search(r"(\d+(?:\.\d+)?)\s*(m|metres|meters|atm|bar)\b", text, re.I)
        if not m:
            return None
        n = float(m.group(1))
        return n * 10 if m.group(2).lower() in ("atm", "bar") else n

    def water_bucket(self, p):
        n = self.water_metres(p)
        return next((slug for slug, _, lo, hi in self.WATER if n is not None and lo <= n <= hi), "")

    def catalog(self, url, title, intro, *, gender="", brand="", budget="", style="", crumbs=None):
        products = self.products
        def matches(p):
            return ((not gender or gender in p["gender"]) and (not brand or p["brand"] == brand)
                    and (not budget or p.get("budget") == budget) and (not style or style in p["styles"]))
        shown = [p for p in products if matches(p)]
        def n(pred):
            return sum(1 for p in products if pred(p))
        groups = [
            {"key": "brand", "title": "Brand", "checked": [brand] if brand else [], "show_empty": True,
             "items": [(slug, value["name"], n(lambda p, s=slug: p["brand"] == s)) for slug, value in self.brands.items() if slug != "sample"]},
            {"key": "budget", "title": "Price", "checked": [budget] if budget else [],
             "items": [(slug, value["label"], n(lambda p, s=slug: p.get("budget") == s)) for slug, value in self.budgets.items() if n(lambda p, s=slug: p.get("budget") == s)]
                      + ([("unlisted", "Price at retailer", n(lambda p: not p.get("budget")))] if n(lambda p: not p.get("budget")) else [])},
            {"key": "purpose", "title": "Purpose", "checked": [],
             "items": [(slug, label, n(lambda p, s=slug: s in p.get("purpose", []))) for slug, label in self.PURPOSES if n(lambda p, s=slug: s in p.get("purpose", []))]},
            {"key": "water", "title": "Water resistance depth", "checked": [],
             "items": [(slug, label, n(lambda p, s=slug: self.water_bucket(p) == s)) for slug, label, lo, hi in self.WATER if n(lambda p, s=slug: self.water_bucket(p) == s)]},
            {"key": "case", "title": "Case material", "checked": [],
             "items": [(slug, label, n(lambda p, s=slug: p.get("case_material") == s)) for slug, label in self.CASES if n(lambda p, s=slug: p.get("case_material") == s)]},
            {"key": "style", "title": "Style", "checked": [style] if style else [],
             "items": [(slug, value["label"], n(lambda p, s=slug: s in p["styles"])) for slug, value in self.styles.items()]},
        ]
        style_links = '<a class="watch-style" href="/watches/" data-style-toggle="" aria-current="false"><span class="style-dot" aria-hidden="true">' + watch_art("style-art") + '</span><span>All styles</span></a>'
        for slug, value in self.styles.items():
            style_links += (f'<a class="watch-style" href="/watches/style/{slug}/" data-style-toggle="{esc(slug)}" aria-current="false">'
                            f'<span class="style-dot style-{esc(slug)}" aria-hidden="true">{watch_art("style-art")}</span><span>{esc(value["label"])}</span></a>')
        quick = ""
        top = ('<div class="watch-discovery"><div class="watch-style-head"><h2>Shop by style</h2><a href="/watches/guide/">Buying guide &rarr;</a></div>'
               f'<nav class="watch-style-row" aria-label="Watch styles">{style_links}</nav>'
               f'<div class="watch-quick-row" data-quick-controls hidden>{quick}'
               '<button type="button" class="btn btn-outline btn-small collection-filter-open" data-filter-open aria-haspopup="dialog" aria-controls="watch-collection-filters">Filters <span data-filter-badge></span></button></div></div>')
        top = top.replace(f'data-style-toggle="{esc(style)}" aria-current="false"', f'data-style-toggle="{esc(style)}" aria-current="true"', 1)
        block = collection.render([self.card(p) for p in products], groups, uid="watch-collection", title="Explore watches", noun="watch", plural="watches",
                                  preset_gender=gender, genders=[("", "All watches"), ("men", "Men"), ("women", "Women")],
                                  top_html=top, visible=[matches(p) for p in products], page_size=24)
        body = ('<section class="section watch-store"><div class="container watch-store-inner">{{breadcrumb}}'
                f'<header class="watch-store-head"><div><p class="watch-kicker">The SAT watch edit</p><h1>{esc(title)}</h1><p>{esc(intro)}</p></div>'
                '<a class="watch-guide-link" href="/watches/guide/">Find your fit &rarr;</a></header>' + block + '<noscript><nav class="watch-static-links" aria-label="Browse watches"><a href="/watches/men/">Men</a> · <a href="/watches/women/">Women</a> · ' + ' · '.join(f'<a href="/watches/brands/{esc(slug)}/">{esc(value["name"])}</a>' for slug, value in self.brands.items() if slug != 'sample') + '</nav></noscript></div></section>')
        meta = self._meta(url, title, intro, body, crumbs or [["Watches", "/watches/"]], shown, js=False)
        meta["css"] += ["collection", "watch-store"]
        meta["js"] = ["collection"]
        return meta

    def budget_page(self, gender, budget):
        g, b = self.genders[gender], self.budgets[budget]
        url = f"/watches/{gender}/{budget}/"
        title = f'{g["label"]} Watches {b["label"]}'
        return self.catalog(url, title, "Compare styles and published details. Confirm the current price with the retailer.", gender=gender, budget=budget,
                            crumbs=[["Watches", "/watches/"], [g["label"], f"/watches/{gender}/"], [b["label"], url]])

    def brand_page(self, slug):
        br = self.brands[slug]
        url = f"/watches/brands/{slug}/"
        meta = self.catalog(url, br["name"] + " Watches", "Explore the collection by style and budget. Read the details before you choose.", brand=slug,
                            crumbs=[["Watches", "/watches/"], [br["name"], url]])
        # Keep old product and gender anchors reachable after introducing dedicated detail pages.
        anchors = ''.join(f'<span id="r-{esc(p["id"])}"></span>' for p in self.products if p["brand"] == slug)
        anchors += '<span id="men"></span><span id="women"></span>'
        meta["_body"] = meta["_body"].replace('<header class="watch-store-head">', anchors + '<header class="watch-store-head">', 1)
        return meta

    def style_page(self, slug):
        st = self.styles[slug]
        url = f"/watches/style/{slug}/"
        return self.catalog(url, st["label"] + " Watches", "Find a style for your everyday, workdays and special occasions.", style=slug,
                            crumbs=[["Watches", "/watches/"], [st["label"], url]])

    def gender_page(self, gender):
        g = self.genders[gender]
        url = f"/watches/{gender}/"
        return self.catalog(url, g["label"] + " Watches", "Explore watches by style, brand and budget. Choose what suits you.", gender=gender,
                            crumbs=[["Watches", "/watches/"], [g["label"], url]])

    def landing(self):
        return self.catalog("/watches/", "Watches for every day.", "Classic style. Everyday usefulness. Find a watch that feels like you.")

    def product_page(self, p):
        brand = self.brands[p["brand"]]["name"]
        url = self.review_url(p)
        title = brand + " " + p["model"]
        body = ('<section class="section"><div class="container content-page watch-page watch-product-page">{{breadcrumb}}'
                f'<h1>{esc(title)}</h1>' + self.review(p) +
                '<p><a class="btn btn-outline" href="/watches/">Explore all watches &rarr;</a></p></div></section>')
        meta = self._meta(url, title, p["verdict"], body, [["Watches", "/watches/"], [brand, f'/watches/brands/{p["brand"]}/'], [p["model"], url]], [p], js=False)
        meta["css"].append("watch-store")
        return meta

    def guide_page(self):
        """One canonical, genuinely useful buying guide that every watch page links to."""
        items = [
            ("Quartz or automatic", "Most watches in these budgets use quartz movements. They run on a battery, keep good time and need little care. Automatic watches wind themselves from wrist movement and are usually found at higher budgets."),
            ("Dial and glass", "A plain dial with clear numbers or markers is easy to read and easy to match with clothes. Check what the glass is made of on the listing."),
            ("Strap: leather or metal", "Leather straps look warmer and softer, but they need to be kept away from water. A good steel bracelet usually lasts longer and copes better with sweat. Check the material on the listing, because plated bracelets can wear off."),
            ("Case size", f'{self.SIZE["men"]} {self.SIZE["women"]}'),
            ("Water resistance", "Marks such as 30 m or 3 ATM mean the watch can handle splashes and rain. They do not mean it is safe for swimming or the shower. Read the maker's own note."),
            ("Warranty and returns", "Check the warranty and the return window on the exact listing, and buy from the brand's own store or an authorised seller. Fake watches are sold on marketplaces."),
            ("Classic or analog", "Analog means the time is shown with hands. Classic describes the look: a simple round dial, clear markers and a plain strap. This section covers both, and it does not cover smartwatches or digital watches."),
        ]
        body_items = "\n".join(f'    <h2>{esc(h)}</h2>\n    <p>{esc(t)}</p>' for h, t in items)
        rel = self.related([("Watches for men", "/watches/men/"), ("Watches for women", "/watches/women/"), ("How we pick", "/how-we-pick/")])
        body = (
            '<section class="section">\n  <div class="container content-page narrow watch-page">\n'
            '    {{breadcrumb}}\n    <h1>Classic Watch Buying Guide</h1>\n'
            '    <p class="lead">Seven things to check before you buy a classic analog watch in India.</p>\n'
            f'{body_items}\n    {rel}\n    {self.affiliate_box()}\n  </div>\n</section>')
        return self._meta("/watches/guide/", "Classic Watch Buying Guide for India",
                          "Seven things to check before you buy a classic analog watch: movement, glass, strap, case size, water resistance and warranty.",
                          body, [["Watches", "/watches/"], ["Buying guide", "/watches/guide/"]], [], noindex=False, js=False)

    def preview(self):
        """A noindex page that shows the templates with clearly labelled sample data."""
        samples = self.samples
        if not samples:
            return None
        body = (
            '<section class="section">\n  <div class="container content-page watch-page">\n'
            '    {{breadcrumb}}\n    <h1>Template preview</h1>\n'
            '    <p class="lead">This page shows the watch templates with <strong>sample content</strong>. None of these are real watches, and nothing here is a recommendation.</p>\n'
            f'    {self.filter_ui()}\n    <h2>Watches in this list</h2>\n{self.grid(samples, local=True)}\n    <h2>Compare</h2>\n{self.table(samples, "Sample comparison")}\n'
            '    <h2>Reviews</h2>\n' + "\n".join(self.review(p) for p in samples) +
            f'\n    {self.short_guide("men", "under-3000")}\n    {self.faq("men", "under-3000", samples)}\n    {self.affiliate_box()}\n  </div>\n</section>')
        return self._meta("/watches/preview/", "Watch Template Preview", "Sample content showing the watch page templates. Not real products.", body,
                          [["Watches", "/watches/"], ["Template preview", "/watches/preview/"]], [], noindex=True)

    def pages(self):
        out = [self.landing(), self.guide_page()] + [self.product_page(p) for p in self.products]
        for g in self.genders:
            out.append(self.gender_page(g))
            for b in self.budgets:
                out.append(self.budget_page(g, b))
        for b in self.config["brands"]:
            out.append(self.brand_page(b["slug"]))
        for s in self.styles:
            out.append(self.style_page(s))
        prev = self.preview()
        if prev:
            out.append(prev)
        return out
