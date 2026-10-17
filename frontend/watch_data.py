"""Watch data engine: one record per watch, normalised, with categories derived automatically.

Nothing here guesses. A value that was not provided stays unknown (the field is simply absent), no filter matches it, and the page says
"not stated". Factual fields (what the maker or listing says) are kept apart from editorial fields (SAT's own judgement):
styles, occasions, features, editorial_labels, best_for, editorial_notes.
Standard library only.
"""
import re
import urllib.parse

UNKNOWN = {"", "unknown", "n/a", "na", "none", "not stated", "-"}
EDITORIAL_LABELS = {"best-value": "Best Value", "office-pick": "Office Pick", "classic-pick": "Classic Pick",
                    "minimal-pick": "Minimal Pick", "first-watch-pick": "First Watch Pick"}
FACT_FIELDS = ["case_diameter_mm", "case_thickness_mm", "band_material", "band_colour", "dial_colour", "case_shape", "movement", "display_type",
               "water_resistance_atm", "water_resistance_metres", "warranty_type", "warranty_duration", "country_of_origin"]
EDITORIAL_FIELDS = ["styles", "occasions", "features", "editorial_labels", "best_for", "editorial_notes"]
COLOUR_ALIASES = {"offwhite": "white", "off-white": "white", "off white": "white", "rose gold": "rose-gold", "rosegold": "rose-gold", "golden": "gold",
                  "grey": "silver", "gray": "silver", "teal green": "green", "teal-green": "green", "tan": "brown", "camel": "brown"}
MATERIAL_ALIASES = {"stainless steel": "stainless-steel", "steel": "stainless-steel", "stainless": "stainless-steel", "leather": "leather", "mesh": "mesh",
                    "silicone": "silicone-rubber", "rubber": "silicone-rubber", "silicone / rubber": "silicone-rubber", "silicone/rubber": "silicone-rubber",
                    "fabric": "fabric-nylon", "nylon": "fabric-nylon", "fabric / nylon": "fabric-nylon"}
GENDER_ALIASES = {"men": ["men"], "man": ["men"], "male": ["men"], "mens": ["men"], "men's": ["men"], "women": ["women"], "woman": ["women"],
                  "female": ["women"], "ladies": ["women"], "womens": ["women"], "women's": ["women"], "unisex": ["men", "women"], "both": ["men", "women"]}
# words that must never appear in editorial or descriptive text of a watch record
BANNED_TEXT = [(re.compile(r"(?:₹|\brs\.?\s?)\s?\d", re.I), "a typed rupee price (use price_band)"),
               (re.compile(r"\b\d(?:\.\d)?\s*(?:/|out of)\s*5\b|\b\d(?:\.\d)?\s*stars?\b|\brated\s+\d", re.I), "a star rating"),
               (re.compile(r"\b(?:lab[- ]tested|personally tested|we tested|tested by us|hands-on tested)\b", re.I), "a testing claim"),
               (re.compile(r"\bwaterproof\b", re.I), "the word waterproof (say water-resistant)"),
               (re.compile(r"\b(?:lowest price|cheapest|best price|price drop)\b", re.I), "a price claim")]


def slug(value):
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower().replace("’", "").replace("'", "")).strip("-")


def known(value):
    if value is None:
        return False
    if isinstance(value, (list, tuple, set)):
        return any(known(v) for v in value)
    return str(value).strip().lower() not in UNKNOWN


def as_list(value):
    if not known(value):
        return []
    if isinstance(value, (list, tuple)):
        return [v for v in value if known(v)]
    return [v.strip() for v in re.split(r"[,;/]|\band\b", str(value)) if known(v)]


def number(value):
    if isinstance(value, (int, float)):
        return float(value)
    m = re.search(r"\d+(?:\.\d+)?", str(value or ""))
    return float(m.group(0)) if m else None


def colours(value):
    out = []
    for v in as_list(value):
        s = COLOUR_ALIASES.get(str(v).strip().lower(), slug(v))
        if s and s not in out:
            out.append(s)
    return out


