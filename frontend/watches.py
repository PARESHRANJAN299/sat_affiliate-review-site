"""Watches section: pages generated from data (src/watches/*).

Everything is driven by three kinds of files, so new brands, budgets, styles, products
and shops can be added without touching this code:

    src/watches/config.json     genders, budgets, brands, styles
    src/watches/merchants.json  shops (Amazon, Flipkart, brand store, other)
    src/watches/products/*.json one file per watch (see src/watches/README.md)

With no products, every page shows an honest "being researched" state and is set to
noindex. A page becomes indexable once it has at least `min_products_to_index` watches.
Standard library only.
"""
import html
import json
import math
import re
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


# ---------- data loading ----------

def load_data(src):
    base = Path(src) / "watches"
    config = json.loads((base / "config.json").read_text(encoding="utf-8"))
    merchants = json.loads((base / "merchants.json").read_text(encoding="utf-8"))
    products = []
    for p in sorted((base / "products").glob("*.json")):
        products.append(json.loads(p.read_text(encoding="utf-8")))
    samples = []
    for p in sorted((base / "_sample").glob("*.json")):
        samples.append(json.loads(p.read_text(encoding="utf-8")))
    return config, merchants, products, samples


class Watches:
    def __init__(self, src, site_config):
        self.config, self.merchants, self.products, self.samples = load_data(src)
        self.site = site_config
        self.budgets = {b["slug"]: b for b in self.config["budgets"]}
        self.brands = {b["slug"]: b for b in self.config["brands"]}
        self.styles = {s["slug"]: s for s in self.config["styles"]}
        self.genders = {g["slug"]: g for g in self.config["genders"]}
        self.min_index = self.config.get("min_products_to_index", 3)
        self.affiliate_active = bool(site_config.get("affiliate_active"))
        if self.samples:
            self.brands["sample"] = {"name": "Sample brand", "slug": "sample", "genders": ["men"], "line": "Classic"}
        self.errors = []
        self._validate()

    # --- validation so a bad product file fails the build, not the page ---
    def _validate(self):
        seen = set()
        for p in self.products:
            pid = p.get("id", "?")
            if pid in seen:
                self.errors.append(f"watch {pid}: duplicate id")
            seen.add(pid)
            for key in ("id", "brand", "model", "gender", "budget", "styles", "verdict"):
                if key not in p:
                    self.errors.append(f"watch {pid}: missing {key}")
            if p.get("brand") not in self.brands:
                self.errors.append(f"watch {pid}: unknown brand {p.get('brand')!r}")
            if p.get("budget") not in self.budgets:
                self.errors.append(f"watch {pid}: unknown budget {p.get('budget')!r}")
            for g in p.get("gender", []):
                if g not in self.genders:
                    self.errors.append(f"watch {pid}: unknown gender {g!r}")
            for s in p.get("styles", []):
                if s not in self.styles:
                    self.errors.append(f"watch {pid}: unknown style {s!r}")
            for m in p.get("merchants", {}):
                if m not in self.merchants:
                    self.errors.append(f"watch {pid}: unknown merchant {m!r}")

    # ---------- shops and affiliate links ----------

    def merchant_links(self, p):
        """[(label, href)] for every shop this watch has. A product link wins; otherwise a shop search link."""
        out = []
        brand = self.brands[p["brand"]]["name"]
        query = urllib.parse.quote_plus(p.get("query") or f'{brand} {p["model"]} watch')
        listed = p.get("merchants") or {}
        for key, info in self.merchants.items():
            entry = listed.get(key) or {}
            url = entry.get("url", "")
            if not url and info.get("search") and (key in listed or key in ("amazon", "flipkart")):
                url = info["search"] + query
            if not url:
                continue
            if self.affiliate_active and info.get("affiliate_value"):
                joiner = "&" if "?" in url else "?"
                url = f'{url}{joiner}{info["affiliate_param"]}={urllib.parse.quote(info["affiliate_value"])}'
            out.append((info["label"], url))
        return out

    def rel(self):
        return "sponsored nofollow noopener" if self.affiliate_active else "nofollow noopener"

    def check_price(self, p, small=True):
        links = self.merchant_links(p)
        if not links:
            return ""
        size = " btn-small" if small else ""
        first_label, first_href = links[0]
        label = f"Check Price on {esc(first_label)}"
        primary = (f'<a class="btn btn-primary{size}" href="{esc(first_href)}" target="_blank" rel="{self.rel()}" '
                   f'aria-label="{label} for {esc(p["model"])} (opens in a new tab)">{label} '
                   '<svg class="ic" aria-hidden="true"><use href="#i-external"/></svg></a>')
        more = ""
        if len(links) > 1:
            items = "".join(
                f'<li><a href="{esc(h)}" target="_blank" rel="{self.rel()}">{esc(l)}</a></li>' for l, h in links[1:])
            more = f'<details class="more-shops"><summary>More shops</summary><ul>{items}</ul></details>'
        return primary + more

    def cta_note(self):
        if self.affiliate_active:
            return '<p class="cta-note"><strong>Affiliate links.</strong> We may earn a commission if you buy, at no extra cost to you.</p>'
        return '<p class="cta-note">Opens a search on the shop. We do not sell watches or take payments.</p>'

    # ---------- small components ----------

    def band_label(self, p):
        return self.budgets[p["budget"]]["label"]

    def style_chips(self, p):
        return "".join(f'<li>{esc(self.styles[s]["label"])}</li>' for s in p["styles"])

    def media(self, p):
        if p.get("image"):
            return f'<img src="{esc(p["image"])}" alt="{esc(self.brands[p["brand"]]["name"])} {esc(p["model"])}" loading="lazy" width="480" height="480">'
        return f'<div class="watch-photo-slot">{watch_art()}<span>Photo coming</span></div>'

    def card(self, p):
        brand = self.brands[p["brand"]]["name"]
        strap = "leather-strap" if "leather-strap" in p["styles"] else ("metal-strap" if "metal-strap" in p["styles"] else "")
        sample = '<span class="sample-flag">Sample</span>' if p.get("sample") else ""
        return (
            f'<article class="watch-card" id="{esc(p["id"])}" data-styles="{esc(" ".join(p["styles"]))}" data-strap="{strap}">\n'
            f'  <div class="watch-media">{sample}{self.media(p)}</div>\n'
            '  <div class="watch-body">\n'
            f'    <p class="watch-brand">{esc(brand)}</p>\n'
            f'    <h3 class="watch-model">{esc(p["model"])}</h3>\n'
            f'    <p class="watch-band">{esc(self.band_label(p))}</p>\n'
            f'    <p class="watch-verdict">{esc(p["verdict"])}</p>\n'
            f'    <ul class="tag-chips">{self.style_chips(p)}</ul>\n'
            '    <div class="rating-slot" aria-hidden="true"></div>\n'
            '    <div class="watch-actions">\n'
            f'      <a class="btn btn-outline btn-small" href="#r-{esc(p["id"])}">View Details</a>\n'
            f'      {self.check_price(p)}\n'
            '    </div>\n'
            '  </div>\n'
            '</article>')

    def grid(self, products):
        return '<div class="watch-grid" data-watch-grid>\n' + "\n".join(self.card(p) for p in products) + "\n</div>"

    def table(self, products):
        head = ["Product", "Brand", "Budget band", "Dial style", "Strap material", "Case size", "Water resistance", "Best for", "Check Price"]
        ths = "".join(f'<th scope="col" role="columnheader">{h}</th>' for h in head)
        rows = []
        for p in products:
            cells = [
                ("Brand", self.brands[p["brand"]]["name"]), ("Budget band", self.band_label(p)),
                ("Dial style", p.get("dial_style", "Not listed")), ("Strap material", p.get("strap", "Not listed")),
                ("Case size", f'{p["case_size_mm"]} mm' if p.get("case_size_mm") else "Not listed"),
                ("Water resistance", p.get("water_resistance", "Not listed")), ("Best for", p.get("best_for", "")),
            ]
            tds = "".join(f'<td role="cell" data-label="{esc(l)}">{esc(v)}</td>' for l, v in cells)
            cta = self.check_price(p) or "Not available"
            rows.append(f'<tr role="row"><th scope="row" role="rowheader">{esc(p["model"])}</th>{tds}'
                        f'<td role="cell" data-label="Check Price">{cta}</td></tr>')
        return ('<div class="compare-table-wrap"><table class="compare-table watch-table" role="table">'
                '<caption class="visually-hidden">Watch comparison</caption>'
                f'<thead><tr role="row">{ths}</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div>')

    def review(self, p):
        brand = self.brands[p["brand"]]["name"]
        good = "".join(f"<li>{esc(x)}</li>" for x in p.get("good", []))
        bad = "".join(f"<li>{esc(x)}</li>" for x in p.get("not_good", []))
        specs = [("Dial style", p.get("dial_style")), ("Strap", p.get("strap")),
                 ("Case size", f'{p["case_size_mm"]} mm' if p.get("case_size_mm") else None),
                 ("Water resistance", p.get("water_resistance")), ("Budget band", self.band_label(p))]
        dl = "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in specs if v)
        label = f'<span class="rank">{esc(p["best_for"])}</span>' if p.get("best_for") else ""
        sources = ""
        if p.get("sources"):
            items = "".join(f'<li><a href="{esc(s["url"])}" target="_blank" rel="nofollow noopener">{esc(s["label"])}</a></li>' for s in p["sources"])
            sources = f'<details class="watch-sources"><summary>Pages we read</summary><ul>{items}</ul></details>'
        paras = "".join(f"<p>{esc(x)}</p>" for x in p.get("paragraphs", []))
        return (
            f'<div class="watch-review" id="r-{esc(p["id"])}">\n'
            f'  <div class="watch-review-media">{self.media(p)}</div>\n'
            '  <div class="watch-review-body">\n'
            f'    {label}\n    <h3>{esc(brand)} {esc(p["model"])}</h3>\n'
            f'    <p class="verdict">Verdict: {esc(p["verdict"])}</p>\n    {paras}\n'
            f'    <dl class="spec-list">{dl}</dl>\n'
            f'    <div class="pros-cons"><div class="pros"><h4>Good</h4><ul>{good}</ul></div>'
            f'<div class="cons"><h4>Not so good</h4><ul>{bad}</ul></div></div>\n'
            f'    <div class="cta-row">{self.check_price(p, small=False)}</div>\n    {self.cta_note()}\n    {sources}\n'
            '  </div>\n</div>')

    # ---------- filters (inline chips on desktop, bottom sheet on phones) ----------

    def filter_ui(self):
        chips = "".join(
            f'<button type="button" class="chip" data-filter="{esc(s["slug"])}" data-group="{esc(s.get("group", "style"))}" aria-pressed="false">{esc(s["label"])}</button>'
            for s in self.config["styles"])
        return (
            '<div class="filter-bar" data-filters hidden>\n'
            '  <button type="button" class="btn btn-outline btn-small filter-open" data-sheet-open>Filters</button>\n'
            f'  <div class="filters-inline" role="group" aria-label="Filter watches">{chips}</div>\n'
            '  <p class="filter-count" role="status" aria-live="polite" data-filter-count></p>\n'
            '</div>\n'
            '<dialog class="sheet" data-sheet aria-labelledby="sheet-title">\n'
            '  <div class="sheet-head"><h2 id="sheet-title">Filters</h2>'
            '<button type="button" class="sheet-close" data-sheet-close aria-label="Close filters">Close</button></div>\n'
            f'  <div class="sheet-chips" role="group" aria-label="Filter watches">{chips}</div>\n'
            '  <div class="sheet-foot"><button type="button" class="btn btn-outline" data-filter-clear>Clear</button>'
            '<button type="button" class="btn btn-primary" data-sheet-close>Show watches</button></div>\n'
            '</dialog>')

    # ---------- shared text ----------

    def affiliate_box(self):
        if self.affiliate_active:
            text = "Some links on this page are affiliate links. We may earn a commission if you buy, at no extra cost to you. It does not change which watches we pick."
        else:
            text = "Our shop buttons are plain links to each shop's search page today, and they earn us nothing. If that changes, we will say so here first."
        return ('<aside class="affiliate-box" id="affiliate-note"><svg class="ic" aria-hidden="true"><use href="#i-info"/></svg>'
                f'<p><strong>Affiliate disclosure.</strong> {esc(text)} <a href="/affiliate-disclosure/">Read the full disclosure</a>.</p></aside>')

    def empty_state(self, what):
        return ('<div class="empty-state"><h2>' + esc(what) + ' is being researched</h2>'
                "<p>We add a watch only after we have read the maker's page and the shop listings. "
                "This page will show top picks, a comparison table and short reviews once it has at least "
                f"{self.min_index} watches. Until then, the buying guide below still applies.</p>"
                '<p><a href="/how-we-pick/">How we pick</a></p></div>')

    def buying_guide(self, gender=None, budget=None):
        size = {
            "men": "Many men's dress watches have a case of about 36 to 42 mm. Pick by wrist size: a smaller case suits a slim wrist.",
            "women": "Many women's dress watches have a case of about 24 to 34 mm. A smaller case looks neat on a slim wrist, while a slightly larger one is easier to read.",
        }.get(gender, "Case size matters more than most buyers expect. Match it to your wrist, not to a trend.")
        expect = self.budgets[budget]["expect"] if budget else "Set a budget first, then compare dial, strap and warranty within it."
        items = [
            ("What to expect from this budget", expect),
            ("Quartz or automatic", "Most watches in these budgets use quartz movements. They run on a battery, keep good time and need little care. Automatic watches wind themselves from wrist movement and are usually found at higher budgets."),
            ("Dial and glass", "A plain dial with clear numbers or markers is easy to read and easy to match with clothes. Check what the glass is made of on the listing."),
            ("Strap: leather or metal", "Leather straps look warmer and softer. Metal bracelets last longer and cope better with sweat. Leather should be kept away from water."),
            ("Case size", size),
            ("Water resistance", "Marks such as 30 m or 3 ATM mean the watch can handle splashes and rain. They do not mean it is safe for swimming or the shower. Read the maker's own note."),
            ("Warranty and returns", "Check the warranty and the return window on the exact listing, and buy from the brand's own store or an authorised seller. Fake watches are sold on marketplaces."),
        ]
        body = "".join(f"<p><strong>{esc(h)}.</strong> {esc(t)}</p>" for h, t in items)
        return f'<h2>Buying guide</h2>\n{body}'

    def faq(self):
        qa = [
            ("Is a classic watch the same as an analog watch?", "Mostly yes. Analog means the time is shown with hands. Classic describes the look: a simple round dial, clear markers and a plain strap. We focus on both."),
            ("Do I need a smartwatch instead?", "That depends on you. This section covers classic and analog watches only. A classic watch needs no charging and suits formal clothes."),
            ("How do I tell a real watch from a fake?", "Buy from the brand's own store or an authorised seller. Be careful with listings that are far cheaper than others, and check the warranty card."),
            ("Why do the buttons say Check Price?", "Prices change often, so we do not copy them here. The button opens the shop so you can see today's price."),
        ]
        items = "".join(
            f'<details class="faq-item"><summary><h3>{esc(q)}</h3><span class="faq-chev" aria-hidden="true"></span></summary><p>{esc(a)}</p></details>'
            for q, a in qa)
        return f'<h2>Common questions</h2>\n{items}'

    # ---------- page builders ----------

    def _meta(self, url, title, description, body, crumbs, count, noindex=None, js=True):
        low = count < self.min_index
        meta = {
            "url": url, "title": title, "description": description,
            "css": ["buttons", "breadcrumb", "content-page", "compare-table", "faq", "product-block", "category-chips", "watches"],
            "js": ["watch-filters"] if js else [],
            "theme": "watches", "breadcrumbs": crumbs, "updated": "2026-10-15",
            "_slug": "watches" + url.rstrip("/").replace("/watches", "").replace("/", "-"),
            "_body": body,
        }
        meta["noindex"] = low if noindex is None else noindex
        return meta

    def _listing_body(self, h1, intro, products, what, gender=None, budget=None, crumbs_html="{{breadcrumb}}", extra_top=""):
        if products:
            top = products[:3]
            sections = (
                '<h2>Our top picks</h2>\n' + self.grid(top) +
                ('<h2>All watches</h2>\n' + self.grid(products[3:]) if len(products) > 3 else "") +
                '<h2>Compare</h2>\n' + self.table(products) +
                '<h2>Reviews</h2>\n' + "\n".join(self.review(p) for p in products))
            filters = self.filter_ui()
        else:
            sections = self.empty_state(what)
            filters = ""
        return (
            '<section class="section">\n  <div class="container content-page watch-page">\n'
            f'    {crumbs_html}\n    <h1>{esc(h1)}</h1>\n    <p class="lead">{esc(intro)}</p>\n'
            f'    {extra_top}\n    {filters}\n    {sections}\n    {self.buying_guide(gender, budget)}\n'
            f'    {self.faq()}\n    {self.affiliate_box()}\n  </div>\n</section>')

    def budget_page(self, gender, budget):
        g, b = self.genders[gender], self.budgets[budget]
        prods = [p for p in self.products if gender in p["gender"] and p["budget"] == budget]
        h1 = f'Best Classic Watches for {g["adjective"].capitalize()} {b["label"]}'
        intro = (f"A short list of classic analog watches for {g['adjective']} in this budget. "
                 "We choose by dial, strap, case size and warranty, and we say what we could not confirm.")
        url = f"/watches/{gender}/{budget}/"
        crumbs = [["Watches", "/watches/"], [f"{g['label']} watches", f"/watches/{gender}/"], [b["label"], url]]
        body = self._listing_body(h1, intro, prods, f"The {g['label'].lower()} {b['label'].lower()} list", gender, budget)
        return self._meta(url, h1, f"Classic analog watches for {g['adjective']} {b['label'].lower()}, with a buying guide and a comparison. Research-based.", body, crumbs, len(prods))

    def brand_page(self, slug):
        br = self.brands[slug]
        url = f"/watches/brands/{slug}/"
        all_p = [p for p in self.products if p["brand"] == slug]
        blocks = []
        for gender in br["genders"]:
            prods = [p for p in all_p if gender in p["gender"]]
            title = f'Best {br["name"]} {br["line"]} Watches for {self.genders[gender]["adjective"].capitalize()}'
            if prods:
                blocks.append(f'<h2>{esc(title)}</h2>\n' + self.grid(prods[:6]) + "\n" + self.table(prods) + "\n" + "\n".join(self.review(p) for p in prods))
            else:
                blocks.append(f'<h2>{esc(title)}</h2>\n' + self.empty_state(title))
        h1 = f'{br["name"]} {br["line"]} Watches'
        body = (
            '<section class="section">\n  <div class="container content-page watch-page">\n'
            f'    {{{{breadcrumb}}}}\n    <h1>{esc(h1)}</h1>\n    <p class="lead">{esc(br["blurb"])}</p>\n'
            + (self.filter_ui() if all_p else "") + "\n" + "\n".join(blocks) + "\n"
            f'    {self.buying_guide()}\n    {self.faq()}\n    {self.affiliate_box()}\n  </div>\n</section>')
        crumbs = [["Watches", "/watches/"], ["Brands", "/watches/"], [br["name"], url]]
        return self._meta(url, f'Best {br["name"]} {br["line"]} Watches in India', f'{br["name"]} {br["line"].lower()} watches picked for Indian buyers, with a buying guide. Research-based, no prices copied.', body, crumbs, len(all_p))

    def style_page(self, slug):
        st = self.styles[slug]
        url = f"/watches/style/{slug}/"
        prods = [p for p in self.products if slug in p["styles"]]
        h1 = f'Best {st["label"]} Watches in India'
        body = self._listing_body(h1, f'{st["label"]} watches from our guides, across budgets and brands.', prods, f'The {st["label"].lower()} watch list')
        crumbs = [["Watches", "/watches/"], [st["label"], url]]
        return self._meta(url, h1, f'{st["label"]} classic and analog watches for Indian buyers, with a buying guide.', body, crumbs, len(prods))

    def gender_page(self, gender):
        g = self.genders[gender]
        url = f"/watches/{gender}/"
        prods = [p for p in self.products if gender in p["gender"]]
        budgets = "".join(
            f'<a class="tile" href="/watches/{gender}/{b["slug"]}/"><span class="tile-kicker">Budget</span><strong>{esc(b["label"])}</strong></a>'
            for b in self.config["budgets"])
        brands = "".join(
            f'<a class="tile brand-{esc(b["tier"])}" href="/watches/brands/{b["slug"]}/"><span class="tile-kicker">{"Featured" if b["tier"] == "featured" else "Value"}</span><strong>{esc(b["name"])}</strong></a>'
            for b in self.config["brands"] if gender in b["genders"])
        h1 = f"{g['label']} Classic Watches"
        grid = self.grid(prods[:6]) if prods else self.empty_state(f"The {g['label'].lower()} watch list")
        body = (
            '<section class="section">\n  <div class="container content-page watch-page">\n'
            f'    {{{{breadcrumb}}}}\n    <h1>{esc(h1)}</h1>\n    <p class="lead">Classic and analog watches for {g["adjective"]}, picked by budget, brand and style.</p>\n'
            f'    <h2>Shop by budget</h2>\n    <div class="tile-grid">{budgets}</div>\n'
            f'    <h2>Explore by brand</h2>\n    <div class="tile-grid">{brands}</div>\n'
            f'    <h2>Editor\'s picks</h2>\n    {grid}\n'
            f'    {self.affiliate_box()}\n  </div>\n</section>')
        return self._meta(url, h1, f"Classic analog watches for {g['adjective']} by budget and brand. Research-based buying guides.", body, [["Watches", "/watches/"], [h1, url]], len(prods))

    def landing(self):
        budget_cards = "".join(
            f'<div class="tile tile-budget"><span class="tile-kicker">Shop by budget</span><strong>{esc(b["label"])}</strong>'
            f'<span class="tile-links"><a href="/watches/men/{b["slug"]}/">Men</a><a href="/watches/women/{b["slug"]}/">Women</a></span></div>'
            for b in self.config["budgets"])
        feat = [b for b in self.config["brands"] if b["tier"] == "featured"]
        value = [b for b in self.config["brands"] if b["tier"] != "featured"]
        brand_cards = "".join(
            f'<a class="tile brand-featured" href="/watches/brands/{b["slug"]}/"><span class="tile-kicker">{esc(b["line"])}</span><strong>{esc(b["name"])}</strong><span class="tile-blurb">{esc(b["blurb"])}</span></a>'
            for b in feat) + "".join(
            f'<a class="tile brand-value" href="/watches/brands/{b["slug"]}/"><span class="tile-kicker">Value</span><strong>{esc(b["name"])}</strong></a>'
            for b in value)
        style_chips = "".join(f'<a class="chip" href="/watches/style/{s["slug"]}/">{esc(s["label"])}</a>' for s in self.config["styles"])
        picks = [p for p in self.products if p.get("editors_pick")][:4]
        picks_html = self.grid(picks) if picks else (
            '<div class="empty-state"><p>Editor\'s picks appear here once we have researched real watches. '
            'We do not show sample watches as picks.</p></div>')
        body = (
            '<section class="watch-hero">\n  <div class="container watch-hero-inner">\n    <div class="watch-hero-copy">\n'
            '      <p class="eyebrow">Classic &amp; analog watches</p>\n      <h1>Timeless Watches. Smart Choices.</h1>\n'
            '      <p>Discover classic and analog watches selected by budget, brand and style.</p>\n'
            '      <div class="hero-actions"><a class="btn btn-primary" href="/watches/men/">Shop Men\'s Watches</a>'
            '<a class="btn btn-outline" href="/watches/women/">Shop Women\'s Watches</a></div>\n    </div>\n'
            f'    <div class="watch-hero-art">{watch_art("hero-watch")}</div>\n  </div>\n</section>\n'
            '<section class="section"><div class="container watch-page">\n'
            f'  <h2>Shop by Budget</h2>\n  <div class="tile-grid">{budget_cards}</div>\n'
            f'  <h2>Explore by Brand</h2>\n  <div class="tile-grid brand-grid">{brand_cards}</div>\n'
            f'  <h2>Shop by Style</h2>\n  <div class="chips">{style_chips}</div>\n'
            f'  <h2>Editor\'s Picks</h2>\n  {picks_html}\n'
            f'  {self.affiliate_box()}\n</div></section>')
        return self._meta("/watches/", "Classic & Analog Watches in India", "Classic and analog watches picked by budget, brand and style, for men and women. Research-based buying guides.", body, [["Watches", "/watches/"]], len(self.products), js=False)

    def preview(self):
        """A noindex page that shows the templates with clearly labelled sample data."""
        samples = self.samples
        if not samples:
            return None
        body = (
            '<section class="section">\n  <div class="container content-page watch-page">\n'
            '    {{breadcrumb}}\n    <h1>Template preview</h1>\n'
            '    <p class="lead">This page shows the watch templates with <strong>sample content</strong>. None of these are real watches, and nothing here is a recommendation.</p>\n'
            f'    {self.filter_ui()}\n    <h2>Our top picks</h2>\n{self.grid(samples)}\n    <h2>Compare</h2>\n{self.table(samples)}\n'
            '    <h2>Reviews</h2>\n' + "\n".join(self.review(p) for p in samples) +
            f'\n    {self.buying_guide("men", "under-3000")}\n    {self.faq()}\n    {self.affiliate_box()}\n  </div>\n</section>')
        meta = self._meta("/watches/preview/", "Watch Template Preview", "Sample content showing the watch page templates. Not real products.", body,
                          [["Watches", "/watches/"], ["Template preview", "/watches/preview/"]], 0, noindex=True)
        return meta

    def pages(self):
        out = [self.landing()]
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
