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
import hashlib
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
        self.keywords = read_json(base / "keywords.json").get("pages", {}) if (base / "keywords.json").exists() else {}
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
        return "Check price on" if link["direct"] else "Search on"

    def check_price(self, p, small=True, include_more=True):
        links = self.merchant_links(p)
        if not links or p.get("sample"):
            return ""
        size = " btn-small" if small else ""
        first = links[0]
        primary = (f'<a class="btn btn-primary{size}" href="{esc(first["href"])}" target="_blank" rel="{self.rel()}" '
                   f'aria-label="{self.verb(first)} {esc(first["label"])} for {esc(p["model"])} (opens in a new tab)">'
                   f'{"Check price" if first["direct"] else "Search " + esc(first["label"])} '
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

    DIAL_HEX = {"black": "#1b1c1f", "white": "#f4f1ea", "blue": "#1f3a6e", "green": "#1f4d3a", "silver": "#c9ccd1", "gold": "#c9a45c", "champagne": "#e3d3a8",
                "cream": "#efe6cf", "pink": "#e8b4bc", "grey": "#8b9097", "brown": "#5a3a24", "rose-gold": "#c98f7f", "red": "#8c1f2c", "beige": "#e3d6bd"}
    STRAP_HEX = {"black": "#232325", "brown": "#5b3a25", "green": "#2f5a43", "silver": "#c3c7cc", "grey": "#868b92", "gold": "#c9a45c", "blue": "#243b6b", "rose-gold": "#c98f7f",
                 "white": "#e9e5dc", "champagne": "#d9c79a", "red": "#8c1f2c", "beige": "#d8c8a8"}
    METAL_HEX = {"gold": "#c9a45c", "rose-gold": "#c98f7f", "silver": "#c7cad0", "red": "#8c1f2c"}

    @staticmethod
    def _mix(hex_, other, t):
        a = [int(hex_[k:k + 2], 16) for k in (1, 3, 5)]
        b = [int(other[k:k + 2], 16) for k in (1, 3, 5)]
        return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))

    def dial_art(self, p):
        """A watch drawn from what the listing states: dial colour, strap colour and material (leather stitching or metal links), case metal, case shape and size,
        chronograph sub-dials, date window. Colours that are not stated are drawn in a neutral tone, never guessed. It is an illustration, not a photograph."""
        mix = self._mix
        dial_key = (p.get("dial_colour") or [""])[0]
        strap_key = (p.get("band_colour") or [""])[0]
        dial = self.DIAL_HEX.get(dial_key, "#d8d1c2")
        strap = self.STRAP_HEX.get(strap_key, "#b4afa4")
        metal_strap = p.get("band_material") in ("stainless-steel", "metal")
        metal = self.METAL_HEX.get(strap_key, "#c7cad0") if metal_strap else "#c7cad0"
        light = sum(int(dial[k:k + 2], 16) * w for k, w in ((1, .3), (3, .59), (5, .11))) > 140
        ink = "#26272b" if light else "#f1e6c9"
        accent = metal if metal in ("#c9a45c", "#c98f7f") else ink
        shape = p.get("case_shape") or "round"
        mm = float(p.get("case_diameter_mm") or 40)
        scale = max(.8, min(1.1, .8 + (mm - 20) / 30 * .3))
        uid = hashlib.md5(f"{p.get('id', '')}{dial}{strap}{metal}{shape}{metal_strap}".encode()).hexdigest()[:8]   # unique per watch: ids must not repeat on a page
        features = p.get("features", [])
        cx, cy = 70, 95

        defs = (f'<linearGradient id="m{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{mix(metal, "#ffffff", .6)}"/><stop offset=".45" stop-color="{metal}"/>'
                f'<stop offset="1" stop-color="{mix(metal, "#000000", .38)}"/></linearGradient>'
                f'<radialGradient id="d{uid}" cx=".36" cy=".3" r=".95"><stop offset="0" stop-color="{mix(dial, "#ffffff", .2)}"/><stop offset=".65" stop-color="{dial}"/>'
                f'<stop offset="1" stop-color="{mix(dial, "#000000", .28)}"/></radialGradient>'
                f'<linearGradient id="s{uid}" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{mix(strap, "#000000", .32)}"/><stop offset=".5" stop-color="{mix(strap, "#ffffff", .14)}"/>'
                f'<stop offset="1" stop-color="{mix(strap, "#000000", .32)}"/></linearGradient>'
                f'<linearGradient id="l{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{mix(strap, "#ffffff", .45)}"/><stop offset=".5" stop-color="{strap}"/>'
                f'<stop offset="1" stop-color="{mix(strap, "#000000", .35)}"/></linearGradient>'
                f'<radialGradient id="v{uid}" cx=".5" cy=".5" r=".55"><stop offset=".62" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".34"/></radialGradient>'
                f'<linearGradient id="k{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".5"/></linearGradient>'
f'<linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".5"/><stop offset=".55" stop-color="#fff" stop-opacity=".06"/>'
                '<stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>')

        if metal_strap:
            top = "".join(f'<rect x="{51 - (0 if n else 0)}" y="{2 + n * 10}" width="38" height="8.4" rx="2.2" fill="url(#l{uid})"/>' for n in range(5))
            bottom = "".join(f'<rect x="51" y="{140 + n * 10}" width="38" height="8.4" rx="2.2" fill="url(#l{uid})"/>' for n in range(5))
            straps = top + bottom + f'<rect x="51" y="52" width="38" height="4" fill="{mix(strap, "#000000", .45)}"/><rect x="51" y="134" width="38" height="4" fill="{mix(strap, "#000000", .45)}"/>'
        else:
            holes = "".join(f'<circle cx="70" cy="{y}" r="1.7" fill="{mix(strap, "#000000", .5)}"/>' for y in (158, 167, 176))
            straps = (f'<path d="M50 0H90L94 58H46Z" fill="url(#s{uid})"/><path d="M46 132H94L90 190H50Z" fill="url(#s{uid})"/>'
                      '<g fill="none" stroke="rgba(255,255,255,.4)" stroke-width=".9" stroke-dasharray="2.2 2"><path d="M54 3L51.5 56M86 3L88.5 56M51.5 134L54 187M88.5 134L86 187"/></g>'
                      + holes)
        lugs = "".join(f'<rect x="{x}" y="{y}" width="11" height="15" rx="4" fill="url(#m{uid})"/>' for x, y in ((47, 47), (82, 47), (47, 128), (82, 128)))

        if shape in ("square", "contemporary"):
            r = 30 if shape == "contemporary" else 12
            outer = f'<rect x="{cx - 42}" y="{cy - 42}" width="84" height="84" rx="{r}" fill="url(#m{uid})"/>'
            bezel = f'<rect x="{cx - 38.5}" y="{cy - 38.5}" width="77" height="77" rx="{max(r - 3, 4)}" fill="rgba(0,0,0,.3)"/>'
            dial_shape = f'x="{cx - 35}" y="{cy - 35}" width="70" height="70" rx="{max(r - 6, 4)}"'
            dial_el, clip = f'<rect {dial_shape} fill="url(#d{uid})"/>', f'<rect {dial_shape}/>'
        elif shape == "rectangular":
            outer = f'<rect x="{cx - 37}" y="{cy - 46}" width="74" height="92" rx="10" fill="url(#m{uid})"/>'
            bezel = f'<rect x="{cx - 33.5}" y="{cy - 42.5}" width="67" height="85" rx="7" fill="rgba(0,0,0,.3)"/>'
            dial_shape = f'x="{cx - 30}" y="{cy - 39}" width="60" height="78" rx="5"'
            dial_el, clip = f'<rect {dial_shape} fill="url(#d{uid})"/>', f'<rect {dial_shape}/>'
        elif shape == "oval":
            outer = f'<ellipse cx="{cx}" cy="{cy}" rx="38" ry="47" fill="url(#m{uid})"/>'
            bezel = f'<ellipse cx="{cx}" cy="{cy}" rx="34.5" ry="43.5" fill="rgba(0,0,0,.3)"/>'
            dial_shape = f'cx="{cx}" cy="{cy}" rx="31" ry="40"'
            dial_el, clip = f'<ellipse {dial_shape} fill="url(#d{uid})"/>', f'<ellipse {dial_shape}/>'
        else:
            outer = f'<circle cx="{cx}" cy="{cy}" r="42" fill="url(#m{uid})"/>'
            bezel = f'<circle cx="{cx}" cy="{cy}" r="38.5" fill="rgba(0,0,0,.3)"/>'
            dial_shape = f'cx="{cx}" cy="{cy}" r="35"'
            dial_el, clip = f'<circle {dial_shape} fill="url(#d{uid})"/>', f'<circle {dial_shape}/>'

        marks = "".join(
            f'<line x1="{cx + (24 if i % 3 else 21.5) * math.sin(math.radians(i * 30)):.1f}" y1="{cy - (24 if i % 3 else 21.5) * math.cos(math.radians(i * 30)):.1f}" '
            f'x2="{cx + 28.5 * math.sin(math.radians(i * 30)):.1f}" y2="{cy - 28.5 * math.cos(math.radians(i * 30)):.1f}" stroke-width="{2 if i % 3 == 0 else 1}"/>'
            for i in range(12) if shape in ("round", "oval", "contemporary", "square") or i % 3 == 0)
        subs = ""
        if "chronograph" in features:
            subs = "".join(f'<circle cx="{x}" cy="{y}" r="7" fill="rgba(0,0,0,.08)"/><circle cx="{x}" cy="{y}" r="7"/><path d="M{x} {y}l0 -4.5"/>' for x, y in ((57, 95), (83, 95), (70, 109)))
        window = (f'<rect x="83" y="92" width="10" height="6" rx="1" fill="#fbfaf7" stroke="{mix(dial, "#000000", .4)}" stroke-width=".5"/>'
                  if ("date" in features or "day-date" in features) else "")
        pushers = (f'<rect x="{cx + 40}" y="{cy - 17}" width="6" height="6" rx="1.5" fill="url(#m{uid})"/><rect x="{cx + 40}" y="{cy + 11}" width="6" height="6" rx="1.5" fill="url(#m{uid})"/>'
                   if "chronograph" in features else "")
        face = (f'<g stroke="{accent}" stroke-linecap="round">{marks}</g><g fill="none" stroke="{ink}" stroke-width=".6" opacity=".75">{subs}</g>{window}'
                f'<g stroke-linecap="round"><line x1="{cx}" y1="{cy}" x2="{cx - 9}" y2="{cy - 15}" stroke="{ink}" stroke-width="3"/><line x1="{cx}" y1="{cy}" x2="{cx - 9}" y2="{cy - 15}" stroke="#e8f5c8" stroke-width="1" opacity=".9"/>'
                f'<line x1="{cx}" y1="{cy}" x2="{cx + 15}" y2="{cy - 19}" stroke="{ink}" stroke-width="2.2"/><line x1="{cx}" y1="{cy}" x2="{cx + 15}" y2="{cy - 19}" stroke="#e8f5c8" stroke-width=".7" opacity=".9"/>'
                f'<line x1="{cx - 4}" y1="{cy + 6}" x2="{cx + 7}" y2="{cy - 11}" stroke="#c9a45c" stroke-width=".8"/></g><circle cx="{cx}" cy="{cy}" r="2.6" fill="#c9a45c"/><circle cx="{cx}" cy="{cy}" r="1" fill="#6b5320"/>')
        glass = f'<ellipse cx="{cx - 11}" cy="{cy - 18}" rx="30" ry="15" transform="rotate(-36 {cx - 11} {cy - 18})" fill="url(#g{uid})" clip-path="url(#c{uid})"/>'
        dark = mix(metal, "#000000", .55)
        thickness = re.sub(r'fill="url\(#m\w+\)"', f'fill="{dark}"', outer)
        bevel = re.sub(r'fill="rgba\(0,0,0,\.3\)"', 'fill="none" stroke="url(#k' + uid + ')" stroke-width="1.1"', bezel)
        vignette = dial_el.replace(f"url(#d{uid})", f"url(#v{uid})")
        crown = (f'<rect x="{cx + 40}" y="{cy - 5}" width="8" height="10" rx="2.2" fill="url(#m{uid})"/>'
                 + "".join(f'<line x1="{cx + 42 + k * 1.8:.1f}" y1="{cy - 4.2}" x2="{cx + 42 + k * 1.8:.1f}" y2="{cy + 4.2}" stroke="rgba(0,0,0,.35)" stroke-width=".5"/>' for k in range(3)))
        face_shadow = f'<g transform="translate(1.1 2.2)" opacity=".28" stroke="#000" stroke-linecap="round"><line x1="{cx}" y1="{cy}" x2="{cx - 9}" y2="{cy - 15}" stroke-width="3"/><line x1="{cx}" y1="{cy}" x2="{cx + 15}" y2="{cy - 19}" stroke-width="2.2"/></g>'
        body = (f'<g transform="translate({cx} {cy}) scale({scale:.3f}) translate({-cx} {-cy})">'
                f'{crown}{pushers}<g transform="translate(0 4.5)">{thickness}</g>{outer}{bevel}{dial_el}{vignette}{face_shadow}{face}{glass}'
                f'<ellipse cx="{cx + 14}" cy="{cy + 20}" rx="22" ry="9" transform="rotate(-30 {cx + 14} {cy + 20})" fill="url(#g{uid})" opacity=".35" clip-path="url(#c{uid})"/></g>')
        return (f'<svg class="dial-art" viewBox="0 20 140 150" aria-hidden="true" focusable="false"><defs>{defs}<clipPath id="c{uid}">{clip}</clipPath></defs>'
                f'<g>{straps}</g><g>{lugs}</g>{body}</svg>')

    def watch_theme(self, p):
        """CSS variables for a watch: a light backdrop tinted by its dial (or strap) colour, a mid tone, and an accent from its case metal or dial.
        Used for the card display and, on the product page, for the background, accents and button, so every watch gets its own look."""
        mix = self._mix
        dial_key = (p.get("dial_colour") or [""])[0]
        strap_key = (p.get("band_colour") or [""])[0]
        base = self.DIAL_HEX.get(dial_key) or self.STRAP_HEX.get(strap_key) or "#cdbfa0"
        metal_strap = p.get("band_material") in ("stainless-steel", "metal")
        metal = self.METAL_HEX.get(strap_key) if metal_strap else None
        wb = mix(mix(base, "#d9c9a8", .35), "#ffffff", .88)
        wc = mix(mix(base, "#d9c9a8", .4), "#ffffff", .62)
        accent = mix(metal, "#000000", .3) if metal in ("#c9a45c", "#c98f7f") else mix(base, "#000000", .42 if sum(int(base[k:k + 2], 16) for k in (1, 3, 5)) > 300 else .0)
        return f"--wb:{wb};--wc:{wc};--wa:{accent}"

    def band_range(self, p):
        """The price band a watch sits in, as a range of band edges ("Rs 2,000 - Rs 3,000"); band edges only, never a price."""
        slug_ = p.get("budget")
        if slug_ not in self.budgets:
            return ""
        keys = list(self.budgets)
        top = self.budgets[slug_].get("max")
        low = self.budgets[keys[keys.index(slug_) - 1]].get("max") if keys.index(slug_) else 0
        if not top:
            return self.budgets[slug_]["label"]
        return f"Up to \u20b9{top:,}" if not low else f"\u20b9{low:,}\u2013\u20b9{top:,}"

    def card(self, p, local=False):
        brand = self.brands[p["brand"]]["name"]
        href = f'#r-{p["id"]}' if local else self.review_url(p)
        band = self.budgets[p["budget"]]["label"] if p.get("budget") in self.budgets else ""
        if p.get("image"):
            media = f'<a class="watch-media" href="{esc(href)}" tabindex="-1" aria-hidden="true">{self.media(p)}</a>'
        else:
            media = f'<a class="watch-media watch-tile" href="{esc(href)}" tabindex="-1" aria-hidden="true">{self.dial_art(p)}</a>'
        label = (f'<p class="watch-label">{esc(watch_data.EDITORIAL_LABELS.get(p["editorial_labels"][0], ""))}</p>'
                 if p.get("editorial_labels") and p["editorial_labels"][0] in watch_data.EDITORIAL_LABELS else "")
        return (
            f'<article class="watch-card" style="{self.watch_theme(p)}" data-id="{esc(p["id"])}" data-name="{esc(brand + " " + p["model"])}" data-brand="{esc(p["brand"])}" '
            f'data-gender="{esc(" ".join(p["gender"]))}" data-style="{esc(" ".join(p["styles"]))}" data-budget="{esc(" ".join(self.qualifies(p)) or "unlisted")}" data-own="{esc(p.get("budget") or "")}" data-styles="{esc(" ".join(p["styles"]))}" '
            + " ".join(f'data-{key}="{esc(" ".join(v for v in getter(self, p) if v))}"' for key, _, _, getter in self.FILTERS) + '>'
            + media + '<div class="watch-body">'
            f'<p class="watch-meta"><span class="watch-brand">{esc(brand)}</span>' + (f'<span class="watch-band">{esc(self.band_range(p))}</span>' if band else "") + '</p>'
            + label + f'<h3 class="watch-model"><a href="{esc(href)}">{esc(p["model"])}</a></h3>'
            + self.spec_rows(p) + self.facts_line(p) +
            f'<div class="watch-product-bottom"><div class="watch-actions">{self.check_price(p, include_more=False)}</div></div></div></article>')

    def facts_line(self, p):
        """One short line of the same facts for phone cards (case size, movement, strap); the 2 x 2 fact boxes are shown on larger screens."""
        mm = p.get("case_diameter_mm")
        strap = " ".join(x for x in (((p.get("band_colour") or [""])[0]).replace("-", " ").title(), (p.get("band_material") or "").replace("-", " ")) if x)
        bits = [f"{mm:g} mm" if mm else "", (p.get("movement") or "").title(), strap]
        text = " \u00b7 ".join(b for b in bits if b)
        return f'<p class="watch-facts">{esc(text)}</p>' if text else ""

    def spec_rows(self, p):
        """Compact facts on a card: best for (only when approved), case size, movement, strap, water resistance. The rest stays on the product page."""
        mm, metres = p.get("case_diameter_mm"), p.get("water_resistance_metres")
        strap = " ".join(x for x in (((p.get("band_colour") or [""])[0]).replace("-", " ").title(), (p.get("band_material") or "").replace("-", " ")) if x)
        rows = [("Best for", p.get("best_for", "")), ("Case size", f"{mm:g} mm" if mm else ""), ("Movement", (p.get("movement") or "").title()),
                ("Strap", strap), ("Water resistance", f"{metres:g} m" if metres else "")]
        items = "".join(f'<div><dt>{label}</dt><dd>{esc(value)}</dd></div>' for label, value in rows if value)
        return f'<dl class="watch-spec-rows">{items}</dl>' if items else ""

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
        dates = [p.get("last_verified") or p.get("updated") or self.config_updated for p in products]
        return max(dates) if dates else self.config_updated

    @staticmethod
    def human_date(iso):
        try:
            y, m, d = (int(x) for x in str(iso).split("-"))
            return f"{d} {('January February March April May June July August September October November December').split()[m - 1]} {y}"
        except (ValueError, IndexError):
            return str(iso)

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
        ("dial", "Case size", [(a, b) for a, b, _, _ in DIAL_SIZES], lambda self, p: [self.bucket(self.DIAL_SIZES, p.get("case_diameter_mm"))]),
        ("strapmat", "Strap material", [("leather", "Leather"), ("stainless-steel", "Stainless Steel"), ("brass", "Brass"), ("ceramic", "Ceramic"), ("metal", "Metal (type not stated)"), ("mesh", "Mesh"), ("silicone-rubber", "Silicone / Rubber"), ("fabric-nylon", "Fabric / Nylon")], lambda self, p: [p.get("band_material", "")]),
        ("movement", "Movement", [("quartz", "Quartz"), ("automatic", "Automatic"), ("mechanical", "Mechanical")], lambda self, p: [p.get("movement", "")]),
        ("water", "Water resistance", [(a, b) for a, b, _, _ in WATER], lambda self, p: [self.bucket(self.WATER, p.get("water_resistance_metres"))]),
        ("dialcolour", "Dial colour", [(x, x.replace("-", " ").title()) for x in ("black", "white", "blue", "green", "silver", "gold", "champagne", "cream", "beige", "pink", "grey", "brown", "red")], lambda self, p: p.get("dial_colour", [])),
        ("strapcolour", "Strap colour", [(x, x.replace("-", " ").title()) for x in ("black", "brown", "green", "silver", "grey", "gold", "blue", "rose-gold", "red", "beige")], lambda self, p: p.get("band_colour", [])),
        ("shape", "Case shape", [("round", "Round"), ("oval", "Oval"), ("square", "Square"), ("rectangular", "Rectangular"), ("contemporary", "Contemporary")], lambda self, p: [p.get("case_shape", "")]),
        ("feature", "Features", [("date", "Date"), ("day-date", "Day-Date"), ("chronograph", "Chronograph"), ("luminous-hands", "Luminous hands"), ("second-hand", "Second hand"), ("world-time", "World time"), ("minimal-dial", "Minimal dial")], lambda self, p: p.get("features", [])),
        ("case", "Case material", CASES, lambda self, p: [p.get("case_material", "")]),
    ]

    @staticmethod
    def bucket(table, value):
        """Size and depth are matched to the nearest whole unit (40.2 mm is 40, 44.6 mm is 45), so a decimal never falls between two buckets.
        RULE: rounding is only for choosing the filter bucket. The stored value stays exact and is what cards and product pages display
        (40.2 mm stays "40.2 mm"). The same holds for water resistance. An unknown value gets no bucket and is never guessed."""
        if value is None:
            return ""
        value = int(value + 0.5)
        return next((slug for slug, _, lo, hi in table if lo <= value <= hi), "")

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
        band = (self.parse_collection_url(url) or {}).get("price_band")
        # a price page lists every watch under the band, but it earns its own URL only with enough watches that sit IN that band,
        # so "Under 3,000" never goes live as a copy of "Under 2,000"
        distinct = sum(1 for p in shown if p.get("budget") == band) if band else len(shown)
        return not (len(shown) >= self.min_index and distinct >= self.min_index and len(str(entry.get("intro", "")).split()) >= 100)

    def linkify(self, text):
        """[text](/path/) becomes a link only when the path is a published collection, a hub or the buying guide; otherwise plain text."""
        allowed = {c["url"] for c in self.published_collections()} | {"/watches/", "/watches/men/", "/watches/women/", "/watches/guide/"}
        def link(m):
            label, target = m.group(1), m.group(2)
            return f'<a href="{esc(target)}">{esc(label)}</a>' if target in allowed else esc(label)
        out, last = [], 0
        for m in re.finditer(r"\[([^\]]+)\]\((/[^)\s]*)\)", text):
            out.append(esc(text[last:m.start()])); out.append(link(m)); last = m.end()
        out.append(esc(text[last:]))
        return "".join(out)

    def collection_copy(self, url):
        entry = self.approved.get(url)
        if not entry or len(str(entry.get("intro", "")).split()) < 100:
            return ""
        faqs = "".join(f'<details class="faq-item"><summary><h3>{esc(f["q"])}</h3><span class="faq-chev" aria-hidden="true"></span></summary><p>{esc(f["a"])}</p></details>'
                       for f in entry.get("faqs", []))
        parts = [f'<p>{self.linkify(entry["intro"])}</p>']
        if entry.get("who_for"):
            parts.append(f'<h3>Who this page is for</h3><p>{self.linkify(entry["who_for"])}</p>')
        if entry.get("advice"):
            parts.append(f'<h3>Buying advice</h3><p>{self.linkify(entry["advice"])}</p>')
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

    CHOOSE = [("Budget", "Decide your price band first. At lower budgets, expect simple quartz watches and compare build details rather than extras."),
              ("Case size", "Match the case to your wrist: under 37 mm suits smaller wrists, 37 to 40 mm is a common everyday range, and 41 mm and above looks bolder."),
              ("Strap", "Leather has a classic, dressier look. A metal strap is usually easier to clean and adjust."),
              ("Water resistance", "30 m means splash resistant: fine for handwashing and rain, not for swimming. Check the listing for the exact rating.")]
    TIPS = [("Choosing your case size", "Case size"), ("Leather or metal strap?", "Strap"), ("What does 30 m water resistance mean?", "Water resistance")]

    def hub_html(self):
        """The part of /watches/ that sits below the watches: links to the published collections (plain text links, real pages), a collapsed How to choose,
        the buying guides and a short explanation. Nothing is repeated above the watches: brand, price and Men / Women already have their own controls there.
        Returns (top, bottom); top is empty."""
        pubs = [c for c in self.published_collections() if c["featured_on_watch_hub"]]
        order = list(self.budgets)
        pubs.sort(key=lambda c: (order.index(c["price_band"]) if c.get("price_band") in order else -1, c["label"]))
        items = []
        for c in pubs:
            band = self.budgets[c["price_band"]]["label"] if c.get("price_band") else ""
            text = f'{c["label"]} \u00b7 {band}' if band else c["label"]
            items.append(f'<li><a href="{esc(c["url"])}">{esc(text)}</a> ({c["count"]})</li>')
        for g, info in self.genders.items():
            count = sum(1 for p in self.products if g in p["gender"])
            if count:
                items.append(f'<li><a href="/watches/{esc(g)}/">{esc(info["label"])} watches</a> ({count})</li>')
        sep = " \u00b7 "
        collections = f'<div><h2>Collections</h2><ul class="lx-links">{"".join(items)}</ul></div>' if items else ""

        choose = self.CHOOSE
        cards = "".join(f'<li><h3>{t}</h3><p>{d}</p></li>' for t, d in choose)
        guides = [("How to choose a watch", "/watches/guide/")] + [(g["title"], g["url"]) for g in self.config.get("hub_guides", [])]
        links = "".join(f'<li><a href="{esc(u)}">{esc(t)}</a></li>' for t, u in guides)
        intro = ("Use this page to find a watch you can compare properly. Start with a budget, a brand or a style, or choose Men or Women, then narrow the list "
                 "by strap material, case size, dial colour, movement or water resistance. Collection pages gather watches in one place, with the specifications "
                 "exactly as the seller lists them. Anything a listing does not state is shown as unknown, never guessed. Prices change often, so check the "
                 "current price on Amazon before you buy.")
        bottom = ('<section class="hub-after" aria-label="About these watches"><div class="lx-guide">' + collections +
                  f'<div><h2>Buying guides</h2><ul class="lx-links">{links}</ul></div></div>'
                  f'<details class="hub-details"><summary>How to choose a watch</summary><ul class="hub-choose-cards">{cards}</ul></details>'
                  f'<p class="hub-intro">{esc(intro)}</p></section>')
        return "", bottom

    # search phrase fragment -> (filter group, value); the first match wins, so "rose gold" is tested before "gold"
    KEYWORD_FILTERS = [("leather strap", "style", "leather-strap"), ("metal strap", "style", "metal-strap"), ("black dial", "dialcolour", "black"),
                       ("blue dial", "dialcolour", "blue"), ("rose gold", "strapcolour", "rose-gold"), ("gold", "strapcolour", "gold"),
                       ("quartz", "movement", "quartz"), ("small dial", "dial", "36-and-under"), ("office", "occasion", "office"),
                       ("formal", "occasion", "formal"), ("everyday", "occasion", "everyday"), ("classic", "style", "classic"),
                       ("minimalist", "style", "minimal"), ("elegant", "style", "elegant")]

    def keyword_chips(self, url, shown):
        """Quick-filter chips for a page's search phrases (keywords.json). A chip exists only when its phrase maps to a filter and at least one
        watch matches, so editorial phrases (formal, office, minimalist ...) stay hidden until those tags are approved and assigned."""
        entry = self.keywords.get(url) or {}
        getters = {key: getter for key, _, _, getter in self.FILTERS}
        out = ""
        for g, info in self.genders.items():
            seen, chips = set(), ""
            for phrase in entry.get(g, []):
                spec = next(((grp, val) for kw, grp, val in self.KEYWORD_FILTERS if kw in phrase.lower()), None)
                if not spec or spec in seen:
                    continue
                grp, val = spec
                if not any(g in p["gender"] and val in (p["styles"] if grp == "style" else getters[grp](self, p)) for p in shown):
                    continue
                seen.add(spec)
                label = re.sub(r"\s+under\s+\u20b9[\d,]+$", "", re.sub(r"^\w+\s+", "", phrase)) if phrase.split()[0].lower() in self.brands else phrase
                chips += (f'<button type="button" class="watch-chip" data-quick-chip="{esc(grp)}" data-value="{esc(val)}" data-chip-gender="{esc(g)}" aria-pressed="false">'
                          f'{esc(label[:1].upper() + label[1:])}</button>')
            if chips:
                out += f'<div class="watch-quick-group"><h3>Popular for {esc(info["adjective"])}</h3><div class="watch-chip-row">{chips}</div></div>'
        return out

    def price_steps(self):
        """Price-band slider steps: every band that has at least one watch under it (lowest first), with the number of watches whose own band it is."""
        return [(slug_, info["label"], "\u20b9" + (f'{info["max"] // 1000}k' if info.get("max") else ""), sum(1 for p in self.products if p.get("budget") == slug_))
                for slug_, info in self.budgets.items() if any(slug_ in self.qualifies(p) for p in self.products)]

    def collection_tables(self, table, shown):
        """table=True gives one comparison table; a list of (heading, watches) gives one table per shopper section (for example Men and Women)."""
        if not table:
            return ""
        if table is True:
            return self.collection_table(shown)
        return "".join(self.collection_table(ps, heading=h) for h, ps in table)

    def related_collections(self, url):
        """Other published collections, same brand or price band first. Empty (nothing shown) until a second collection is published."""
        me = next((c for c in self.published_collections() if c["url"] == url), None)
        others = [c for c in self.published_collections() if c["url"] != url]
        if not me or not others:
            return ""
        others.sort(key=lambda c: -((c.get("brand") == me.get("brand") and bool(me.get("brand"))) + (c.get("price_band") == me.get("price_band") and bool(me.get("price_band")))))
        pills = "".join(f'<li><a class="hub-pill" href="{esc(c["url"])}">{esc(c["title"])} <span class="hub-count">{c["count"]}</span></a></li>' for c in others[:8])
        return f'<nav class="watch-related" aria-labelledby="related-collections"><h2 id="related-collections">Related watch collections</h2><ul class="hub-pills">{pills}</ul></nav>'

    def collection_table(self, products, heading="Compare these watches"):
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
        return (f'<section class="watch-collection-table"><h2>{esc(heading)}</h2><div class="compare-table-wrap"><table class="compare-table" role="table">'
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
        steps = self.price_steps()
        ladder = collection.price_slider(steps, dual=True, title="Budget")
        quick = self.keyword_chips(url, shown)
        order = list(self.budgets)
        pubs = sorted([c for c in self.published_collections() if c["featured_on_watch_hub"] and c.get("price_band") in order],
                      key=lambda c: (order.index(c["price_band"]), c["label"])) if hub else []
        curated = ('<p class="ladder-curated"><span>Curated</span>' + " ".join(
            f'<a href="{esc(c["url"])}">{esc(c["label"])} {esc(self.budgets[c["price_band"]]["label"].lower())}</a>' for c in pubs) + '</p>') if pubs else ""
        chips_html = '<div class="lx-chips">'
        if len(steps) >= 2:
            chips_html += '<button type="button" class="lx-chip" data-filter-open data-jump="budget" aria-haspopup="dialog"><span>Budget</span><b data-chip-val="budget"></b></button>'
        if len(active) >= 2:
            chips_html += '<button type="button" class="lx-chip" data-filter-open data-jump="brand" aria-haspopup="dialog"><span>Brand</span><b data-chip-val="brand"></b></button>'
        chips_html += '</div>'
        quick_row = f'<div class="lx-quick" data-quick-controls hidden>{quick}</div>' if quick else ""
        headline, sub = (("Timeless Watches. Smart Choices.", "Discover classic and analog watches by budget, brand, style and fit.") if hub else (title, intro))
        reviewed = (f'<span class="lx-reviewed">Last reviewed: <time datetime="{esc(self.updated(shown))}">{esc(self.human_date(self.updated(shown)))}</time></span>' if shown else "")
        hero = ('<header class="lx-hero"><div class="lx-hero-text"><p class="lx-kicker">The SAT watch edit</p>'
                f'<h1 data-default="{esc(headline)}">{esc(headline)}</h1><p class="lx-sub">{esc(sub)}</p></div><!--segments--></header>')
        footline = f'<p class="lx-foot">{reviewed} <a class="lx-fit" href="/watches/guide/">Find your fit &rarr;</a></p>'
        top = hero + quick_row
        counts = {slug_: n(lambda p, s=slug_: s in p["styles"]) for slug_ in self.styles}
        style_cards = "".join(
            f'<li><a class="lx-style" href="/watches/style/{slug_}/" data-style-toggle="{esc(slug_)}" aria-current="{"true" if slug_ == style else "false"}">'
            f'<span class="lx-s-name">{esc(value["label"])}</span><span class="lx-s-count">{counts[slug_]} {"watch" if counts[slug_] == 1 else "watches"}</span></a></li>'
            for slug_, value in self.styles.items() if counts[slug_])
        after = (f'<section class="lx-sec lx-styles" aria-labelledby="lx-styles"><div class="lx-sec-head"><h2 id="lx-styles">Shop by style</h2></div><ul class="lx-style-grid">{style_cards}</ul></section>'
                 if style_cards else "")
        tips = ""
        if hub:
            by = dict(self.CHOOSE)
            tips = "".join(f'<aside class="watch-tip" data-tip hidden><p class="lx-tip-k">Good to know</p><h3>{esc(t)}</h3><p>{esc(by[k])}</p></aside>' for t, k in self.TIPS)
        hub_top, hub_bottom = hub or ("", "")
        note = ('<p class="watch-affiliate-note">Amazon links on this page are affiliate links. As an Amazon Associate I earn from qualifying purchases. '
                '<a href="/affiliate-disclosure/">How we earn</a></p>') if any(self.merchant_links(p) for p in shown) else ""
        card_html = [self.card(p) for p in products]
        lead_at = next((i for i, p in enumerate(products) if matches(p)), None)
        if lead_at is not None and len(shown) >= 4:
            card_html[lead_at] = card_html[lead_at].replace('class="watch-card"', 'class="watch-card is-lead"', 1)
        block = collection.render(card_html, groups, uid="watch-collection", title="Explore watches", noun="watch", plural="watches",
                                  preset_gender=gender, genders=[("men", "Men"), ("women", "Women")],
                                  top_html=top, visible=[matches(p) for p in products], page_size=24, grid_note=note,
                                  panel_top=ladder + curated, after_html=after, tips_html=tips, controls_html=chips_html, main_toolbar=True)
        body = ('<section class="section watch-store" data-mobile-grid="two"><div class="container watch-store-inner">{{breadcrumb}}' + hub_top + block + footline + hub_bottom + self.collection_tables(table, shown) + self.collection_copy(url) + self.related_collections(url) + extra_html + '<noscript><nav class="watch-static-links" aria-label="Browse watches"><a href="/watches/men/">Men</a> · <a href="/watches/women/">Women</a> · ' + ' · '.join(f'<a href="/watches/brands/{esc(slug)}/">{esc(value["name"])}</a>' for slug, value in self.brands.items() if slug != 'sample') + '</nav></noscript></div></section>')
        meta = self._meta(url, title, intro, body, crumbs or [["Watches", "/watches/"]], shown, js=False)
        meta["noindex"] = self.collection_noindex(url, shown)
        meta["css"] += ["collection", "watch-store", "price-slider", "watch-luxe"]
        meta["js"] = ["collection", "watch-tilt"]
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
                band = next((d[1] for d in (a, b) if d is not None and d[0] == "budget"), None)
                if band and sum(1 for p in items if p.get("budget") == band) < self.min_index:
                    continue   # a price page needs enough watches inside its own band, not only watches from cheaper bands
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
        shown = [p for p in self.products if p["brand"] == brand and budget in self.qualifies(p)]
        ready = not self.collection_noindex(url, shown)
        lead = "Best " if ready else ""
        title = f'{lead}{br["name"]} Watches {bd["label"]}'
        intro = f'{br["name"]} watches {bd["label"].lower()}, for men and women. Compare the published details and confirm the current price at the retailer.'
        sections = [(f'{lead}{br["name"]} Watches {bd["label"]} for {info["adjective"].title()}', [p for p in shown if g in p["gender"]])
                    for g, info in self.genders.items()]
        return self.catalog(url, title, intro, brand=brand, budget=budget, table=[(h, ps) for h, ps in sections if ps],
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
            section("Why consider it", f'<p>{esc(why)}</p>' if why else "")
            + section("Best for", f'<p>{esc(p["best_for"])}</p>' if p.get("best_for") else "")
            + section("Key specifications", dl + miss + provenance)
            + section("What we like", ul(p.get("good", [])))
            + section("What to know before buying", ul(p.get("not_good", [])))
            + section("Fit and size", f"<p>{esc(fit)}</p>" if fit else "")
            + section("Water resistance explained", f"<p>{esc(wr)}</p>" if wr else "")
            + section("Who should buy it", ul(p.get("who_should_buy", [])))
            + section("Who should skip it", ul(p.get("who_should_skip", [])))
            + section("Alternatives", self.grid(alts) if alts else "")
            + section("Questions shoppers ask", faq)
            + f'<div class="watch-cta-row watch-cta-end">{self.check_price(p, small=False, include_more=False)}</div>')

    def product_hero(self, p, title):
        """The top of a product page: the drawing on a light display, the brand, the name with its price band, the key facts and the Check price button."""
        brand = self.brands[p["brand"]]["name"]
        band = self.band_range(p)
        label = watch_data.EDITORIAL_LABELS.get((p.get("editorial_labels") or [""])[0], "")
        return ('<div class="watch-pdp">'
                f'<div class="watch-pdp-photo">{self.dial_art(p)}<span class="tile-brand">{esc(brand)}</span>' + (f'<span class="tile-band">{esc(band)}</span>' if band else "") + '</div>'
                '<div class="watch-pdp-info">'
                f'<p class="watch-kicker">{esc(brand)}' + (f' \u00b7 {esc(label)}' if label else "") + f'</p><h1>{esc(title)}</h1>'
                + self.spec_rows(p) +
                f'<div class="watch-cta-row">{self.check_price(p, small=False, include_more=False)}</div>'
                '<p class="watch-pdp-note">Specifications are as listed by the seller. Check the price and the colour on the Amazon page before you buy.</p>'
                '</div></div>')

    def product_page(self, p):
        brand = self.brands[p["brand"]]["name"]
        url = self.review_url(p)
        title = p["product_name"] if p["product_name"].lower().startswith(brand.lower()) else brand + " " + p["model"]
        body = (f'<section class="section watch-pdp-wrap" style="{self.watch_theme(p)}"><div class="container content-page watch-page watch-product-page">{{{{breadcrumb}}}}'
                + self.product_hero(p, title) + self.product_detail(p) +
                '<p><a class="btn btn-outline" href="/watches/">Explore all watches &rarr;</a></p></div></section>')
        short = title if len(title) <= 52 else title[:52].rsplit(" ", 1)[0]  # the page <title> stays within the search-result length
        meta = self._meta(url, short, p["verdict"], body, [["Watches", "/watches/"], [brand, f'/watches/brands/{p["brand"]}/'], [p["model"], url]], [p], js=False)
        # a page without any written review stays out of Google until it has one
        meta["noindex"] = not (p.get("paragraphs") or p.get("editorial_notes"))
        meta["css"] += ["watch-store"]
        meta["js"] = ["watch-tilt"]
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