def water(p):
    """(atm, metres, derived?) from the explicit fields or the stated text; ATM x 10 gives metres. None when nothing is stated."""
    atm, metres = number(p.get("water_resistance_atm")), number(p.get("water_resistance_metres"))
    text = str(p.get("water_resistance", "") or "")
    if atm is None and metres is None and text:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(atm|bar)\b", text, re.I)
        if m:
            atm = float(m.group(1))
        m = re.search(r"(\d+(?:\.\d+)?)\s*(m|metres|meters)\b", text, re.I)
        if m:
            metres = float(m.group(1))
    derived = False
    if metres is None and atm is not None:
        metres, derived = atm * 10, True
    if atm is None and metres is not None:
        atm = metres / 10
    return atm, metres, derived


def price_band(value, budgets):
    """Slug of a configured band from a slug, 'Under ₹2,000', 'under 2000' or a number; '' when unknown."""
    if not known(value):
        return ""
    v = str(value).strip()
    if v in budgets:
        return v
    n = number(v.replace(",", ""))
    if n is not None and f"under-{int(n)}" in budgets:
        return f"under-{int(n)}"
    return "?" + v  # not a configured band: reported as an error by the caller


def normalise(raw, budgets):
    """Canonical record from a raw watch file (new or legacy field names). Keeps the legacy keys the pages already use."""
    p = dict(raw)
    notes = []
    # identity
    name = p.get("product_name") or p.get("model") or ""
    p["product_name"] = name
    brand_name = p.get("brand_name") or ""
    if p.get("model") is None and name:
        stripped = re.sub(r"^\s*" + re.escape(brand_name or str(p.get("brand", "")).replace("-", " ")) + r"\b[\s:,-]*", "", name, flags=re.I)
        p["model"] = stripped or name
    p["gender"] = [g for v in as_list(p.get("gender")) for g in GENDER_ALIASES.get(str(v).strip().lower(), [slug(v)])]
    # commerce
    if p.get("amazon_url") and not (p.get("merchants") or {}).get("amazon", {}).get("url"):
        p["merchants"] = dict(p.get("merchants") or {}, amazon={"url": p["amazon_url"]})
    elif (p.get("merchants") or {}).get("amazon", {}).get("url") and not p.get("amazon_url"):
        p["amazon_url"] = p["merchants"]["amazon"]["url"]
    # price (a band, never a price)
    band = price_band(p.get("price_band") or p.get("budget"), budgets)
    p["price_band"] = band
    p["budget"] = band if band and not band.startswith("?") else None
    # facts
    p["case_diameter_mm"] = number(p.get("case_diameter_mm", p.get("case_size_mm")))
    p["case_size_mm"] = p["case_diameter_mm"] if p["case_diameter_mm"] is None or p["case_diameter_mm"] != int(p["case_diameter_mm"]) else int(p["case_diameter_mm"])
    p["case_thickness_mm"] = number(p.get("case_thickness_mm"))
    mat = str(p.get("band_material") or p.get("strap_material") or "").strip().lower()
    p["band_material"] = MATERIAL_ALIASES.get(mat, slug(mat)) if known(mat) else ""
    p["band_colour"] = colours(p.get("band_colour") or p.get("strap_colour"))
    p["dial_colour"] = colours(p.get("dial_colour"))
    p["case_shape"] = slug(p["case_shape"]) if known(p.get("case_shape")) else ""
    p["case_material"] = slug(p["case_material"]) if known(p.get("case_material")) else ""
    p["movement"] = slug(str(p.get("movement", "")).split()[0]) if known(p.get("movement")) else ""
    p["display_type"] = slug(p["display_type"]) if known(p.get("display_type")) else ""
    atm, metres, derived = water(p)
    p["water_resistance_atm"], p["water_resistance_metres"] = atm, metres
    p["water_metres_derived"] = bool(derived)
    for k in ("warranty_type", "warranty_duration", "country_of_origin", "image_source", "last_verified"):
        p[k] = str(p[k]).strip() if known(p.get(k)) else ""
    p["warranty_type"] = p["warranty_type"].lower()
    p["source_verified"] = p.get("source_verified") if known(p.get("source_verified")) else ("maker page" if p.get("sources") else "")
    # editorial
    p["occasions"] = [slug(o) for o in as_list(p.get("occasions") or p.get("occasion"))]
    p["features"] = [slug(f) for f in as_list(p.get("features"))]
    p["editorial_labels"] = [slug(f) for f in as_list(p.get("editorial_labels"))]
    p["styles"] = [slug(s) for s in as_list(p.get("styles"))]
    # derived styles come from facts, never from the title
    if p["display_type"] == "analog" and "analog" not in p["styles"]:
        p["styles"].append("analog")
    if p["band_material"] == "leather" and "leather-strap" not in p["styles"]:
        p["styles"].append("leather-strap")
    if p["band_material"] == "stainless-steel" and "metal-strap" not in p["styles"]:
        p["styles"].append("metal-strap")
    # legacy display fields used by the existing cards
    if not p.get("strap") and p["band_material"]:
        p["strap"] = " ".join(x for x in (p["band_colour"][0].title() if p["band_colour"] else "", p["band_material"].replace("-", " ")) if x).strip().capitalize() + " band"
    p["strap_material"] = p["band_material"]
    p["purpose"] = p["occasions"]
    p["occasion"] = p["occasions"]
    if not p.get("card_specs"):
        bits = [f'{int(p["case_diameter_mm"]) if p["case_diameter_mm"] else ""} mm case'.strip() if p["case_diameter_mm"] else "",
                p["band_material"].replace("-", " ").capitalize() if p["band_material"] else "",
                p["movement"].capitalize() if p["movement"] else ""]
        p["card_specs"] = " · ".join(b for b in bits if b)
    p["unknown_fields"] = [k for k in FACT_FIELDS + ["price_band"] if not known(p.get(k))]
    return p


