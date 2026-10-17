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
import watch_data
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
        self.settings = read_json(base / "settings.json") if (base / "settings.json").exists() else {}
        self.brand_notes = read_json(base / "brand-notes.json") if (base / "brand-notes.json").exists() else {}
        self.approved = (read_json(base / "collections.json") if (base / "collections.json").exists() else {}).get("approved", {})
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
        self.intake_notes = {}
        for p in [watch_data.normalise(r, self.budgets) for r in raw]:
            self._register_brand(p)
            self._validate(p)
            ok, why = self._ready(p)
            if ok:
                self.products.append(p)
            else:
                self.warnings.append(f"watch {p.get('id', '?')}: not shown ({why})")
        seen = {}
        for p in self.products:
            for reason in watch_data.duplicates(p, [q for q in self.products if q is not p and q["id"] < p["id"]]):
                self.errors.append(f"watch {p['id']}: duplicate ({reason})")
        ids = [p["id"] for p in self.products]
        for dup in {i for i in ids if ids.count(i) > 1}:
            self.errors.append(f"watch id {dup!r} is used by more than one file")
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

    def _register_brand(self, p):
        """A product from a brand that is not in config.json creates the brand automatically (name from the slug unless settings give one)."""
        slug_ = p.get("brand")
        if not slug_ or slug_ in self.brands:
            return
        name = (self.settings.get("brand_names") or {}).get(slug_) or str(slug_).replace("-", " ").title()
        entry = {"slug": slug_, "name": name, "tier": "value", "genders": ["men", "women"], "line": "Classic",
                 "blurb": f"{name} watches listed on SAT."}
        self.brands[slug_] = entry
        self.config["brands"].append(entry)
        self.warnings.append(f"brand {slug_!r} was added automatically as {name!r}")

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
        errs, warns = watch_data.validate(p, self.brands, self.styles, self.genders, self.budgets)
        self.errors.extend(f"watch {pid}: {e}" for e in errs)
        self.warnings.extend(f"watch {pid}: {w}" for w in warns)
        if p.get("brand") and p["brand"] not in self.brands:
            self.errors.append(f"watch {pid}: unknown brand {p['brand']!r}")
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
        if not p.get("brand") or not p.get("product_name") or not p.get("gender"):
            return False, "missing brand, product_name or gender"
        if not p.get("verdict"):
            p["verdict"] = p.get("best_for") or ("Specifications as listed: " + p["card_specs"] + "." if p.get("card_specs") else "Details as listed by the retailer.")
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
            f'data-gender="{esc(" ".join(p["gender"]))}" data-style="{esc(" ".join(p["styles"]))}" data-budget="{esc(" ".join(self.qualifies(p)) or "unlisted")}" data-styles="{esc(" ".join(p["styles"]))}" '
            + " ".join(f'data-{key}="{esc(" ".join(v for v in getter(self, p) if v))}"' for key, _, _, getter in self.FILTERS) + '>'
            + media + '<div class="watch-body">'
            f'<p class="watch-brand">{esc(brand)}</p>' + (f'<p class="watch-label">{esc(watch_data.EDITORIAL_LABELS.get(p["editorial_labels"][0], ""))}</p>' if p.get("editorial_labels") and p["editorial_labels"][0] in watch_data.EDITORIAL_LABELS else "") +
            f'<h3 class="watch-model"><a href="{esc(href)}">{esc(p["model"])}</a></h3>'
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

    # One table defines every filter group in the panel. To add a filter, add a row here and an optional field to the watch files.
    # "get" returns the option slugs a watch has; a group is shown only when at least one watch has a value.
    CASES = [("alloy-steel", "Alloy Steel"), ("brass", "Brass"), ("metal", "Metal"), ("plastic", "Plastic"), ("polycarbonate", "Polycarbonate"),
             ("resin", "Resin"), ("stainless-steel", "Stainless Steel")]
    DIAL_SIZES = [("36-and-under", "36 mm and under", 0, 36), ("37-40", "37\u201340 mm", 37, 40), ("41-44", "41\u201344 mm", 41, 44), ("45-plus", "45 mm and above", 45, 10 ** 4)]
    WATER = [("splash", "Splash resistant", 0, 29), ("30-m", "30 m", 30, 49), ("50-m", "50 m", 50, 99), ("100-m", "100 m", 100, 199), ("200-plus", "200 m and above", 200, 10 ** 6)]
    FILTERS = [
        ("occasion", "Occasion", [("office", "Office"), ("formal", "Formal"), ("casual", "Casual"), ("everyday", "Everyday"), ("party", "Party"), ("gift", "Gift")], lambda self, p: p.get("occasions", [])),
        ("dial", "Dial size", [(a, b) for a, b, _, _ in DIAL_SIZES], lambda self, p: [self.bucket(self.DIAL_SIZES, p.get("case_diameter_mm"))]),
        ("strapmat", "Strap material", [("leather", "Leather"), ("stainless-steel", "Stainless Steel"), ("mesh", "Mesh"), ("silicone-rubber", "Silicone / Rubber"), ("fabric-nylon", "Fabric / Nylon")], lambda self, p: [p.get("band_material", "")]),
        ("movement", "Movement", [("quartz", "Quartz"), ("automatic", "Automatic"), ("mechanical", "Mechanical")], lambda self, p: [p.get("movement", "")]),
        ("water", "Water resistance", [(a, b) for a, b, _, _ in WATER], lambda self, p: [self.bucket(self.WATER, p.get("water_resistance_metres"))]),
        ("dialcolour", "Dial colour", [(x, x.replace("-", " ").title()) for x in ("black", "white", "blue", "green", "silver", "gold", "brown")], lambda self, p: p.get("dial_colour", [])),
        ("strapcolour", "Strap colour", [(x, x.replace("-", " ").title()) for x in ("black", "brown", "green", "silver", "gold", "blue", "rose-gold")], lambda self, p: p.get("band_colour", [])),
        ("shape", "Case shape", [("round", "Round"), ("square", "Square"), ("rectangular", "Rectangular")], lambda self, p: [p.get("case_shape", "")]),
        ("feature", "Features", [("date", "Date"), ("day-date", "Day-Date"), ("chronograph", "Chronograph"), ("luminous-hands", "Luminous hands"), ("second-hand", "Second hand"), ("minimal-dial", "Minimal dial")], lambda self, p: p.get("features", [])),
        ("case", "Case material", CASES, lambda self, p: [p.get("case_material", "")]),
    ]

    @staticmethod
    def bucket(table, value):
        return next((slug for slug, _, lo, hi in table if value is not None and lo <= value <= hi), "")

    def qualifies(self, p):
        """Price bands a watch appears under: its own and every higher one (Under 2,000 also appears under 3,000, 5,000 ...)."""
        return watch_data.price_qualifies(p, self.budgets)

    def active_brands(self):
        """Brands that have live watches, in the order set in settings.json (brand_order, then featured_brands, then most watches); hidden ones left out."""
        counts = {}
        for p in self.products:
            counts[p["brand"]] = counts.get(p["brand"], 0) + 1
        hidden = set(self.settings.get("hidden_brands", []))
        order = self.settings.get("brand_order", [])
        featured = self.settings.get("featured_brands") or [b["slug"] for b in self.config["brands"] if b.get("tier") == "featured"]
        def rank(slug_):
            return (order.index(slug_) if slug_ in order else len(order), 0 if slug_ in featured else 1, -counts[slug_], self.brands[slug_]["name"].lower())
        return [(slug_, self.brands[slug_]["name"], counts[slug_]) for slug_ in sorted(counts, key=rank) if slug_ not in hidden and slug_ in self.brands]

    HUBS = {"/watches/", "/watches/men/", "/watches/women/"}

    def collection_noindex(self, url, shown):
        """A hub page is indexable once it has a watch. Any other collection is indexable only when it has enough watches, is approved in
        collections.json, and has its own introduction of at least 100 words. Everything else stays a normal filter result."""
        if url in self.HUBS:
            return not shown
        entry = self.approved.get(url) or {}
        return not (len(shown) >= self.min_index and len(str(entry.get("intro", "")).split()) >= 100)

    def collection_copy(self, url):
        entry = self.approved.get(url)
        if not entry or len(str(entry.get("intro", "")).split()) < 100:
            return ""
        faqs = "".join(f'<details class="faq-item"><summary><h3>{esc(f["q"])}</h3><span class="faq-chev" aria-hidden="true"></span></summary><p>{esc(f["a"])}</p></details>'
                       for f in entry.get("faqs", []))
        parts = [f'<p>{esc(entry["intro"])}</p>']
        if entry.get("who_for"):
            parts.append(f'<h3>Who this page is for</h3><p>{esc(entry["who_for"])}</p>')
        if entry.get("advice"):
            parts.append(f'<h3>Buying advice</h3><p>{esc(entry["advice"])}</p>')
        if faqs:
            parts.append(f'<h3>Common questions</h3>{faqs}')
        return '<section class="watch-collection-copy">' + "".join(parts) + '</section>'

    def parse_collection_url(self, url):
        """The filter combination a collection URL stands for ({'brand': ..., 'price_band': ...}), or None when no such page is generated."""
        parts = [x for x in url.strip("/").split("/") if x]
        if not parts or parts[0] != "watches":
            return None
        parts = parts[1:]
        if len(parts) == 1 and parts[0] in self.genders:
            return {"gender": parts[0]}
        if len(parts) == 2 and parts[0] == "brands" and parts[1] in self.brands:
            return {"brand": parts[1]}
        if len(parts) == 2 and parts[0] == "style" and parts[1] in self.styles:
            return {"style": parts[1]}
        if len(parts) == 2 and parts[1] in self.budgets:
            if parts[0] in self.genders:
                return {"gender": parts[0], "price_band": parts[1]}
            if parts[0] in self.brands and (parts[0], parts[1]) in self.brand_budget_pairs():
                return {"brand": parts[0], "price_band": parts[1]}
        return None

    def published_collections(self):
        """Collections open to Google: approved in collections.json, with their own introduction and enough watches. Each entry carries
        the metadata the Watches hub is built from: category, brand, price_band, gender, style, seo_status, featured_on_watch_hub.
        An entry in collections.json may set "featured_on_watch_hub": false to keep a published page off the hub."""
        out = []
        for url, entry in self.approved.items():
            key = self.parse_collection_url(url)
            if not key:
                continue
            shown = [p for p in self.products if (not key.get("gender") or key["gender"] in p["gender"]) and (not key.get("brand") or p["brand"] == key["brand"])
                     and (not key.get("price_band") or key["price_band"] in self.qualifies(p)) and (not key.get("style") or key["style"] in p["styles"])]
            if self.collection_noindex(url, shown):
                continue
            band = self.budgets[key["price_band"]]["label"] if key.get("price_band") else ""
            name = self.brands[key["brand"]]["name"] if key.get("brand") else (self.genders[key["gender"]]["label"] if key.get("gender") else self.styles[key["style"]]["label"])
            out.append({"category": "watches", "url": url, **key, "genders": sorted({g for p in shown for g in p["gender"]}), "count": len(shown),
                        "seo_status": "indexable", "featured_on_watch_hub": entry.get("featured_on_watch_hub", True) is not False,
                        "label": name, "title": f"{name} watches {band.lower()}" if band else f"{name} watches"})
        return out

    def hub_html(self):
        """Discovery sections of /watches/ built from the published collections: real links to their own pages, never a filter state.
        Returns (html, keys of the sections shown). Brand, budget and style links appear only for collections that are published."""
        pubs = [c for c in self.published_collections() if c["featured_on_watch_hub"]]
        blocks, keys = [], set()

        def block(key, heading, inner):
            keys.add(key)
            blocks.append(f'<section class="hub-block hub-{key}" aria-labelledby="hub-{key}"><h2 id="hub-{key}">{esc(heading)}</h2>{inner}</section>')

        rows = ""
        for band, info in self.budgets.items():
            links = [c for c in pubs if c.get("price_band") == band]
            if links:
                rows += (f'<div class="hub-row"><h3>{esc(info["label"])}</h3><ul class="hub-pills">'
                         + "".join(f'<li><a class="hub-pill" href="{esc(c["url"])}">{esc(c["label"])}</a></li>' for c in links) + '</ul></div>')
        if rows:
            block("budget", "Looking for watches by budget?", rows)

        by_brand = {}
        for c in pubs:
            if c.get("brand"):
                by_brand.setdefault(c["brand"], []).append(c)
        pills = ""
        for slug_, name, _ in self.active_brands():
            cs = by_brand.get(slug_)
            if cs:
                target = next((c for c in cs if not c.get("price_band")), cs[0])
                pills += f'<li><a class="hub-pill" href="{esc(target["url"])}">{esc(name)}</a></li>'
        if pills:
            block("brand", "Shop by Brand", f'<ul class="hub-pills">{pills}</ul>')

        pills = "".join(f'<li><a class="hub-pill" href="{esc(c["url"])}">{esc(c["label"])}</a></li>' for c in pubs if c.get("style") and not c.get("brand"))
        if pills:
            block("style", "Shop by Style", f'<ul class="hub-pills">{pills}</ul>')

        cards = ""
        for g, info in self.genders.items():
            count = sum(1 for p in self.products if g in p["gender"])
            if count:
                cards += f'<li><a class="hub-person" href="/watches/{esc(g)}/"><strong>{esc(info["label"])}</strong><span>{count} {"watch" if count == 1 else "watches"}</span></a></li>'
        if cards:
            block("people", "Men or women?", f'<ul class="hub-people">{cards}</ul>')

        guides = [("How to choose a watch", "/watches/guide/", "What to check before you buy, in plain words.")]
        guides += [(g["title"], g["url"], g.get("note", "")) for g in self.config.get("hub_guides", [])]
        items = "".join(f'<li><a class="hub-guide" href="{esc(u)}"><strong>{esc(t)}</strong>' + (f'<span>{esc(n)}</span>' if n else "") + '</a></li>' for t, u, n in guides)
        block("guides", "Popular buying guides", f'<ul class="hub-guides">{items}</ul>')
        return '<div class="watch-hub">' + "".join(blocks) + '</div>', keys

    def collection_table(self, products):
        """Comparison table for a collection page: Model | Best for | Gender | Case size | Movement | Strap | Water resistance | CTA."""
        if len(products) < 2:
            return ""
        def cell(label, value):
            return f'<td role="cell" data-label="{esc(label)}">{esc(value) if value else "Not stated"}</td>'
        rows = []
        for p in products:
            strap = " ".join(x for x in ((p.get("band_colour") or [""])[0].replace("-", " ").title(), p.get("band_material", "").replace("-", " ")) if x).strip()
            mm, metres = p.get("case_diameter_mm"), p.get("water_resistance_metres")
            rows.append(
                f'<tr role="row"><th scope="row" role="rowheader"><a href="{esc(self.review_url(p))}">{esc(p["model"])}</a></th>'
                + cell("Best for", p.get("best_for", "")) + cell("Gender", " / ".join(self.genders[g]["label"] for g in p["gender"] if g in self.genders))
                + cell("Case size", f"{mm:g} mm" if mm else "") + cell("Movement", p.get("movement", "").title())
                + cell("Strap", strap) + cell("Water resistance", f"{metres:g} m" if metres else "")
                + f'<td role="cell" data-label="Shop">{self.check_price(p, include_more=False) or "Not available"}</td></tr>')
        head = "".join(f'<th scope="col" role="columnheader">{h}</th>' for h in ("Model", "Best for", "Gender", "Case size", "Movement", "Strap", "Water resistance", "Shop"))
        return ('<section class="watch-collection-table"><h2>Compare these watches</h2><div class="compare-table-wrap"><table class="compare-table" role="table">'
                f'<caption class="visually-hidden">Comparison of the watches on this page</caption><thead><tr role="row">{head}</tr></thead><tbody>' + "".join(rows) + '</tbody></table></div></section>')

    def catalog(self, url, title, intro, *, gender="", brand="", budget="", style="", crumbs=None, extra_html="", table=False, hub=None):
        products = self.products
        def matches(p):
            return ((not gender or gender in p["gender"]) and (not brand or p["brand"] == brand)
                    and (not budget or budget in self.qualifies(p)) and (not style or style in p["styles"]))
        shown = [p for p in products if matches(p)]
        def n(pred):
            return sum(1 for p in products if pred(p))
        planned = self.settings.get("planned_filters", {})
        active = self.active_brands()
        groups = [
            {"key": "brand", "title": "Brand", "checked": [brand] if brand else [], "items": [(slug_, name, cnt) for slug_, name, cnt in active]},
            {"key": "budget", "title": "Price", "checked": [budget] if budget else [],
             "items": [(slug_, value["label"], n(lambda p, s=slug_: s in self.qualifies(p))) for slug_, value in self.budgets.items() if n(lambda p, s=slug_: s in self.qualifies(p))]
                      + ([("unlisted", "Price at retailer", n(lambda p: not p.get("budget")))] if n(lambda p: not p.get("budget")) else [])},
        ]
        for key, group_title, options, getter in self.FILTERS:
            items = [(slug_, label, n(lambda p, s=slug_: s in getter(self, p))) for slug_, label in options]
            live = [it for it in items if it[2]]
            wanted = set(planned.get(key, []))
            items = [it for it in items if it[2] or it[0] in wanted]
            if len(live) >= 2 or (live and len(items) > len(live)):
                groups.append({"key": key, "title": group_title, "checked": [], "show_empty": True, "items": items})
        # a group with only one live value is hidden: it would filter nothing
        groups = [g for g in groups if len([it for it in g["items"] if it[2]]) >= 2 or g["key"] in ("brand", "budget") and len(g["items"]) >= 2]
        groups.append({"key": "style", "title": "Style", "checked": [style] if style else [],
                       "items": [(slug_, value["label"], n(lambda p, s=slug_: s in p["styles"])) for slug_, value in self.styles.items()]})
        style_links = '<a class="watch-style" href="/watches/" data-style-toggle="" aria-current="false"><span class="style-dot" aria-hidden="true">' + watch_art("style-art") + '</span><span>All styles</span></a>'
        for slug, value in self.styles.items():
            style_links += (f'<a class="watch-style" href="/watches/style/{slug}/" data-style-toggle="{esc(slug)}" aria-current="false">'
                            f'<span class="style-dot style-{esc(slug)}" aria-hidden="true">{watch_art("style-art")}</span><span>{esc(value["label"])}</span></a>')
        brand_pills = "".join(
            f'<button type="button" class="watch-chip" data-quick-chip="brand" data-value="{esc(slug_)}" aria-pressed="false">{esc(name)} <em>{cnt}</em></button>'
            for slug_, name, cnt in active) if len(active) >= 2 else ""
        quick = ""
        top = ('<div class="watch-discovery"><div class="watch-style-head"><h2>Shop by style</h2><a href="/watches/guide/">Buying guide &rarr;</a></div>'
               f'<nav class="watch-style-row" aria-label="Watch styles">{style_links}</nav>'
               + (f'<div class="watch-brand-head"><h2>Shop by brand</h2></div><div class="watch-chip-row" role="group" aria-label="Shop by brand" data-brand-row>{brand_pills}</div>' if brand_pills else "")
               + f'<div class="watch-quick-row" data-quick-controls hidden>{quick}'
               '</div></div>')
        hub_html, hub_keys = hub or ("", set())
        if "brand" in hub_keys:  # the hub lists the brands that have their own page; this row only filters the list below
            top = top.replace("<h2>Shop by brand</h2>", "<h2>Filter by brand</h2>")
        if "style" in hub_keys:
            top = top.replace("<h2>Shop by style</h2>", "<h2>Filter by style</h2>")
        top = top.replace(f'data-style-toggle="{esc(style)}" aria-current="false"', f'data-style-toggle="{esc(style)}" aria-current="true"', 1)
        block = collection.render([self.card(p) for p in products], groups, uid="watch-collection", title="Explore watches", noun="watch", plural="watches",
                                  preset_gender=gender, genders=[("men", "Men"), ("women", "Women")],
                                  top_html=top, visible=[matches(p) for p in products], page_size=24)
        body = ('<section class="section watch-store"><div class="container watch-store-inner">{{breadcrumb}}'
                f'<header class="watch-store-head"><div><p class="watch-kicker">The SAT watch edit</p><h1>{esc(title)}</h1><p>{esc(intro)}</p></div>'
                '<a class="watch-guide-link" href="/watches/guide/">Find your fit &rarr;</a></header>' + hub_html + block + (self.collection_table(shown) if table else "") + self.collection_copy(url) + extra_html + '<noscript><nav class="watch-static-links" aria-label="Browse watches"><a href="/watches/men/">Men</a> · <a href="/watches/women/">Women</a> · ' + ' · '.join(f'<a href="/watches/brands/{esc(slug)}/">{esc(value["name"])}</a>' for slug, value in self.brands.items() if slug != 'sample') + '</nav></noscript></div></section>')
        meta = self._meta(url, title, intro, body, crumbs or [["Watches", "/watches/"]], shown, js=False)
        meta["noindex"] = self.collection_noindex(url, shown)
        meta["css"] += ["collection", "watch-store"]
        meta["js"] = ["collection"]
        return meta

    def filter_state(self, products):
        """{group key: number of different live values}: a group is shown to shoppers when this is 2 or more."""
        state = {"brand": len({p["brand"] for p in products}), "price": len({b for p in products for b in watch_data.price_qualifies(p, self.budgets)})}
        for key, _, options, getter in self.FILTERS:
            state[key] = len({v for p in products for v in getter(self, p) if v})
        return state

    def intake_report(self, p):
        """Everything the owner needs to know before publishing one normalised watch record (does not change any file)."""
        errs, warns = watch_data.validate(p, {**self.brands, p.get("brand", ""): {}}, self.styles, self.genders, self.budgets)
        before = self.filter_state(self.products)
        after_products = [q for q in self.products if q["id"] != p.get("id")] + [p]
        after = self.filter_state(after_products)
        labels = dict((k, t) for k, t, _, _ in self.FILTERS)
        labels.update({"brand": "Brand", "price": "Price"})
        cats = [("Gender", ", ".join(self.genders[g]["label"] for g in p["gender"] if g in self.genders)), ("Brand", self.brands.get(p["brand"], {}).get("name", p.get("brand", "")))]
        cats.append(("Styles", ", ".join(self.styles[x]["label"] if x in self.styles else x for x in p["styles"]) or "none yet"))
        for key, title, options, getter in self.FILTERS:
            names = dict(options)
            vals = [names.get(v, v) for v in getter(self, p) if v]
            if vals:
                cats.append((title, ", ".join(vals)))
        cats.append(("Price", ", ".join(self.budgets[b]["label"] for b in watch_data.price_qualifies(p, self.budgets)) or "Price at retailer (no band given)"))
        enabled = [labels[k] for k in after if after[k] >= 2 and before.get(k, 0) < 2]
        missing_optional = [f.replace("_", " ") for f in watch_data.FACT_FIELDS + ["price_band"] if not watch_data.known(p.get(f))]
        saved = self.products
        self.products = after_products
        try:
            cands = self.collection_candidates(must=p)
        finally:
            self.products = saved
        mine = sorted(cands, key=lambda c: (-c["count"], c["name"]))[:8]
        dup = watch_data.duplicates(p, self.products)
        errs = errs + [f"duplicate: {r}" for r in dup]
        return {"errors": errs, "duplicates": dup, "warnings": warns, "categories": cats, "filters_enabled": enabled, "missing_optional": missing_optional,
                "collections": [f'{c["name"]} ({c["count"]} watches, {"approved" if c["approved"] else "needs approval and its own copy"})' for c in mine]}

    def collection_candidates(self, must=None):
        """Filter combinations (up to two) that have enough watches to justify a page, and whether each is approved. Report only."""
        dims = []
        for g in self.genders:
            dims.append(("gender", g, self.genders[g]["label"], lambda p, v=g: v in p["gender"]))
        for slug_, name, _ in self.active_brands():
            dims.append(("brand", slug_, name, lambda p, v=slug_: p["brand"] == v))
        own = {p.get("budget") for p in self.products if p.get("budget")}
        for b, info in self.budgets.items():
            if b in own:  # only bands that a live watch actually belongs to; the filter still lists every higher band
                dims.append(("budget", b, info["label"], lambda p, v=b: v in self.qualifies(p)))
        for st, info in self.styles.items():
            dims.append(("style", st, info["label"], lambda p, v=st: st in p["styles"] if v == st else False))
        for key, _, options, getter in self.FILTERS:
            if key in ("water", "occasion", "strapmat", "movement"):
                for slug_, label in options:
                    dims.append((key, slug_, label, lambda p, g=getter, v=slug_: v in g(self, p)))
        out = []
        for i, a in enumerate(dims):
            for b in [None] + dims[i + 1:]:
                if b is not None and a[0] == b[0]:
                    continue
                items = [p for p in self.products if a[3](p) and (b is None or b[3](p))]
                if len(items) < self.min_index:
                    continue
                if must is not None and not (a[3](must) and (b is None or b[3](must))):
                    continue
                name = a[2] + ("" if b is None else " + " + b[2])
                url = self.collection_url(a, b)
                out.append({"name": name, "count": len(items), "url": url, "approved": bool(url and len(str((self.approved.get(url) or {}).get("intro", "")).split()) >= 100)})
        return out

    @staticmethod
    def collection_url(a, b):
        pair = {a[0]: a[1]}
        if b is not None:
            pair[b[0]] = b[1]
        if len(pair) == 1:
            k, v = next(iter(pair.items()))
            return {"gender": f"/watches/{v}/", "brand": f"/watches/brands/{v}/", "style": f"/watches/style/{v}/"}.get(k)
        if set(pair) == {"gender", "budget"}:
            return f'/watches/{pair["gender"]}/{pair["budget"]}/'
        if set(pair) == {"brand", "budget"}:
            return f'/watches/{pair["brand"]}/{pair["budget"]}/'
        return None

    def budget_page(self, gender, budget):
        g, b = self.genders[gender], self.budgets[budget]
        url = f"/watches/{gender}/{budget}/"
        title = f'{g["label"]} Watches {b["label"]}'
        return self.catalog(url, title, "Compare styles and published details. Confirm the current price with the retailer.", gender=gender, budget=budget,
                            crumbs=[["Watches", "/watches/"], [g["label"], f"/watches/{gender}/"], [b["label"], url]])

    def brand_budget_pairs(self):
        """(brand, band) pairs where a live watch of that brand sits in that band: each gets a clean URL /watches/<brand>/<band>/."""
        pairs = []
        for b in self.config["brands"]:
            for slug_, info in self.budgets.items():
                if any(p["brand"] == b["slug"] and p.get("budget") == slug_ for p in self.products):
                    pairs.append((b["slug"], slug_))
        return pairs

    def brand_budget_page(self, brand, budget):
        br, bd = self.brands[brand], self.budgets[budget]
        url = f"/watches/{brand}/{budget}/"
        count = sum(1 for p in self.products if p["brand"] == brand and budget in self.qualifies(p))
        ready = count >= self.min_index and url in self.approved
        title = f'{"Best " if ready else ""}{br["name"]} Watches {bd["label"]}'
        intro = f'{br["name"]} watches {bd["label"].lower()}, for men and women. Compare the published details and confirm the current price at the retailer.'
        return self.catalog(url, title, intro, brand=brand, budget=budget, table=True,
                            crumbs=[["Watches", "/watches/"], [br["name"], f"/watches/brands/{brand}/"], [bd["label"], url]])

    def brand_page(self, slug):
        br = self.brands[slug]
        url = f"/watches/brands/{slug}/"
        pair_links = "".join(f'<li><a href="/watches/{slug}/{b}/">{esc(br["name"])} watches {esc(self.budgets[b]["label"].lower())}</a></li>' for br_, b in self.brand_budget_pairs() if br_ == slug)
        extra = f'<nav class="watch-static-links" aria-label="{esc(br["name"])} by price"><h2>{esc(br["name"])} by price</h2><ul class="related-links">{pair_links}</ul></nav>' if pair_links else ""
        meta = self.catalog(url, br["name"] + " Watches", "Explore the collection by style and budget. Read the details before you choose.", brand=slug,
                            crumbs=[["Watches", "/watches/"], [br["name"], url]], extra_html=extra)
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
        return self.catalog("/watches/", "Watches for every day.", "Classic style. Everyday usefulness. Find a watch that feels like you.", hub=self.hub_html())

    def product_detail(self, p):
        brand = self.brands[p["brand"]]["name"]
        href = self.review_url(p)
        def section(title, inner):
            return f'<section class="watch-section"><h2>{esc(title)}</h2>{inner}</section>' if inner else ""
        def ul(items):
            return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>" if items else ""
        specs, unknown = [], []
        def spec(label, value, key=None):
            if value:
                specs.append((label, value))
            elif key:
                unknown.append(label.lower())
        mm, th = p.get("case_diameter_mm"), p.get("case_thickness_mm")
        spec("Case diameter", f"{mm:g} mm" if mm else "", "case diameter")
        spec("Case thickness", f"{th:g} mm" if th else "")
        mat = p.get("band_material", "")
        spec("Strap", " ".join(x for x in ((p.get("band_colour") or [""])[0].replace("-", " ").title(), mat.replace("-", " ")) if x).strip() or p.get("strap", ""), "strap")
        spec("Dial colour", ", ".join(c.replace("-", " ").title() for c in p.get("dial_colour", [])))
        spec("Case shape", p.get("case_shape", "").title())
        spec("Movement", p.get("movement", "").title(), "movement")
        spec("Display", p.get("display_type", "").replace("-", " ").title())
        metres, atm = p.get("water_resistance_metres"), p.get("water_resistance_atm")
        spec("Water resistance", f"Rated {metres:g} m ({atm:g} ATM), water-resistant, not waterproof" if metres else "", "water resistance")
        spec("Warranty", " ".join(x for x in (p.get("warranty_type", "").title(), p.get("warranty_duration", "")) if x), "warranty")
        spec("Country of origin", p.get("country_of_origin", ""))
        dl = "<dl class=\"spec-list\">" + "".join(f"<div><dt>{esc(k)}</dt><dd>{esc(v)}</dd></div>" for k, v in specs) + "</dl>" if specs else ""
        miss = f'<p class="watch-unknown">Not stated: {esc(", ".join(unknown))}.</p>' if unknown else ""
        prov = p.get("source_verified", "")
        provenance = f'<p class="watch-provenance">Specifications: {esc(prov)}. We have not tested this watch.</p>' if prov else ""
        qs = watch_data.questions(p, {"band_label": self.budgets[p["budget"]]["label"] if p.get("budget") in self.budgets else "",
                                      "brand_notes": self.brand_notes, "other_brands": {q["brand"] for q in self.products}})
        faq = "".join(f'<details class="faq-item"><summary><h3>{esc(q)}</h3><span class="faq-chev" aria-hidden="true"></span></summary><p>{esc(a)}</p></details>' for kind, q, a in qs if kind not in ("fit", "water"))
        fit = next((a for k, q, a in qs if k == "fit"), "")
        wr = next((a for k, q, a in qs if k == "water"), "")
        alts = [q for q in self.products if q["id"] != p["id"] and set(q["gender"]) & set(p["gender"])
                and (q["brand"] == p["brand"] or set(self.qualifies(q)) & set(self.qualifies(p)))]
        alts = sorted(alts, key=lambda q: (q["brand"] != p["brand"], q.get("budget") != p.get("budget")))[:3]
        label = watch_data.EDITORIAL_LABELS.get((p.get("editorial_labels") or [""])[0], "")
        why = p.get("editorial_notes") or (p["verdict"] if p.get("paragraphs") or p.get("best_for") else "")
        return (
            (f'<span class="rank">{esc(label)}</span>' if label else "") +
            f'<div class="watch-cta-row">{self.check_price(p, small=False, include_more=False)}</div>{self.cta_note(p)}'
            + section("Why consider it", f'<p>{esc(why)}</p>' if why else "")
            + section("Best for", f'<p>{esc(p["best_for"])}</p>' if p.get("best_for") else "")
            + section("Key specifications", dl + miss + provenance)
            + section("What we like", ul(p.get("good", [])))
            + section("What to know before buying", ul(p.get("not_good", [])))
            + section("Fit and size", f"<p>{esc(fit)}</p>" if fit else "")
            + section("Water resistance explained", f"<p>{esc(wr)}</p>" if wr else "")
            + section("Who should buy it", ul(p.get("who_should_buy", [])))
            + section("Who should skip it", ul(p.get("who_should_skip", [])))
            + section("Alternatives", self.grid(alts) if alts else "")
            + section("Questions shoppers ask", faq))

    def product_page(self, p):
        brand = self.brands[p["brand"]]["name"]
        url = self.review_url(p)
        title = p["product_name"] if p["product_name"].lower().startswith(brand.lower()) else brand + " " + p["model"]
        body = ('<section class="section"><div class="container content-page watch-page watch-product-page">{{breadcrumb}}'
                f'<h1>{esc(title)}</h1>' + self.product_detail(p) +
                '<p><a class="btn btn-outline" href="/watches/">Explore all watches &rarr;</a></p></div></section>')
        short = title if len(title) <= 52 else title[:52].rsplit(" ", 1)[0]  # the page <title> stays within the search-result length
        meta = self._meta(url, short, p["verdict"], body, [["Watches", "/watches/"], [brand, f'/watches/brands/{p["brand"]}/'], [p["model"], url]], [p], js=False)
        # a page without any written review stays out of Google until it has one
        meta["noindex"] = not (p.get("paragraphs") or p.get("editorial_notes"))
        meta["css"] += ["watch-store"]
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
        for brand_, budget_ in self.brand_budget_pairs():
            out.append(self.brand_budget_page(brand_, budget_))
        for s in self.styles:
            out.append(self.style_page(s))
        prev = self.preview()
        if prev:
            out.append(prev)
        return out
