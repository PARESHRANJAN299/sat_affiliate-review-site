"""Product listings: validation of product files, filter lists, and the HTML for the filterable product grid.

build.py hands this module the few helpers it needs (see `Kit`), so there is no circular import.
Standard library only.
"""
import datetime
import difflib
import html
import json
import os
import re
import unicodedata
import urllib.parse
from pathlib import Path

TARGET_PER_TYPE = 15          # the owner's working target: at least 15 chosen products per product type
PAGE_SIZE = 12                # cards shown first; "Show 12 more" adds the next batch
STALE_DAYS = 90

TYPED_PRICE = re.compile(r"((\u20b9|\brs\.?|\binr\b|\brupees?\b|\bmrp\b)[\s:.\-]*\d[\d,]*|\d[\d,]*\s*(/-|\brs\b|\brupees?\b|\binr\b))", re.I)
NUMBER_WORDS = r"(one|two|three|four|five|1|2|3|4|5)"
RATING_WORDS = re.compile(
    r"(\d(\.\d)?\s*(/|out of)\s*(5|10)\b|\d(\.\d)?\s*[- ]?stars?\b|\b" + NUMBER_WORDS + r"[- ]?stars?\b|[\u2605\u2606\u2b50]"
    r"|\bstar[- ]?rating\b|\brating\s*:?\s*\d|\brated\s+\d|\btop[- ]rated\b|\bhighly[- ]rated\b|\b\d+(\.\d)?\s*/\s*5\b)", re.I)
TESTED_CLAIM = re.compile(
    r"(personally tested|hands[- ]on|lab[- ]tested|tested by (us|our|me)|\b(we|i|our team)\s+(have\s+|had\s+)?(tested|tried|used|reviewed in person)\s+(it|this|them|these)?\b"
    r"|\bafter (weeks|months|days) of (use|testing)\b|\bour (own )?(testing|test results)\b)", re.I)
PRICE_CLAIM = re.compile(r"\b(lowest price|cheapest price|best price|price drop|deal of the day|price guarantee|lowest ever)\b", re.I)
ID_OK = re.compile(r"^[a-z0-9][a-z0-9-]*$")
KNOWN_KEYS = {"id", "family", "name", "brand", "audience", "price_band", "best_for", "pros", "cons", "facets", "features", "key_ingredients",
              "value_for_money", "who_should_buy", "avoid", "how_to_choose", "alternatives", "final_recommendation", "editor_pick", "rank",
              "checked", "image", "retailers", "sources", "slot", "sample", "product_type", "category", "suits", "best_use_case", "maintenance",
              "care", "material", "fit", "size_range", "style", "occasion", "size", "draft", "notes"}
RETAILER_HOSTS = {"amazon": ("amazon.in", "amzn.to", "amzn.in", "a.co"), "flipkart": ("flipkart.com", "fkrt.it", "fkrt.cc")}
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")


def clean_text(value):
    """Normalise text before the honesty patterns run, so odd spacing or look-alike characters cannot hide a claim."""
    value = unicodedata.normalize("NFKC", str(value))
    value = re.sub(r"[\u200b-\u200f\u2060\ufeff\u00ad]", "", value)
    return re.sub(r"\s+", " ", value)


def esc(value):
    return html.escape(str(value), quote=True)


def slug(text):
    text = str(text).lower().replace("–", "-").replace("₹", "").replace(",", "")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