def validate(p, brands, styles, genders, budgets):
    """(errors, warnings) for one normalised record. Errors stop the build."""
    errors, warnings = [], []
    pid = p.get("id", "?")
    for k in ("id", "brand", "product_name"):
        if not known(p.get(k)):
            errors.append(f"missing required field {k}")
    if not p.get("gender"):
        errors.append("missing required field gender")
    for g in p.get("gender", []):
        if g not in genders:
            errors.append(f"unknown gender {g!r}")
    for s in p.get("styles", []):
        if s not in styles:
            warnings.append(f"style {s!r} is not configured; it is kept but has no style tile")
    if str(p.get("price_band", "")).startswith("?"):
        errors.append(f"price_band {p['price_band'][1:]!r} is not a configured band (use one of: {', '.join(budgets)})")
    for k in ("price", "mrp", "rating", "ratings", "reviews", "review_count", "stars", "discount"):
        if p.get(k) not in (None, "", [], 0):
            errors.append(f"field {k!r} is not allowed (SAT never stores live prices, ratings or reviews)")
    for l in p.get("editorial_labels", []):
        if l not in EDITORIAL_LABELS:
            errors.append(f"unknown editorial label {l!r} (use: {', '.join(EDITORIAL_LABELS)})")
    text_fields = [p.get("verdict", ""), p.get("best_for", ""), p.get("editorial_notes", "")] + list(p.get("paragraphs", [])) + list(p.get("good", [])) + list(p.get("not_good", []))
    for t in text_fields:
        for rx, what in BANNED_TEXT:
            if isinstance(t, str) and rx.search(t):
                errors.append(f"text contains {what}: {t[:60]!r}")
    url = p.get("amazon_url", "")
    if url:
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            errors.append("amazon_url must be an https link")
        elif not (parts.hostname == "amazon.in" or parts.hostname.endswith(".amazon.in")):
            warnings.append("amazon_url is not an amazon.in address")
    if p.get("water_metres_derived"):
        warnings.append(f"water resistance metres ({p['water_resistance_metres']:g}) are derived from {p['water_resistance_atm']:g} ATM (x10); confirm the source")
    if known(p.get("source_verified")) and "not independently verified" in str(p["source_verified"]):
        warnings.append("specifications are owner-provided and not independently verified; the page says 'as listed'")
    if not known(p.get("source_verified")):
        warnings.append("no source for the specifications (source_verified is empty)")
    if p.get("occasions") and not p.get("editorial_notes") and not p.get("best_for"):
        warnings.append("occasions are editorial: add best_for or editorial_notes to explain them")
    return errors, warnings


