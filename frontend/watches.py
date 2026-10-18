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
import urllib.parse
import collection
import cards as ui
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
        badge_key = (p.get("editorial_labels") or [""])[0]
        badge = f'<span class="watch-badge">{esc(watch_data.EDITORIAL_LABELS[badge_key])}</span>' if badge_key in watch_data.EDITORIAL_LABELS else ""
        fav = (f'<button type="button" class="watch-fav" data-fav="{esc(p["id"])}" aria-pressed="false" aria-label="Save {esc(p["model"])}">'
               '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-9-9a5 5 0 0 1 9-3 5 5 0 0 1 9 3c-2 4.6-9 9-9 9z"/></svg></button>')
        art = f'<div class="watch-visual">{media}{badge}{fav}</div>'
        return (
            f'<article class="watch-card" style="{self.watch_theme(p)}" data-id="{esc(p["id"])}" data-name="{esc(brand + " " + p["model"])}" data-brand="{esc(p["brand"])}" '
            f'data-gender="{esc(" ".join(p["gender"]))}" data-style="{esc(" ".join(p["styles"]))}" data-budget="{esc(" ".join(self.qualifies(p)) or "unlisted")}" data-own="{esc(p.get("budget") or "")}" data-styles="{esc(" ".join(p["styles"]))}" '
            + " ".join(f'data-{key}="{esc(" ".join(v for v in getter(self, p) if v))}"' for key, _, _, getter in self.FILTERS) + '>'
            + art + '<div class="watch-body">'
            f'<p class="watch-meta"><span class="watch-brand">{esc(brand)}</span>' + (f'<span class="watch-band">{esc(self.band_range(p))}</span>' if band else "") + '</p>'
            + f'<h3 class="watch-model"><a href="{esc(href)}">{esc(p["model"])}</a></h3>'
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
        ("strapmat", "Strap material", [("leather", "Leather"), ("stainless-steel", "Stainless Steel"), ("brass", "Brass"), ("ceramic", "Ceramic"), ("resin", "Resin"), ("plastic", "Plastic"), ("polyurethane", "Polyurethane"), ("metal", "Metal (type not stated)"), ("mesh", "Mesh"), ("silicone-rubber", "Silicone / Rubber"), ("fabric-nylon", "Fabric / Nylon")], lambda self, p: [p.get("band_material", "")]),
        ("movement", "Movement", [("quartz", "Quartz"), ("automatic", "Automatic"), ("mechanical", "Mechanical")], lambda self, p: [p.get("movement", "")]),
        ("water", "Water resistance", [(a, b) for a, b, _, _ in WATER], lambda self, p: [self.bucket(self.WATER, p.get("water_resistance_metres"))]),
        ("dialcolour", "Dial colour", [(x, x.replace("-", " ").title()) for x in ("black", "white", "blue", "green", "silver", "gold", "champagne", "cream", "beige", "pink", "rose-gold", "grey", "brown", "red")], lambda self, p: p.get("dial_colour", [])),
        ("strapcolour", "Strap colour", [(x, x.replace("-", " ").title()) for x in ("black", "brown", "green", "silver", "grey", "gold", "blue", "rose-gold", "red", "beige")], lambda self, p: p.get("band_colour", [])),
        ("display", "Display", [("analog", "Analog"), ("digital", "Digital")], lambda self, p: [p.get("display_type", "")]),
        ("shape", "Case shape", [("round", "Round"), ("oval", "Oval"), ("square", "Square"), ("rectangular", "Rectangular"), ("tonneau", "Tonneau"), ("contemporary", "Contemporary")], lambda self, p: [p.get("case_shape", "")]),
        ("feature", "Features", [("date", "Date"), ("day-date", "Day-Date"), ("chronograph", "Chronograph"), ("luminous-hands", "Luminous hands"), ("second-hand", "Second hand"), ("world-time", "World time"), ("minimal-dial", "Minimal dial"), ("alarm", "Alarm"), ("led-light", "LED light"), ("stopwatch", "Stopwatch")], lambda self, p: p.get("features", [])),
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
        if len(parts) == 1 and parts[0] in self.budgets:
            return {"price_band": parts[0]}      # /watches/under-5000/: every brand, one price band
        if len(parts) == 1 and parts[0] == "premium":
            return {"premium": True}             # /watches/premium/: watches above the last shopper tier
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

    def collection_name(self, brand="", gender="", style="", band="", best=False):
        """The one canonical name of a collection page, for the title, menu, cards, related links and search: "Best Titan Watches Under \u20b93,000"
        ("Best" only once the page is published). Everything that names a collection calls this or reads display_title from published_collections()."""
        name = (self.brands[brand]["name"] if brand else self.genders[gender]["label"] if gender else self.styles[style]["label"] if style else "")
        label = self.budgets[band]["label"] if band else ""
        return ("Best " if best else "") + (f"{name} Watches" if name else "Watches") + (f" {label}" if label else "")

    def page_title(self, url, premium=False, **key):
        """The title and H1 of a collection page: the canonical seo_title once published (so an override in collections.json applies), else the plain name."""
        rec = next((c for c in self.published_collections() if c["url"] == url), None)
        if rec:
            return rec["seo_title"]
        return self.premium_heading() if premium else self.collection_name(**key)

    def published_collections(self):
        """The canonical collection records, one per published, indexable collection page (approved in collections.json with its own introduction and
        enough watches). Every menu, card, link and count on the Watches pages reads from these records.
        Fields: id, category, url/href, brand, brand_name, price_band, gender, genders, count (live), published, indexable, seo_status, featured,
        featured_on_watch_hub, priority (lower first), seo_title, display_title, short_label, description, and the older label, title, heading, summary.
        collections.json may override display_title, short_label, seo_title, summary (the one-line description), featured, priority and featured_on_watch_hub."""
        out = []
        for url, entry in self.approved.items():
            key = self.parse_collection_url(url)
            if not key:
                continue
            shown = [p for p in self.products if (not key.get("gender") or key["gender"] in p["gender"]) and (not key.get("brand") or p["brand"] == key["brand"])
                     and (not key.get("price_band") or key["price_band"] in self.qualifies(p)) and (not key.get("style") or key["style"] in p["styles"])
                     and (not key.get("premium") or p.get("budget") in self.premium_bands())]
            if self.collection_noindex(url, shown):
                continue
            band = self.budgets[key["price_band"]]["label"] if key.get("price_band") else ""
            name = (self.brands[key["brand"]]["name"] if key.get("brand") else self.genders[key["gender"]]["label"] if key.get("gender") else
                    self.styles[key["style"]]["label"] if key.get("style") else "Premium" if key.get("premium") else "")
            broad = not (key.get("brand") or key.get("gender") or key.get("style"))    # a price page for every brand
            seo = str(entry.get("seo_title") or "").strip() or (("Best Premium Watches in India" if key.get("premium") else f"Best Watches {band} in India") if broad else
                  self.collection_name(brand=key.get("brand", ""), gender=key.get("gender", ""), style=key.get("style", ""), band=key.get("price_band", ""), best=True))
            display = str(entry.get("display_title") or "").strip() or (("Best Premium Watches" if key.get("premium") else f"Best Watches {band}") if broad else seo)
            short = str(entry.get("short_label") or "").strip() or ((self.premium_label() if key.get("premium") else band) if broad else f"{name} \u00b7 {band}" if band else name)
            desc = str(entry.get("summary") or "").strip() or (" ".join(x for x in (f"{len(shown)}", name if not key.get("premium") else "premium", "watches", band.lower()) if x) + " to compare.")
            out.append({"id": url.strip("/").replace("/", "-"), "category": "watches", "url": url, "href": url, **key, "genders": sorted({g for p in shown for g in p["gender"]}), "count": len(shown),
                        "brand_name": self.brands[key["brand"]]["name"] if key.get("brand") else "", "premium": bool(key.get("premium")), "published": True, "indexable": True, "seo_status": "indexable",
                        "featured": bool(entry.get("featured")), "priority": entry.get("priority", 100),
                        "featured_on_watch_hub": entry.get("featured_on_watch_hub", True) is not False,
                        "seo_title": seo, "display_title": display, "short_label": short, "description": desc,
                        "label": name or band, "title": f"{name} watches {band.lower()}".strip() if band else f"{name} watches", "heading": display, "summary": desc})
        return out

    def ordered_collections(self, pubs=None):
        """Collections in the order shoppers should meet them: featured first, then the owner's priority number, then wider pages before brand pages, then the budget
        progression (lowest band first), then the strongest product count."""
        order = list(self.budgets)
        pubs = self.published_collections() if pubs is None else pubs
        return sorted(pubs, key=lambda c: (not c["featured"], c["priority"], bool(c.get("brand") or c.get("style")), order.index(c["price_band"]) if c.get("price_band") in order else (len(order) if c.get("premium") else -1),
                                          -c["count"], c["display_title"]))

    # ---- collection service: the same records, grouped for the places that need them
    def collections_by_budget(self):
        out = {}
        for c in self.ordered_collections():
            if c.get("price_band"):
                out.setdefault(c["price_band"], []).append(c)
        return out

    def collections_by_brand(self):
        out = {}
        for c in self.ordered_collections():
            if c.get("brand"):
                out.setdefault(c["brand"], []).append(c)
        return out

    def collection_counts(self):
        return {c["href"]: c["count"] for c in self.published_collections()}

    def popular_collection_records(self, limit=None):
        pubs = self.ordered_collections([c for c in self.published_collections() if c["featured_on_watch_hub"]])
        return pubs[:limit] if limit else pubs

    # ---- budget discovery: the shopper price tiers, built from the whole live catalogue (the approved SEO pages are a separate thing, see published_collections)
    DEFAULT_TIERS = ["under-1000", "under-2000", "under-3000", "under-5000", "under-10000", "under-20000"]
    DEFAULT_MENU = ["under-3000", "under-5000", "under-10000", "under-20000", "premium"]
    PREMIUM_NOTE = "Explore higher-budget watches from the premium end of the current SAT catalogue."   # neutral default until the owner approves other wording

    def discovery_config(self):
        """settings.json budget_discovery with safe defaults. Every part is optional: a missing or malformed block falls back to the defaults, a slug that is not a
        price band is ignored, and Premium starts above the last tier when premium_after is not set. It never raises."""
        cfg = self.settings.get("budget_discovery")
        cfg = cfg if isinstance(cfg, dict) else {}
        tiers = [b for b in (cfg["tiers"] if isinstance(cfg.get("tiers"), list) else self.DEFAULT_TIERS) if b in self.budgets]
        after = cfg.get("premium_after") if cfg.get("premium_after") in self.budgets else (tiers[-1] if tiers else "")
        menu = [m for m in (cfg["menu"] if isinstance(cfg.get("menu"), list) else self.DEFAULT_MENU) if isinstance(m, str)]
        return {"tiers": tiers, "premium_after": after, "menu": menu, "descriptions": cfg["descriptions"] if isinstance(cfg.get("descriptions"), dict) else {}}

    def premium_bands(self):
        """Price bands above the last shopper tier (budget_discovery.premium_after): a watch in one of these is Premium."""
        order = list(self.budgets)
        after = self.discovery_config()["premium_after"]
        return order[order.index(after) + 1:] if after in order else []

    def hub_affiliate(self):
        """The owner's Amazon link for the watch pictures on the hub (settings hub_affiliate), as {url, label}, or None. Only while affiliate links are on."""
        cfg = self.settings.get("hub_affiliate")
        url = str(cfg.get("url") or "").strip() if isinstance(cfg, dict) else ""
        if not (self.affiliate_active and url.startswith("https://")):
            return None
        return {"url": url, "label": str(cfg.get("label") or "Shop watches on Amazon").strip()}

    def tier_affiliate(self, t, aff):
        """The owner's Amazon link for one budget card: the supplied url with only the search words (k) and Amazon's price limit (rh) changed, so an Under 2,000
        card searches for watches under 2,000 and shows only those. Everything else in the link (tag, linkCode, linkId, ref_, i) is kept as supplied.
        Prices are in paise on Amazon (rh=p_36:-200000 means up to 2,000; rh=p_36:2000000- means 20,000 and above). Returns None without a base link."""
        if not aff:
            return None
        cfg = self.settings.get("hub_affiliate") if isinstance(self.settings.get("hub_affiliate"), dict) else {}
        premium = t["kind"] == "premium"
        low = self.budgets[self.discovery_config()["premium_after"]]["max"] if premium and self.discovery_config()["premium_after"] in self.budgets else 0
        high = int(t.get("max") or 0)
        template = str(cfg.get("premium_keyword" if premium else "keyword") or ("watches above {min}" if premium else "watches under {max}"))
        words = template.replace("{min}", str(low)).replace("{max}", str(high)).strip()
        parts = urllib.parse.urlsplit(aff["url"])
        pairs = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)]
        swapped = False
        out = []
        for k, v in pairs:
            if k == "k":
                out.append((k, words)); swapped = True
            elif k != "rh":
                out.append((k, v))
        if not swapped:
            out.insert(0, ("k", words))
        if cfg.get("price_filter", True) and (high or low):
            out.append(("rh", f"p_36:{low * 100}-" if premium else f"p_36:-{high * 100}"))
        link = urllib.parse.urlunsplit(parts._replace(query=urllib.parse.urlencode(out)))
        what = f"watches above \u20b9{low:,}" if premium else f"watches under \u20b9{high:,}"
        return {"url": link, "label": aff["label"], "search": what}

    def premium_heading(self):
        after = self.discovery_config()["premium_after"]
        return f"Premium Watches Above \u20b9{self.budgets[after]['max']:,}" if after in self.budgets else "Premium Watches"

    def premium_ui(self):
        """The Premium filter as the page script needs it, as JSON: where it starts and ends and the one shopper-facing label ('₹20,000+') and heading.
        The script shows this one label in place of the two internal filters (a top band and a lower limit). Empty when there is no premium watch."""
        top = self.premium_top()
        if not top:
            return ""
        return json.dumps({"from": self.discovery_config()["premium_after"], "top": top, "label": self.premium_label(), "heading": self.premium_heading()}, ensure_ascii=False)

    def premium_label(self):
        after = self.discovery_config()["premium_after"]
        return f"\u20b9{self.budgets[after]['max']:,}+" if after in self.budgets else ""

    @staticmethod
    def brand_list_text(names):
        """'Titan', 'Titan and Fossil', 'Titan, Fossil and Casio', then 'Titan, Fossil, Casio and 1 more brand' / '... and 4 more brands'."""
        if len(names) <= 1:
            return names[0] if names else ""
        if len(names) <= 3:
            return ", ".join(names[:-1]) + " and " + names[-1]
        more = len(names) - 3
        return ", ".join(names[:3]) + f" and {more} more brand{'' if more == 1 else 's'}"

    def budget_discovery(self):
        """One record per shopper price tier, from every live watch that has a known price band (a watch without one joins no tier): Under tiers are
        cumulative (a watch in a lower band also counts under a higher one, like the filter), Premium holds the watches above the last tier.
        Fields: id, kind ('budget' or 'premium'), tier (1 to 7, the colour), amount, eyebrow, count, brands (names), brand_slugs, brand_line, seo_title,
        display_title, short_label, description, page_url, has_page, href (the approved page when published, else a filter link), destination ('seo-page' or 'filter')."""
        cfg = self.discovery_config()
        tiers, overrides = cfg["tiers"], cfg["descriptions"]
        published = {c["url"] for c in self.published_collections()}
        active = [s for s, _, _ in self.active_brands()]
        def summarize(items):
            counts = {}
            for p in items:
                counts[p["brand"]] = counts.get(p["brand"], 0) + 1
            slugs = sorted(counts, key=lambda s: (-counts[s], active.index(s) if s in active else len(active)))
            return slugs, [self.brands[s]["name"] for s in slugs]
        def record(id_, kind, items, **fields):
            slugs, names = summarize(items)
            line = " \u00b7 ".join(names[:3]) + (f" +{len(names) - 3}" if len(names) > 3 else "")
            n = len(items)
            entry = self.approved.get(fields["page_url"]) or {}   # collections.json is authoritative: approved override, then generated default
            for key in ("seo_title", "display_title", "short_label"):
                if str(entry.get(key) or "").strip():
                    fields[key] = str(entry[key]).strip()
            fields.setdefault("heading", fields.get("display_title"))
            if str(entry.get("display_title") or "").strip():
                fields["heading"] = fields["display_title"]
            default = self.PREMIUM_NOTE if kind == "premium" else f'From {self.brand_list_text(names)}.'
            desc = str(entry.get("summary") or "").strip() or str(overrides.get(id_) or "").strip() or default
            has_page = fields["page_url"] in published
            return {"id": id_, "kind": kind, "count": n, "brands": names, "brand_slugs": slugs, "brand_line": line, "description": desc, "has_page": has_page,
                    "href": fields["page_url"] if has_page else fields["filter_url"], "destination": "seo-page" if has_page else "filter", "brand_name": "", "price_band": fields.get("price_band", ""), **fields}
        out = []
        for slug_ in tiers:
            items = [p for p in self.products if slug_ in self.qualifies(p)]
            if items:
                band = self.budgets[slug_]
                out.append(record(slug_, "budget", items, tier=self.budget_tier(band["max"]), amount="\u20b9" + format(band["max"], ","), eyebrow="Under", label=band["label"],
                                  seo_title=f'Best Watches {band["label"]} in India', display_title=f'Best Watches {band["label"]}', short_label=band["label"],
                                  page_url=f"/watches/{slug_}/", filter_url=f"/watches/?price={slug_}", max=band["max"], price_band=slug_))
        premium = [p for p in self.products if p.get("budget") in self.premium_bands()]
        if premium:
            top = max((p["budget"] for p in premium), key=list(self.budgets).index)
            after = cfg["premium_after"]
            out.append(record("premium", "premium", premium, tier=7, amount=self.premium_label(), eyebrow="Premium", label="Premium",
                              seo_title="Best Premium Watches in India", display_title="Premium Watches", heading=self.premium_heading(), short_label=self.premium_label(),
                              page_url="/watches/premium/", filter_url=f"/watches/?price={top}&from={after}", max=self.budgets[top]["max"]))
        return out

    def tier_meta(self, t):
        """A meta description for a tier page, written from the tier's own count and brands (so no two tiers share one). An approved meta_description wins
        (applied in catalog). Kept under 155 characters by naming fewer brands when needed."""
        names = t["brands"]
        for keep in range(min(len(names), 5), 0, -1):
            shown, more = names[:keep], len(names) - keep
            who = (", ".join(shown) + f" and {more} more brand{'' if more == 1 else 's'}") if more else self.brand_list_text(shown)
            if t["kind"] == "premium":
                text = f'Compare {t["count"]} higher-budget watches from {who}, with case size, movement, strap and water-resistance details.'
            else:
                text = f'Compare {t["count"]} watches {t["label"].lower()} from {who}, with case size, movement, strap and water-resistance details.'
            if len(text) <= 155:
                return text
        return text[:152].rstrip(" ,") + "..."

    def tier_seo_status(self, t):
        """Where a tier's own SEO page stands: published, approved but short of the rules, or not approved."""
        entry = self.approved.get(t["page_url"])
        if t["has_page"]:
            return "published and indexable"
        if not entry:
            return "not approved (filter link only)"
        words = len(str(entry.get("intro", "")).split())
        if words < 100:
            return f"approved but not published: intro has {words} of 100 words"
        return "approved but not published: too few watches in the tier"

    def menu_discovery(self, limit=5):
        """The tiers shown in the menu and in the filter sheet's Popular watch collections: the order set in settings (budget_discovery.menu), live tiers only."""
        by_id = {r["id"]: r for r in self.budget_discovery()}
        return [by_id[i] for i in self.discovery_config()["menu"] if i in by_id][:limit]

    def available_filters(self):
        """Every filter option that has at least one watch, with live counts: [(key, title, [(slug, label, count)])]."""
        out = []
        for key, title, options, getter in self.FILTERS:
            items = [(slug_, label, sum(1 for p in self.products if slug_ in getter(self, p))) for slug_, label in options]
            items = [i for i in items if i[2]]
            if items:
                out.append((key, title, items))
        return out

    def hub_html(self):
        """The part of /watches/ that sits below the watches: Continue your watch journey (curated collection cards, the buying guide, Find your fit) and
        How SAT helps you choose. Collections are the published pages, named by their canonical display_title. Returns (top, bottom); top is empty."""
        top3 = self.popular_collection_records(3)
        curated = ""
        if len(top3) >= 2:
            items = "".join(f'<li>{ui.collection_card(c)}</li>' for c in top3)
            curated = ('<div class="lx-curated"><div class="cur-head"><p class="lx-mk">Curated collections</p><h3>Curated for every budget</h3>'
                       '<p>Browse ready-made collections by brand and price, selected to make comparison easier.</p></div>'
                       f'<ul class="cur-grid" data-count="{len(top3)}">{items}</ul></div>')
        pool = [p for p in self.products if not p.get("sample")]
        art_a = self.art_copy(pool[min(1, len(pool) - 1)], "g1") if pool else ""
        art_b = self.art_copy(pool[min(5, len(pool) - 1)], "g2") if pool else ""
        guide = ui.feature_card("Watch buying guide", "Choose with confidence", "Understand case size, movement, strap type and water resistance before you buy.", "/watches/guide/", "Read the buying guide", art_a)
        fit = ui.feature_card("Find your fit", "Find a watch that feels right", "Start with your budget, style or wrist size and narrow down the options that suit you.", "#watch-filters", "Find your fit", art_b)
        how = [("Compare clearly", "See case size, strap, movement and water resistance exactly as the seller lists them."),
               ("No guessing", "Anything not stated stays unknown."),
               ("Check before buying", "Retailer prices change, so confirm the current price before purchase.")]
        how_cards = "".join(f'<li class="info-card"><h3>{esc(t)}</h3><p>{esc(d)}</p></li>' for t, d in how)
        lede = ("Use this page to find a watch you can compare properly. Start with a budget, a brand or a style, or choose Men or Women, "
                "then narrow the list by strap material, case size, dial colour, movement or water resistance. Anything a listing does not state is shown as unknown, never guessed.")
        bottom = ('<section class="hub-after" aria-label="About these watches">'
                  '<section class="lx-sec lx-more" aria-labelledby="lx-more"><div class="lx-sec-head"><div><h2 id="lx-more">Continue your watch journey</h2><p class="lx-sec-sub">Explore curated collections, learn what matters, or find the style that fits you.</p></div></div>'
                  f'{curated}<div class="lx-more-row" data-count="2">{guide}{fit}</div></section>'
                  '<section class="lx-sec lx-how" aria-labelledby="lx-how"><div class="lx-sec-head"><div><h2 id="lx-how">How SAT helps you choose</h2>'
                  f'<p class="lx-sec-sub lx-how-lede">{esc(lede)}</p></div></div><ul class="lx-how-row">{how_cards}</ul></section></section>')
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
        pills = "".join(f'<li><a class="hub-pill" href="{esc(c["url"])}">{esc(c["display_title"])} <span class="hub-count">{c["count"]}</span></a></li>' for c in others[:8])
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

    ICONS = {"budget": '<path d="M3 8h18v11H3zM3 8l3-4h12l3 4M15 13.5h3"/>', "brand": '<path d="M6 4h12l3 5-9 11L3 9zM3 9h18M9 4l3 5 3-5"/>',
             "style": '<circle cx="12" cy="12" r="5"/><path d="M9.5 3h5l-.8 4h-3.4zM9.5 21h5l-.8-4h-3.4zM12 9.5V12l1.8 1.2"/>',
             "more": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>'}

    def art_copy(self, p, tag):
        """A second copy of a watch drawing on the same page needs its own ids, or the browser mixes up their gradients."""
        svg = self.dial_art(p)
        for i in set(re.findall(r'id="([^"]+)"', svg)):
            svg = svg.replace(f'id="{i}"', f'id="{i}-{tag}"').replace(f"url(#{i})", f"url(#{i}-{tag})").replace(f'href="#{i}"', f'href="#{i}-{tag}"')
        return svg

    WATCH_GLYPH = '<svg viewBox="0 0 24 24"><rect x="8.5" y="2" width="7" height="4.5" rx="1.2"/><rect x="8.5" y="17.5" width="7" height="4.5" rx="1.2"/><circle cx="12" cy="12" r="5.4"/><path d="M12 9.4V12l1.9 1.3"/></svg>'

    def icon(self, name):
        return f'<svg viewBox="0 0 24 24" aria-hidden="true">{self.ICONS[name]}</svg>'

    def quick_row(self, steps, active, styles_live):
        """Four quick filters under the hero: icon, label, the current choice, chevron. Each opens the filter panel at that section."""
        items = []
        if len(steps) >= 2:
            items.append(("budget", "Budget", "Any price"))
        if len(active) >= 2:
            items.append(("brand", "Brand", "All brands"))
        if styles_live:
            items.append(("style", "Style", "All styles"))
        items.append(("more", "More filters", "Case size, Strap, etc."))
        return ('<nav class="qa-row" id="watch-filters" aria-label="Quick filters">' + "".join(
            f'<button type="button" class="qa" data-filter-open data-jump="{k}" aria-haspopup="dialog"><i class="qa-ico">{self.icon(k)}</i>'
            f'<span class="qa-t"><b>{label}</b><em data-qa-val="{k}" data-qa-default="{esc(default)}">{esc(default)}</em></span><i class="qa-chev" aria-hidden="true"></i></button>'
            for k, label, default in items) + '</nav>')

    def filter_count(self, flt):
        """Watches a discovery card's filter ({group, value}) would show."""
        group, value = flt["group"], flt["value"]
        if group == "budget":
            return [p for p in self.products if value in self.qualifies(p)]
        if group == "style":
            return [p for p in self.products if value in p["styles"]]
        getter = next((g for k, _, _, g in self.FILTERS if k == group), None)
        return [p for p in self.products if getter and value in getter(self, p)]

    def popular_collections(self, pubs):
        """'Popular watch collections' in the filter panel: one card per budget tier (budget_discovery records, in the given order). Hidden with fewer than two."""
        if len(pubs) < 2:
            return ""
        cards_html = "".join(f'<li>{ui.collection_card(c, "secondary")}</li>' for c in pubs)
        return (f'<section class="pc" aria-labelledby="pc-h"><h2 id="pc-h" class="pc-title">Popular watch collections</h2><ul class="pc-list" data-count="{len(pubs)}">{cards_html}</ul></section>')

    # Data-backed destinations used to fill the discovery rail when fewer than four editorial cards are approved. They use only listing facts (movement, display),
    # never editorial fields such as features or styles; the text is a plain count. Without scripts a card link only scrolls to the list; scripts apply the filter.
    FACT_CARDS = [("movement", "automatic", "Automatic watches", "Mechanical movement with a more traditional feel."), ("display", "digital", "Digital watches", "{n} {w} with a digital display."),
                  ("movement", "quartz", "Quartz watches", "{n} {w} with a quartz movement.")]

    def intent_cards(self, fill=True):
        """The 'What are you looking for?' rail: up to four cards. Approved editorial cards come first (each needs an approved flag and a filter that matches a watch);
        then data-backed cards (for example Automatic watches) top the rail up to four. With fewer than two cards the section is not shown. One card = one link."""
        cards, seen = [], set()
        def add(title, text, flt, href):
            matches = self.filter_count(flt)
            if not matches or len(cards) >= 4:
                return
            key = (flt["group"], flt["value"])
            if key in seen:
                return
            seen.add(key)
            n = len(cards)
            cards.append(f'<li>{ui.intent_card(title, text, href, flt["group"] + ":" + flt["value"], self.WATCH_GLYPH)}</li>')
        for card in self.settings.get("intent_cards", []):
            flt = card.get("filter")
            if card.get("approved") and flt:
                href = f'/watches/style/{flt["value"]}/' if flt["group"] == "style" else "#watch-collection"
                add(card["title"], card["text"], flt, href)
        if fill:
            for group, value, title, text in self.FACT_CARDS:
                flt = {"group": group, "value": value}
                n = len(self.filter_count(flt))
                if n:
                    add(title, text.format(n=n, w="watch" if n == 1 else "watches"), flt, "#watch-collection")
        if len(cards) < 2:
            return ""
        return ('<section class="lx-sec lx-intents" aria-labelledby="lx-intents"><div class="lx-sec-head"><h2 id="lx-intents">What are you looking for?</h2></div>'
                f'<ul class="lx-intent-row" data-count="{len(cards)}">{"".join(cards)}</ul></section>')

    @staticmethod
    def budget_tier(max_value):
        """1 (lightest) to 7 (charcoal and gold): the colour progression of a budget card as the price band rises."""
        for tier, limit in enumerate((1000, 2000, 3000, 6000, 15000, 20000), start=1):
            if max_value <= limit:
                return tier
        return 7

    def budget_cards(self, tiers, aff=None):
        """Shop by budget: one card per shopper price tier (see budget_discovery), each with live count and brands, a watch from the tier and a colour that deepens
        with the price. A tier with no watch is not shown, and a tier never links to a page that is not published: it links to the hub filter instead."""
        tiers = [t for t in tiers if t["count"]]
        if not tiers:
            return ""
        items = []
        for t in tiers:
            if t["kind"] == "premium":
                mine = [p for p in self.products if p.get("budget") in self.premium_bands()]
            else:
                mine = [p for p in self.products if p.get("budget") == t["price_band"]] or [p for p in self.products if t["price_band"] in self.qualifies(p)]
            art = self.art_copy(mine[0], "b" + str(len(items))) if mine else ""
            items.append(f'<li>{ui.budget_card(t, art, self.tier_affiliate(t, aff))}</li>')
        return ('<section class="lx-sec lx-budgets" aria-labelledby="lx-budgets"><div class="lx-sec-head"><h2 id="lx-budgets">Shop by budget</h2></div>'
                f'<ul class="lx-budget-row" data-count="{len(items)}">{"".join(items)}</ul></section>')

    def brand_tiles(self, active):
        if len(active) < 2:
            return ""
        tiles = "".join(f'<li>{ui.brand_card(s, name, cnt)}</li>' for s, name, cnt in active)
        return ('<section class="lx-sec lx-brands" aria-labelledby="lx-brands"><div class="lx-sec-head"><h2 id="lx-brands">Shop by brand</h2></div>'
                f'<ul class="lx-brand-row">{tiles}</ul></section>')

    def catalog(self, url, title, intro, *, gender="", brand="", budget="", style="", premium=False, crumbs=None, extra_html="", table=False, hub=None):
        products = self.products
        def matches(p):
            return ((not gender or gender in p["gender"]) and (not brand or p["brand"] == brand)
                    and (not budget or budget in self.qualifies(p)) and (not style or style in p["styles"])
                    and (not premium or p.get("budget") in self.premium_bands()))
        shown = [p for p in products if matches(p)]
        def n(pred):
            return sum(1 for p in products if pred(p))
        planned = self.settings.get("planned_filters", {})
        active = self.active_brands()
        groups = [
            {"key": "brand", "title": "Brand", "checked": [brand] if brand else [], "items": [(slug_, name, cnt) for slug_, name, cnt in active]},
            {"key": "budget", "title": "Price", "checked": [budget] if budget else [self.premium_top()] if premium else [],
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
        groups.append({"key": "gender", "title": "Gender", "checked": [gender] if gender else [],
                       "items": [(g, info["label"], n(lambda p, g=g: g in p["gender"])) for g, info in self.genders.items()]})
        groups.append({"key": "style", "title": "Style", "checked": [style] if style else [],
                       "items": [(slug_, value["label"], n(lambda p, s=slug_: s in p["styles"])) for slug_, value in self.styles.items()]})
        priority = ["brand", "budget", "gender", "dial", "strapmat", "dialcolour", "movement", "water", "style", "occasion"]
        groups.sort(key=lambda g: priority.index(g["key"]) if g["key"] in priority else len(priority))
        steps = self.price_steps()
        budget_rail = collection.price_slider(steps, title="Budget")
        quick = self.keyword_chips(url, shown)
        curated = self.popular_collections(self.menu_discovery()) if hub else ""
        quick_row = f'<div class="lx-quick" data-quick-controls hidden>{quick}</div>' if quick else ""
        headline, sub = (("Timeless Watches. Smart Choices.", "Discover classic and analog watches by budget, brand, style and fit.") if hub else (title, intro))
        reviewed = (f'<span class="lx-reviewed">Last reviewed: <time datetime="{esc(self.updated(shown))}">{esc(self.human_date(self.updated(shown)))}</time></span>' if shown else "")
        gcount = {g: n(lambda p, g=g: g in p["gender"]) for g in self.genders}
        art_for = (shown or products)[0]
        aff = self.hub_affiliate() if hub else None
        hero = ('<header class="lx-hero">' + (ui.hero_link(aff) if aff else "") + '<div class="lx-hero-text"><p class="lx-kicker">The SAT watch edit</p>'
                f'<h1 data-default="{esc(headline)}"{" data-static" if hub else ""}>{esc(headline)}</h1><p class="lx-sub">{esc(sub)}</p><!--segments--></div>'
                f'<div class="lx-hero-art" aria-hidden="true"><div class="lx-hero-watch">{self.art_copy(art_for, "h")}</div>'
                f'<dl class="lx-stats"><div><dt>{gcount["men"]}</dt><dd>Men\'s watches</dd></div><div><dt>{gcount["women"]}</dt><dd>Women\'s watches</dd></div></dl></div></header>')
        footline = f'<p class="lx-foot">{reviewed}</p>' if reviewed else ""
        top = (hero + self.quick_row(steps, active, any(self.styles)) + quick_row + (self.intent_cards() + self.budget_cards(self.budget_discovery(), aff) + self.brand_tiles(active) if hub else ""))
        hub_top, hub_bottom = hub or ("", "")
        note = ('<p class="watch-affiliate-note">Amazon links on this page are affiliate links. As an Amazon Associate I earn from qualifying purchases. '
                '<a href="/affiliate-disclosure/">How we earn</a></p>') if any(self.merchant_links(p) for p in shown) else ""
        card_html = [self.card(p) for p in products]
        sizes = {}
        for p in products:
            mm = p.get("case_diameter_mm")
            if mm:
                sizes[round(mm)] = sizes.get(round(mm), 0) + 1
        common = sorted(sorted(sizes, key=lambda k: -sizes[k])[:4])
        sizes_json = json.dumps([[mm, self.bucket(self.DIAL_SIZES, mm)] for mm in common])
        block = collection.render_store(card_html, groups, uid="watch-collection", title="Selected for you", noun="watch", plural="watches",
                                        preset_gender=gender, genders=[(g, g.title(), gcount[g]) for g in self.genders],
                                        top_html=top, visible=[matches(p) for p in products], page_size=24, grid_note=note,
                                        panel_top=budget_rail + curated, panel_title="Refine your watches", sizes_json=sizes_json,
                                        preset_from=self.discovery_config()["premium_after"] if premium else "", premium_json=self.premium_ui())
        body = ('<section class="section watch-store" data-mobile-grid="two"><div class="container watch-store-inner">{{breadcrumb}}' + hub_top + block + hub_bottom + footline + self.collection_tables(table, shown) + self.collection_copy(url) + self.related_collections(url) + extra_html + '<noscript><nav class="watch-static-links" aria-label="Browse watches"><a href="/watches/men/">Men</a> · <a href="/watches/women/">Women</a> · ' + ' · '.join(f'<a href="/watches/brands/{esc(slug_)}/">{esc(name)}</a>' for slug_, name, _ in active) + '</nav></noscript></div></section>')
        meta = self._meta(url, title, intro, body, crumbs or [["Watches", "/watches/"]], shown, js=False)
        meta["noindex"] = self.collection_noindex(url, shown)
        custom = str((self.approved.get(url) or {}).get("meta_description") or "").strip()
        if custom:   # an approved meta_description in collections.json always wins
            meta["description"] = custom
        meta["css"] += ["collection", "watch-store", "price-slider", "watch-luxe"]
        meta["js"] = ["collection", "watch-tilt"]
        return meta

    def premium_top(self):
        """The highest band that holds a live watch: the Premium page and filter link choose it, with a lower limit at the end of the last tier."""
        own = [p["budget"] for p in self.products if p.get("budget") in self.premium_bands()]
        return max(own, key=list(self.budgets).index) if own else ""

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
        if self.premium_bands():
            dims.append(("premium", "premium", f"Premium {self.premium_label()}", lambda p: p.get("budget") in self.premium_bands()))
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
                if b is not None and "premium" in (a[0], b[0]):
                    continue   # Premium is a broad tier on its own, not combined with other filters
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
            return {"gender": f"/watches/{v}/", "brand": f"/watches/brands/{v}/", "style": f"/watches/style/{v}/", "budget": f"/watches/{v}/", "premium": "/watches/premium/"}.get(k)
        if set(pair) == {"gender", "budget"}:
            return f'/watches/{pair["gender"]}/{pair["budget"]}/'
        if set(pair) == {"brand", "budget"}:
            return f'/watches/{pair["brand"]}/{pair["budget"]}/'
        return None

    def budget_page(self, gender, budget):
        g, b = self.genders[gender], self.budgets[budget]
        url = f"/watches/{gender}/{budget}/"
        title = self.page_title(url, gender=gender, band=budget)
        return self.catalog(url, title, "Compare styles and published details. Confirm the current price with the retailer.", gender=gender, budget=budget,
                            crumbs=[["Watches", "/watches/"], [g["label"], f"/watches/{gender}/"], [b["label"], url]])

    def all_brands_budget_page(self, budget):
        url = f"/watches/{budget}/"
        b = self.budgets[budget]
        t = next((x for x in self.budget_discovery() if x["id"] == budget), None)
        return self.catalog(url, self.page_title(url, band=budget), self.tier_meta(t) if t else "Compare watches from every brand in this price range by case size, strap, movement and water resistance.", budget=budget,
                            crumbs=[["Watches", "/watches/"], [b["label"], url]])

    def premium_page(self):
        url = "/watches/premium/"
        t = next((x for x in self.budget_discovery() if x["id"] == "premium"), None)
        return self.catalog(url, self.page_title(url, premium=True), self.tier_meta(t) if t else "Compare the higher-budget watches in the catalogue by case size, strap, movement and water resistance.", premium=True,
                            crumbs=[["Watches", "/watches/"], ["Premium", url]])

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
        title = self.page_title(url, brand=brand, band=budget)
        intro = f'{br["name"]} watches {bd["label"].lower()}, for men and women. Compare the published details and confirm the current price at the retailer.'
        sections = [(f'{title} for {info["adjective"].title()}', [p for p in shown if g in p["gender"]])
                    for g, info in self.genders.items()]
        return self.catalog(url, title, intro, brand=brand, budget=budget, table=[(h, ps) for h, ps in sections if ps],
                            crumbs=[["Watches", "/watches/"], [br["name"], f"/watches/brands/{brand}/"], [bd["label"], url]])

    def brand_page(self, slug):
        br = self.brands[slug]
        url = f"/watches/brands/{slug}/"
        pub_urls = {c["url"] for c in self.published_collections()}
        pair_links = "".join(f'<li><a href="/watches/{slug}/{b}/">{esc(self.collection_name(brand=slug, band=b, best=f"/watches/{slug}/{b}/" in pub_urls))}</a></li>' for br_, b in self.brand_budget_pairs() if br_ == slug)
        extra = f'<nav class="watch-static-links" aria-label="{esc(br["name"])} by price"><h2>{esc(br["name"])} by price</h2><ul class="related-links">{pair_links}</ul></nav>' if pair_links else ""
        meta = self.catalog(url, self.page_title(url, brand=slug), "Explore the collection by style and budget. Read the details before you choose.", brand=slug,
                            crumbs=[["Watches", "/watches/"], [br["name"], url]], extra_html=extra)
        # Keep old product and gender anchors reachable after introducing dedicated detail pages.
        anchors = ''.join(f'<span id="r-{esc(p["id"])}"></span>' for p in self.products if p["brand"] == slug)
        anchors += '<span id="men"></span><span id="women"></span>'
        meta["_body"] = meta["_body"].replace('<header class="watch-store-head">', anchors + '<header class="watch-store-head">', 1)
        return meta

    def style_page(self, slug):
        st = self.styles[slug]
        url = f"/watches/style/{slug}/"
        return self.catalog(url, self.page_title(url, style=slug), "Find a style for your everyday, workdays and special occasions.", style=slug,
                            crumbs=[["Watches", "/watches/"], [st["label"], url]])

    def gender_page(self, gender):
        g = self.genders[gender]
        url = f"/watches/{gender}/"
        return self.catalog(url, self.page_title(url, gender=gender), "Explore watches by style, brand and budget. Choose what suits you.", gender=gender,
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
        for url in self.approved:   # a price page for every brand exists only once the owner approves it with its own copy
            key = self.parse_collection_url(url) or {}
            if key.get("premium"):
                out.append(self.premium_page())
            elif set(key) == {"price_band"}:
                out.append(self.all_brands_budget_page(key["price_band"]))
        prev = self.preview()
        if prev:
            out.append(prev)
        return out