class Kit:
    """Everything this module borrows from build.py."""

    def __init__(self, src, config, categories, default_bands, retailer_order, retailer_label, slot_keys,
                 price_note, category_icon, errors, warnings):
        self.src = Path(src)
        self.config = config
        self.categories = categories
        self.default_bands = default_bands
        self.retailer_order = retailer_order
        self.retailer_label = retailer_label
        self.slot_keys = slot_keys
        self.price_note = price_note
        self.category_icon = category_icon
        self.errors = errors
        self.warnings = warnings
        try:
            raw = json.loads((self.src / "facets.json").read_text(encoding="utf-8"))
        except ValueError as exc:
            raise SystemExit(f"src/facets.json is not valid JSON: {exc}")
        self.facets = raw.get("categories", {})
        self._check_facets()

    def _check_facets(self):
        reserved = {"price", "brand", "type", "aud", "for", "sort"}
        for cat, cfg in self.facets.items():
            seen_keys = set()
            for f in cfg.get("facets", []):
                key = f.get("key", "")
                if not re.fullmatch(r"[a-z0-9_]+", key) or key in reserved or key in seen_keys:
                    self.errors.append(f'src/facets.json: {cat}: facet key "{key}" must be lowercase letters, numbers or _, unique, and not one of {sorted(reserved)}')
                seen_keys.add(key)
                codes = set()
                for v in f.get("values", []):
                    if not (isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) and x for x in v)) or not re.fullmatch(r"[a-z0-9-]+", v[0]) or v[0] in codes:
                        self.errors.append(f'src/facets.json: {cat}/{key}: each value must be ["code", "Label"] with a unique code of lowercase letters, numbers and -; found {v!r}')
                    else:
                        codes.add(v[0])

    # ---------- lists ----------

    def bands(self, cat):
        labels = cat.get("price_bands") or self.default_bands
        return [(slug(b), b) for b in labels]

    def cfg(self, cat):
        return self.facets.get(cat["slug"], {})

    def segment(self, cat):
        return self.cfg(cat).get("segment")

    def facet_list(self, cat):
        return self.cfg(cat).get("facets", [])

    # ---------- validation ----------

    def validate(self, cat, p, fam_slugs, fname):
        """Return a list of error strings for one product file (empty means fine). Warnings go to self.warnings."""
        errs = []
        pid = p.get("id", fname)
        where = f"product {cat['slug']}/{fname}"

        def bad(msg):
            errs.append(f"{where}: {msg}")

        if not isinstance(p, dict):
            return [f"{where}: the file must contain one JSON object like the template"]
        for key in ("id", "name", "family", "brand", "price_band"):
            if not p.get(key):
                bad(f'missing "{key}"')
        if errs:
            return errs
        # types first, so later checks cannot crash on a wrong kind of value
        for key in ("id", "name", "family", "brand", "price_band", "best_for", "checked", "image", "slot"):
            if key in p and p[key] is not None and not isinstance(p[key], str):
                bad(f'"{key}" must be text, found {type(p[key]).__name__}')
        for key in ("pros", "cons", "features", "key_ingredients", "alternatives", "audience"):
            if key in p and not (isinstance(p[key], list) and all(isinstance(x, str) for x in p[key])):
                bad(f'"{key}" must be a list of text items, for example ["one", "two"]')
        for key in ("facets", "retailers"):
            if key in p and not isinstance(p[key], dict):
                bad(f'"{key}" must be an object ({{...}})')
        if "sources" in p and not (isinstance(p["sources"], list) and all(isinstance(x, dict) and isinstance(x.get("label"), str) and isinstance(x.get("url"), str) for x in p["sources"])):
            bad('"sources" must be a list like [{"label": "Maker page", "url": "https://..."}]')
        if "editor_pick" in p and not isinstance(p["editor_pick"], bool):
            bad('"editor_pick" must be true or false')
        if "rank" in p and p["rank"] is not None and not isinstance(p["rank"], int):
            bad('"rank" must be a whole number or null')
        if errs:
            return errs
        if not ID_OK.match(p["id"]):
            bad(f'id "{p["id"]}" must use lowercase letters, numbers and - only')
        elif p["id"] != Path(fname).stem:
            bad(f'id "{p["id"]}" must be the same as the file name ("{Path(fname).stem}")')
        if not slug(p["brand"]):
            bad(f'brand "{p["brand"]}" needs at least one letter or number in English letters (keep the display name simple)')
        unknown = [k for k in p if k not in KNOWN_KEYS]
        for k in unknown:
            near = difflib.get_close_matches(k, sorted(KNOWN_KEYS), n=1, cutoff=0.6)
            self.warnings.append(f'{where}: unknown field "{k}"' + (f' (did you mean "{near[0]}"?)' if near else " and it is not used"))
        if p["id"] in ("brand-short-model-name",) or p["name"].startswith("Product name as the brand writes it"):
            bad("this is still the template text. Fill in the real product details")
        if errs:
            return errs
        if p["family"] not in fam_slugs:
            norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
            by_norm = {norm(f): f for f in fam_slugs}
            near = [by_norm[m] for m in difflib.get_close_matches(norm(p["family"]), list(by_norm), n=3, cutoff=0.5)] or fam_slugs[:3]
            bad(f'family "{p["family"]}" not found. Did you mean one of: {", ".join(near)}?')
        codes = {label: code for code, label in self.bands(cat)}
        if p["price_band"] not in codes:
            bad(f'price_band "{p["price_band"]}" is not one of: {" | ".join(codes)}')
        if p.get("slot") and p["slot"] not in self.slot_keys.values():
            bad(f'slot "{p["slot"]}" is not one of: {", ".join(sorted(set(self.slot_keys.values())))}')
        # honesty rules: scan every text value (price_band itself is the one allowed place for rupee amounts)
        for key, value in self._strings(p):
            if key in ("price_band", "image", "retailers", "sources", "url"):
                continue
            value = clean_text(value)
            if TYPED_PRICE.search(value):
                bad(f'"{key}" contains a typed price ("{TYPED_PRICE.search(value).group(0)}"). Use the price_band only')
            if RATING_WORDS.search(value):
                bad(f'"{key}" contains a rating ("{RATING_WORDS.search(value).group(0)}"). SAT shows no ratings')
            if TESTED_CLAIM.search(value):
                bad(f'"{key}" claims testing ("{TESTED_CLAIM.search(value).group(0)}"). Only say this when it is true and the page says so')
            if PRICE_CLAIM.search(value):
                bad(f'"{key}" makes a price claim ("{PRICE_CLAIM.search(value).group(0)}")')
        for r, info in (p.get("retailers") or {}).items():
            if r not in self.retailer_order:
                bad(f'retailer "{r}" is not one of: {", ".join(self.retailer_order)}')
                continue
            url = (info or {}).get("url", "") if isinstance(info, dict) else None
            if url is None:
                bad(f'retailer "{r}" must look like {{"url": "https://..."}}')
            elif url:
                self._check_url(bad, f'retailer "{r}"', url, RETAILER_HOSTS.get(r))
        for srcs in p.get("sources") or []:
            self._check_url(bad, f'source "{srcs.get("label", "")}"', srcs.get("url", ""), None)
        # filter values
        seg = self.segment(cat)
        aud = p.get("audience") or []
        if aud and not seg:
            bad('"audience" is not used in this category')
        elif seg:
            allowed = {c for c, _ in seg["values"]}
            for a in aud:
                if a not in allowed:
                    bad(f'audience "{a}" is not one of: {", ".join(sorted(allowed))}')
            if not aud:
                bad(f'missing "audience" (one or more of: {", ".join(sorted(allowed))})')
            # a product must be for an audience that its product type is listed under (men's shirts are not for women)
            fam = next((f for f in cat.get("families", []) if f["slug"] == p["family"]), None)
            tabs = {t["slug"]: t["sections"] for t in cat.get("audience_tabs", [])}
            if fam and tabs:
                ok_aud = [a for a, secs in tabs.items() if fam.get("section") in secs]
                for a in aud:
                    if a in tabs and a not in ok_aud:
                        bad(f'audience "{a}" does not match product type "{p["family"]}" (it is listed under: {", ".join(ok_aud)})')
        allowed_facets = {f["key"]: {c for c, _ in f["values"]} for f in self.facet_list(cat)}
        for key, values in (p.get("facets") or {}).items():
            if key not in allowed_facets:
                bad(f'facet "{key}" is not defined for this category. Known: {", ".join(allowed_facets) or "none"}')
                continue
            if not isinstance(values, list):
                bad(f'facet "{key}" must be a list, for example ["{sorted(allowed_facets[key])[0]}"]')
                continue
            for v in values:
                if v not in allowed_facets[key]:
                    bad(f'facet "{key}" has unknown value "{v}". Allowed: {", ".join(sorted(allowed_facets[key]))}. '
                        f'To add a new value, add one line to src/facets.json')
        # image
        img = p.get("image")
        if img:
            folder = self.src / "static" / "images" / "products"
            name = img[len("/images/products/"):]
            if not img.startswith("/images/products/") or "/" in name or "\\" in name or ".." in name:
                bad('image must be a file directly under /images/products/ (your own photo or one you have the right to use)')
            elif not name.lower().endswith(IMAGE_EXT):
                bad(f'image must end with {", ".join(IMAGE_EXT)}')
            elif not folder.is_dir() or name not in os.listdir(folder):
                bad(f'image file not found (names are case-sensitive on the live server): src/static{img}')
        # dates and soft warnings
        checked = p.get("checked")
        if checked:
            try:
                age = (datetime.date.today() - datetime.date.fromisoformat(checked)).days
                if age < 0:
                    bad(f'"checked" is in the future ({checked})')
                elif age > STALE_DAYS:
                    self.warnings.append(f"{where}: last checked {age} days ago ({checked}). Please re-check the listing")
            except ValueError:
                bad('"checked" must look like 2026-10-16')
        elif not p.get("sample"):
            self.warnings.append(f'{where}: add "checked": "YYYY-MM-DD" (the day you last checked the shop listing)')
        if not p.get("sample") and not p.get("sources"):
            self.warnings.append(f'{where}: no "sources" (pages you read). They appear under "Pages we read"')
        del pid
        return errs

    def _check_url(self, bad, label, url, hosts):
        if not isinstance(url, str) or not url.startswith("https://"):
            bad(f"{label} link must start with https://")
            return
        parts = urllib.parse.urlparse(url)
        host = (parts.hostname or "").lower()
        if not host or "." not in host or "..." in url or host.endswith("example.com") or host == "example.org":
            bad(f"{label} link looks like placeholder text: {url}")
        elif hosts and not any(host == h or host.endswith("." + h) for h in hosts):
            bad(f"{label} link should be on {' or '.join(hosts)}, found {host}")

    def _strings(self, obj, prefix=""):
        if isinstance(obj, str):
            yield prefix, obj
        elif isinstance(obj, dict):
            for k, v in obj.items():
                yield from self._strings(v, k if not prefix else prefix)
        elif isinstance(obj, list):
            for v in obj:
                yield from self._strings(v, prefix)

    # ---------- cards ----------

    def _buttons(self, p):
        """Compact retailer buttons (same link rules as the review block: plain links until affiliate_active)."""
        active = bool(self.config.get("affiliate_active"))
        rel = "sponsored nofollow noopener" if active else "nofollow noopener"
        retailers = p.get("retailers") or {}
        out = []
        short = {"amazon": "View on Amazon", "flipkart": "View on Flipkart", "brand_store": "Brand website", "other": "View on shop"}
        for key in self.retailer_order:
            url = (retailers.get(key) or {}).get("url", "")
            if not url:
                continue
            cls = "btn-primary" if not out else "btn-outline"
            out.append(f'<a class="btn {cls} btn-small pl-buy" href="{esc(url)}" target="_blank" rel="{rel}" '
                       f'aria-label="{esc(short[key])}: {esc(p["name"])} (opens in a new tab)">{esc(short[key])}</a>')
        if not out:
            if p.get("sample"):
                return '<span class="btn btn-primary btn-small pl-buy is-disabled" aria-disabled="true">View on Amazon</span>'
            return '<span class="pl-soon-link">Retailer link coming soon</span>'
        return "".join(out[:3])

    def _media(self, cat, p):
        if p.get("image"):
            return (f'<img src="{esc(p["image"])}" alt="{esc(p.get("brand", ""))} {esc(p["name"])}" '
                    'loading="lazy" decoding="async" width="360" height="360">')
        return (f'<span class="pl-ph" aria-hidden="true">{self.category_icon(cat, "pl-ph-ic")}'
                f'<span class="pl-ph-t">{"Sample" if p.get("sample") else "Photo coming"}</span></span>')

    def card(self, cat, p, index, fam_names, seg_mode):
        bands = {label: i for i, (_, label) in enumerate(self.bands(cat))}
        attrs = {
            "data-id": p["id"],
            "data-price": slug(p["price_band"]),
            "data-pord": str(bands.get(p["price_band"], 99)),
            "data-brand": slug(p["brand"]),
            "data-type": p["family"],
            "data-aud": " ".join(p.get("audience") or []),
            "data-pick": "1" if p.get("editor_pick") else "0",
            "data-rank": str(p.get("rank") if isinstance(p.get("rank"), int) else 999),
            "data-i": str(index),
        }
        for key, values in (p.get("facets") or {}).items():
            attrs[f"data-f-{key}"] = " ".join(values)
        attr_html = " ".join(f'{k}="{esc(v)}"' for k, v in attrs.items())
        pros = "".join(f"<li>{esc(x)}</li>" for x in (p.get("pros") or [])[:2])
        best = f'<p class="pl-best">{esc(p["best_for"])}</p>' if p.get("best_for") else ""
        badge = ""
        if p.get("sample"):
            badge = '<span class="pl-badge pl-badge-sample">Sample</span>'
        elif p.get("editor_pick"):
            badge = '<span class="pl-badge">Our pick</span>'
        checked = ""
        if p.get("checked"):
            try:
                d = datetime.date.fromisoformat(p["checked"])
                checked = f'<span class="pl-checked">Checked {d.day} {d.strftime("%b %Y")}</span>'
            except ValueError:
                pass
        type_name = fam_names.get(p["family"], "")
        seg = self.segment(cat)
        aud_label = ""
        if seg_mode and seg and p.get("audience"):
            names = dict(seg["values"])
            aud_label = '<span class="pl-aud">' + esc(" / ".join(names.get(a, a) for a in p["audience"])) + " · </span>"
        return (
            f'<li class="pl-item"><article class="pl-card" {attr_html}>\n'
            f'  <a class="pl-media" href="#r-{esc(p["id"])}" data-details tabindex="-1" aria-hidden="true">{self._media(cat, p)}{badge}</a>\n'
            '  <div class="pl-body">\n'
            f'    <p class="pl-brand">{aud_label}{esc(p["brand"])}{(" · " + esc(type_name)) if type_name else ""}</p>\n'
            f'    <h3 class="pl-name"><a href="#r-{esc(p["id"])}" data-details>{esc(p["name"])}</a></h3>\n'
            f'    {best}\n'
            f'    <ul class="pl-pros">{pros}</ul>\n'
            f'    <p class="pl-band"><span class="pl-band-v">{esc(p["price_band"])}</span>{checked}</p>\n'
            f'    <div class="pl-actions">{self._buttons(p)}'
            f'<a class="btn btn-outline btn-small pl-more-info" href="#r-{esc(p["id"])}" data-details>Details</a></div>\n'
            '  </div>\n</article></li>')

    # ---------- the listing ----------

    def note(self, products):
        if self.config.get("affiliate_active"):
            text = "Affiliate links. We may earn a commission if you buy, at no extra cost to you."
            has_amazon = any(((p.get("retailers") or {}).get("amazon") or {}).get("url") for p in products)
            if self.config.get("amazon_associate_approved") and has_amazon:
                text += " As an Amazon Associate I earn from qualifying purchases."
            return text + " Prices change; check the shop for the current price."
        return self.price_note

    def listing(self, cat, products, uid, families, *, segment_tabs=False, type_chips=None, soon_text=""):
        """HTML for a filterable product listing.

        products: validated products. families: list of family dicts (for names).
        segment_tabs: show the audience as tabs (Women / Girls / Men). type_chips: {segment: [(name, url), ...]}.
        """
        fam_names = {f["slug"]: f["name"] for f in families}
        seg = self.segment(cat)
        seg_values = seg["values"] if seg else []
        cards = [self.card(cat, p, i, fam_names, segment_tabs) for i, p in enumerate(products)]
        if not products:
            return self._empty(cat, uid, seg_values if segment_tabs else [], type_chips, soon_text)

        def options(key, label, entries, counts):
            if len(entries) < 2:
                return ""
            rows = "".join(
                f'<label class="pl-opt"><input type="checkbox" name="{esc(key)}" value="{esc(code)}">'
                f'<span class="pl-opt-t">{esc(name)}</span><em class="pl-n">{counts.get(code, 0)}</em></label>'
                for code, name in entries)
            return (f'<details class="pl-group" data-key="{esc(key)}" open><summary>{esc(label)}</summary>'
                    f'<div class="pl-opts">{rows}</div></details>')

        def present(values_of, order):
            seen, counts = [], {}
            for p in products:
                for v in values_of(p):
                    counts[v] = counts.get(v, 0) + 1
                    if v not in seen:
                        seen.append(v)
            return [(c, n) for c, n in order if c in seen], counts

        groups = []
        band_entries, c = present(lambda p: [slug(p["price_band"])], self.bands(cat))
        groups.append(options("price", "Price", band_entries, c))
        brand_order = sorted({(slug(p["brand"]), p["brand"]) for p in products}, key=lambda t: t[1].lower())
        brand_entries, c = present(lambda p: [slug(p["brand"])], brand_order)
        groups.append(options("brand", "Brand", brand_entries, c))
        type_order = [(f["slug"], f["name"]) for f in families]
        type_entries, c = present(lambda p: [p["family"]], type_order)
        groups.append(options("type", "Product type", type_entries, c))
        if seg and not segment_tabs:
            aud_entries, c = present(lambda p: p.get("audience") or [], [tuple(v) for v in seg_values])
            groups.append(options("aud", seg["label"], aud_entries, c))
        for f in self.facet_list(cat):
            entries, c = present(lambda p, k=f["key"]: (p.get("facets") or {}).get(k, []), [tuple(v) for v in f["values"]])
            groups.append(options(f["key"], f["label"], entries, c))
        groups_html = "".join(g for g in groups if g)

        tabs = ""
        types = ""
        if segment_tabs and seg_values:
            tab_btns = "".join(
                f'<button type="button" role="tab" class="pl-tab" id="{uid}-tab-{esc(code)}" data-seg="{esc(code)}" aria-selected="false" tabindex="-1">'
                f'{esc(name)}<span class="pl-tab-n">{sum(1 for p in products if code in (p.get("audience") or []))}</span></button>'
                for code, name in seg_values)
            tabs = f'<div class="pl-tabs" role="tablist" aria-label="{esc(seg["label"])}" hidden>{tab_btns}</div>\n'
        if type_chips:
            types = self._type_chips(type_chips, seg_values)

        sort = ('<label class="pl-sort"><span class="visually-hidden">Sort by</span><select data-sort aria-label="Sort by">'
                '<option value="pick">Our picks first</option><option value="price-asc">Price: low to high</option>'
                '<option value="price-desc">Price: high to low</option></select></label>')
        return (
            f'<section class="pl" id="{uid}" data-pl data-limit="{PAGE_SIZE}" data-segments="{1 if segment_tabs else 0}" aria-label="Products">\n'
            f'{tabs}{types}'
            '<div class="pl-bar" hidden>\n'
            '  <button type="button" class="btn btn-outline btn-small pl-open" data-panel-open aria-haspopup="dialog">Filters <span class="pl-badge-n" data-filter-n></span></button>\n'
            f'  {sort}\n  <p class="pl-count" role="status" aria-live="polite" data-count></p>\n</div>\n'
            '<div class="pl-chips" data-chips hidden></div>\n'
            '<div class="pl-layout">\n'
            '  <aside class="pl-panel" data-panel aria-label="Filters" hidden>\n'
            '    <div class="pl-panel-head"><h2>Filters</h2><button type="button" class="pl-panel-close" data-panel-close>Close</button></div>\n'
            f'    <div class="pl-groups">{groups_html}</div>\n'
            '    <div class="pl-panel-foot"><button type="button" class="btn btn-outline" data-clear>Clear all</button>'
            '<button type="button" class="btn btn-primary" data-panel-close data-show-n>Show products</button></div>\n'
            '  </aside>\n'
            '  <div class="pl-main">\n'
            f'    <ul class="pl-grid" data-grid>\n{chr(10).join(cards)}\n    </ul>\n'
            '    <p class="pl-empty" data-empty hidden>No products match these filters. <button type="button" class="linklike" data-clear>Clear filters</button></p>\n'
            f'    <button type="button" class="btn btn-outline pl-show-more" data-more hidden>Show {PAGE_SIZE} more</button>\n'
            '  </div>\n</div>\n'
            + (f'<p class="pl-note">{esc(self.note(products))}</p>\n' if self.config.get("affiliate_active") else "")
            + '</section>')

    def _type_chips(self, type_chips, seg_values):
        names = dict(seg_values) if seg_values else {}
        groups = []  # [(codes, items)]: tabs with the same product types share one row
        for code, items in type_chips.items():
            for g in groups:
                if g[1] == items:
                    g[0].append(code)
                    break
            else:
                groups.append([[code], items])
        blocks = []
        for codes, items in groups:
            lis = "".join(f'<li><a class="pl-type" href="{esc(url)}">{esc(name)}</a></li>' for name, url in items)
            label = f'<p class="pl-types-label">{esc(" / ".join(names.get(c, c) for c in codes))}</p>' if names else ""
            blocks.append(f'<div class="pl-types" data-types="{esc(" ".join(codes))}">{label}<ul>{lis}</ul></div>')
        return "".join(blocks)

    def _empty(self, cat, uid, seg_values, type_chips, soon_text):
        tabs = ""
        if seg_values:
            tab_btns = "".join(
                f'<button type="button" role="tab" class="pl-tab" data-seg="{esc(code)}" aria-selected="false" tabindex="-1">{esc(name)}</button>'
                for code, name in seg_values)
            tabs = f'<div class="pl-tabs" role="tablist" hidden>{tab_btns}</div>\n'
        types = self._type_chips(type_chips, seg_values) if type_chips else ""
        text = soon_text or ("We add a product only after we have read the maker's page and the shop listings. "
                             "Read <a href=\"/how-we-pick/\">how we pick</a>.")
        return (f'<section class="pl pl-none" id="{uid}" data-pl data-segments="{1 if seg_values else 0}" aria-label="Products">\n{tabs}{types}'
                f'<div class="empty-state"><h2>Products are being researched</h2><p>{text}</p></div>\n</section>')

    # ---------- sample products for the preview page ----------

    def samples(self, cat, families, count=18):
        """Made-up products that only appear on the noindex preview page, so the layout can be judged with a full list."""
        bands = [label for _, label in self.bands(cat)]
        brands = ["Brand A", "Brand B", "Brand C", "Brand D", "Brand E"]
        seg = self.segment(cat)
        fl = self.facet_list(cat)
        out = []
        for i in range(count):
            fam = families[i % len(families)]
            p = {"id": f"sample-{i + 1:02d}", "sample": True, "family": fam["slug"], "name": f"Sample product {i + 1:02d}",
                 "brand": brands[i % len(brands)], "price_band": bands[i % len(bands)],
                 "best_for": "One plain line about who it suits",
                 "pros": ["A real strength goes here", "Another real strength"], "cons": ["A real limit"],
                 "editor_pick": i in (0, 7), "rank": i + 1, "features": ["Main feature"], "retailers": {}}
            if seg:
                codes = [c for c, _ in seg["values"]]
                p["audience"] = [codes[i % len(codes)]]
            facets = {}
            for f in fl:
                vals = [c for c, _ in f["values"]]
                facets[f["key"]] = [vals[(i + len(f["key"])) % len(vals)]]
            p["facets"] = facets
            out.append(p)
        return out