# ---------- automatic categories ----------

def bucket(table, value):
    return next((s for s, _, lo, hi in table if value is not None and lo <= value <= hi), "")


def price_qualifies(p, budgets):
    """Every configured band at or above the product's own band: under-2000 also qualifies for under-3000, 5000, ..."""
    own = budgets.get(p.get("budget") or "")
    if not own:
        return []
    return [s for s, b in budgets.items() if b["max"] >= own["max"]]


# ---------- shopper questions ----------

def questions(p, ctx):
    """Relevant questions for one watch, at most 6. Every answer uses only the record's own facts, general definitions, or our written brand notes.
    ctx: {"brand_name", "band_label", "alternatives_url", "brand_notes": {"titan-vs-casio": {"q":..,"a":..}}, "other_brands": set of brand slugs with live watches}"""
    out = []
    mm = p.get("case_diameter_mm")
    if mm:
        n = f"{mm:g}"
        out.append(("fit", f"What does a {n} mm case mean, and will it suit my wrist?",
                    f"The case diameter is the width of the watch case without the crown. This watch lists {n} mm. As a rough guide (not a measurement of your wrist), "
                    "many men's dress watches have a case of about 36 to 42 mm and many women's about 24 to 34 mm. Compare it with a watch you already wear."))
    atm, metres = p.get("water_resistance_atm"), p.get("water_resistance_metres")
    if metres:
        out.append(("water", f"What does {metres:g} m ({atm:g} ATM) water resistance mean?",
                    f"The listing gives a {metres:g} m rating ({atm:g} ATM). That is a pressure-test rating, not the depth you can swim or dive to, and it does not by itself "
                    "mean the watch suits swimming, the shower or hot water. Follow the maker's care instructions. We say water-resistant, never waterproof."))
    mat = p.get("band_material")
    if mat == "leather":
        out.append(("material", "Is the strap leather, and how should I look after it?",
                    "The listing gives a leather strap. Leather looks warm and soft but does not like water, so keep it away from rain and sweat where you can and check the maker's care note."))
    elif mat == "stainless-steel":
        out.append(("material", "Is the strap stainless steel?",
                    "The listing gives a stainless steel band. Metal bands cope with sweat and water better than leather in our view, but check the maker's note and the clasp before you buy."))
    elif mat:
        out.append(("material", f"What is the strap made of?", f"The listing gives {mat.replace('-', ' ')}."))
    if p.get("movement") == "quartz":
        out.append(("movement", "What is a quartz watch, and does it need a battery?",
                    "A quartz watch is powered by a battery and keeps time with a quartz crystal. The battery needs replacing every so often. The listing says this watch is quartz."))
    if p.get("occasions"):
        names = ", ".join(o.replace("-", " ") for o in p["occasions"])
        out.append(("style", "Is this watch suitable for work or special occasions?",
                    f"In our view it suits: {names}. This is our own editorial judgement from its look and listed details, not a claim by the maker."))
    if p.get("budget"):
        out.append(("value", f"Is this a good watch {ctx['band_label'].lower()}?",
                    f"We list it in the {ctx['band_label']} band. Prices change, so check today's price at the retailer, and compare with the alternatives below."))
    for key, note in sorted((ctx.get("brand_notes") or {}).items()):
        if key.startswith("_") or not isinstance(note, dict) or not note.get("q") or not note.get("a"):
            continue
        a, b = (list(note.get("brands", [])) + [None, None])[:2]
        if p["brand"] in (a, b) and a in ctx.get("other_brands", ()) and b in ctx.get("other_brands", ()):
            out.append(("brand", note["q"], note["a"]))
    return out[:6]


# ---------- human-readable intake ----------

INTAKE_KEYS = {
    "product": "product_name", "name": "product_name", "title": "product_name", "brand": "brand", "gender": "gender", "for": "gender",
    "case": "case_diameter_mm", "case diameter": "case_diameter_mm", "case size": "case_diameter_mm", "dial size": "case_diameter_mm", "diameter": "case_diameter_mm",
    "thickness": "case_thickness_mm", "case thickness": "case_thickness_mm",
    "strap": "band_material", "band": "band_material", "strap material": "band_material", "band material": "band_material",
    "strap colour": "band_colour", "strap color": "band_colour", "band colour": "band_colour", "band color": "band_colour",
    "dial colour": "dial_colour", "dial color": "dial_colour", "dial": "dial_colour", "shape": "case_shape", "case shape": "case_shape",
    "movement": "movement", "display": "display_type", "display type": "display_type", "type": "display_type",
    "water resistance": "water_resistance", "water-resistance": "water_resistance", "water": "water_resistance",
    "warranty": "warranty_type", "warranty type": "warranty_type", "warranty duration": "warranty_duration", "country": "country_of_origin",
    "country of origin": "country_of_origin", "amazon url": "amazon_url", "amazon": "amazon_url", "url": "amazon_url", "link": "amazon_url",
    "price band": "price_band", "price": "price_band", "budget": "price_band", "image": "image_source", "styles": "styles", "style": "styles",
    "occasions": "occasions", "occasion": "occasions", "features": "features", "labels": "editorial_labels", "editorial labels": "editorial_labels",
    "best for": "best_for", "notes": "editorial_notes", "source": "source_verified", "asin": "asin",
    "case material": "case_material", "what we like": "good", "likes": "good", "what to know": "not_good", "what to know before buying": "not_good",
    "who should buy": "who_should_buy", "who should skip": "who_should_skip",
}


def parse_intake(text, budgets):
    """Turn 'Key: value' lines into a raw record. Returns (record, unknown_lines)."""
    rec, unknown = {}, []
    for line in text.splitlines():
        line = line.strip().lstrip("-* ").strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        k = INTAKE_KEYS.get(key.strip().lower())
        if not k:
            unknown.append(line)
            continue
        value = value.strip()
        if k == "price_band":
            if re.search(r"₹|rs\.?|\d{3,}", value, re.I) and not re.search(r"under", value, re.I):
                unknown.append(f"{line}  (a price was given; give a band such as 'Under 2000')")
                continue
        rec[k] = value
    if rec.get("product_name") and not rec.get("id"):
        words = [w for w in slug(re.sub(r"^" + re.escape(rec.get("brand", "")), "", rec["product_name"], flags=re.I)).split("-") if w and w not in ("watch", "mens", "womens", "dial", "for", "men", "women")]
        rec["id"] = (slug(rec.get("brand", "")) + "-" + "-".join(words))[:48].strip("-")
        asin = re.search(r"/dp/([A-Z0-9]{10})", rec.get("amazon_url", ""))
        if asin:
            rec["id"] = (rec["id"][:40].strip("-") + "-" + asin.group(1).lower())
    for k in ("styles", "occasions", "features", "editorial_labels"):
        if k in rec:
            rec[k] = as_list(rec[k])
    for k in ("good", "not_good", "who_should_buy", "who_should_skip"):  # sentences: separate items with " | "
        if k in rec:
            rec[k] = [x.strip() for x in str(rec[k]).split("|") if x.strip()]
    return rec, unknown


SCHEMA_ORDER = ["id", "product_name", "brand", "gender", "amazon_url", "asin", "image_source", "price_band", "case_material"] + FACT_FIELDS + EDITORIAL_FIELDS + [
    "who_should_buy", "who_should_skip", "verdict", "paragraphs", "good", "not_good", "sources", "source_verified", "last_verified"]


def canonical(p):
    """The record as it is stored: schema order, normalised values, unknown fields left out (never filled with guesses)."""
    out = {}
    for k in SCHEMA_ORDER:
        v = p.get(k)
        if k == "price_band":
            v = p.get("budget") or ""
        if not known(v):
            continue
        if isinstance(v, float) and v == int(v) and k.endswith("_mm") is False and k != "case_thickness_mm":
            v = int(v)
        if k == "case_diameter_mm" and isinstance(v, float) and v == int(v):
            v = int(v)
        out[k] = v
    return out
