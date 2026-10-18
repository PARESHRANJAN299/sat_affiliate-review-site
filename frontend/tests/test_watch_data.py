"""Watch data engine: normalisation, no guessing, hierarchical price, dynamic filters, collection gating, intact Amazon links."""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build
import collection
import watch_data
import watches

BUDGETS = {"under-2000": {"max": 2000, "label": "Under 2,000"}, "under-3000": {"max": 3000, "label": "Under 3,000"}, "under-5000": {"max": 5000, "label": "Under 5,000"}}
TITAN = json.loads((ROOT / "src/watches/products/titan-analog-offwhite-b01clf3bfw.json").read_text(encoding="utf-8"))


class Engine(unittest.TestCase):
    def test_titan_is_normalised_without_guessing(self):
        p = watch_data.normalise(TITAN, BUDGETS)
        self.assertEqual((p["band_material"], p["band_colour"], p["dial_colour"], p["movement"]), ("stainless-steel", ["gold"], ["white"], "quartz"))
        self.assertEqual((p["water_resistance_atm"], p["water_resistance_metres"]), (3, 30))
        self.assertIn("analog", p["styles"])
        self.assertIn("metal-strap", p["styles"])
        self.assertEqual(p["occasions"], [])            # editorial: never inferred
        self.assertEqual(p["budget"], "under-2000" if "under-2000" in BUDGETS else None)  # the owner confirmed the band
        for field in ("case_shape", "country_of_origin", "warranty_duration"):
            self.assertIn(field, p["unknown_fields"])
        bare = watch_data.normalise({"id": "x", "brand": "titan", "product_name": "X", "gender": "men"}, BUDGETS)
        self.assertIsNone(bare["budget"])               # a band is never guessed
        self.assertIn("price_band", bare["unknown_fields"])

    def test_price_bands_are_hierarchical(self):
        p = watch_data.normalise({"id": "x", "brand": "titan", "product_name": "X", "gender": "men", "price_band": "Under 2000"}, BUDGETS)
        self.assertEqual(watch_data.price_qualifies(p, BUDGETS), ["under-2000", "under-3000", "under-5000"])
        q = watch_data.normalise({"id": "y", "brand": "titan", "product_name": "Y", "gender": "men"}, BUDGETS)
        self.assertEqual(watch_data.price_qualifies(q, BUDGETS), [])

    def test_water_resistance_reads_atm_and_metres(self):
        self.assertEqual(watch_data.water({"water_resistance": "3 ATM"}), (3.0, 30.0, True))
        self.assertEqual(watch_data.water({"water_resistance": "50 m"}), (5.0, 50.0, False))
        self.assertEqual(watch_data.water({}), (None, None, False))

    def test_forbidden_content_is_rejected(self):
        base = {"id": "x", "brand": "titan", "product_name": "X", "gender": ["men"]}
        for extra in ({"verdict": "Costs ₹1,899 today"}, {"verdict": "Rated 4.5 stars"}, {"verdict": "We tested it in the lab"}, {"best_for": "A waterproof watch"}, {"rating": 4.5}, {"price": 1899}):
            errors, _ = watch_data.validate(watch_data.normalise({**base, **extra}, BUDGETS), {"titan": {}}, {}, {"men": {}}, BUDGETS)
            self.assertTrue(errors, extra)

    def test_questions_use_only_known_facts(self):
        p = watch_data.normalise({"id": "x", "brand": "titan", "product_name": "X", "gender": "men"}, BUDGETS)
        self.assertEqual(watch_data.questions(p, {"band_label": ""}), [])
        qs = watch_data.questions(watch_data.normalise(TITAN, BUDGETS), {"band_label": ""})
        self.assertLessEqual(len(qs), 6)
        self.assertNotIn("waterproof?", " ".join(q for _, q, _ in qs).lower())

    def test_intake_text_becomes_a_record(self):
        raw, unknown = watch_data.parse_intake("Product: Titan Slim\nBrand: Titan\nCase: 38 mm\nStrap: Stainless Steel\nPrice: 1899\nColour of sky: blue", BUDGETS)
        self.assertEqual(raw["case_diameter_mm"], "38 mm")
        self.assertNotIn("price_band", raw)              # a typed price is refused
        self.assertEqual(len(unknown), 2)


class Site(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def test_amazon_link_is_kept_exactly(self):
        p = next(q for q in self.shop.products if q["id"] == "titan-analog-offwhite-b01clf3bfw")
        raw = TITAN["amazon_url"]
        self.assertEqual(self.shop.merchant_links(p)[0]["href"], raw)
        self.assertIn("tag=pareshsat-21", raw)

    def test_single_value_groups_are_not_offered(self):
        quartz_only = [p for p in self.shop.products if p.get("movement") == "quartz"]
        state = self.shop.filter_state(quartz_only)
        self.assertEqual(state["movement"], 1)  # only quartz is known, so no Movement filter is shown
        self.assertGreaterEqual(state["brand"], 2)
        both = quartz_only + [p for p in self.shop.products if p.get("movement") == "automatic"]
        if len(both) > len(quartz_only):
            self.assertEqual(self.shop.filter_state(both)["movement"], 2)   # a second movement type makes the filter appear

    def test_collections_need_approval_and_copy(self):
        self.assertTrue(self.shop.collection_noindex("/watches/brands/casio/", self.shop.products[:3]))
        self.assertFalse(self.shop.collection_noindex("/watches/men/", self.shop.products[:1]))

    def test_new_brand_is_registered_by_itself(self):
        class Fake(watches.Watches):
            pass
        p = {"brand": "seiko"}
        self.shop._register_brand(p)
        self.assertEqual(self.shop.brands["seiko"]["name"], "Seiko")
        self.shop.brands.pop("seiko")
        self.shop.config["brands"] = [b for b in self.shop.config["brands"] if b["slug"] != "seiko"]



class NeoIV(unittest.TestCase):
    def test_titan_under_2000_collection_is_published(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        neo = next(p for p in shop.products if p["id"] == "titan-neo-iv-analog-black-b07mxgl85j")
        self.assertEqual(shop.qualifies(neo)[0], "under-2000")
        self.assertIn(("titan", "under-2000"), shop.brand_budget_pages if hasattr(shop, "brand_budget_pages") else shop.brand_budget_pairs())
        meta = shop.brand_budget_page("titan", "under-2000")
        self.assertEqual(meta["url"], "/watches/titan/under-2000/")
        self.assertFalse(meta["noindex"])          # approved by the owner, with its own introduction and at least 3 watches
        self.assertEqual((neo["water_resistance_metres"], neo["band_material"], neo["case_material"]), (50, "leather", "metal"))
        self.assertEqual(neo["movement"], "")      # not stated: never guessed

    def test_sentences_in_intake_are_split_on_bars(self):
        raw, _ = watch_data.parse_intake("What we like: First point | Second point", BUDGETS)
        self.assertEqual(raw["good"], ["First point", "Second point"])


class Hub(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def test_published_collection_carries_metadata(self):
        c = next(c for c in self.shop.published_collections() if c["url"] == "/watches/titan/under-2000/")
        self.assertEqual((c["category"], c["brand"], c["price_band"], c["seo_status"], c["featured_on_watch_hub"]), ("watches", "titan", "under-2000", "indexable", True))
        self.assertEqual(c["genders"], ["men", "women"])

    def test_hub_links_only_to_published_collections(self):
        top, bottom = self.shop.hub_html()
        self.assertEqual(top, "")                      # nothing above the watches repeats the brand, price and Men / Women controls
        self.assertIn('href="/watches/titan/under-2000/"', bottom)
        self.assertIn('href="/watches/titan/under-3000/"', bottom)
        self.assertNotIn("Fossil", bottom)             # no published collection for it
        self.assertNotIn("Under \u20b95,000", bottom)  # no published collection for that band
        for slug_ in ("men", "women"):
            self.assertNotIn(f'href="/watches/{slug_}/"', bottom)   # the journey card shows only the strongest published collections

    def test_unapproved_or_thin_collections_never_surface(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        shop.approved = dict(shop.approved)
        shop.approved["/watches/men/under-5000/"] = {"intro": "too short"}
        shop.approved["/watches/titan/under-1000/"] = {"intro": " ".join(["word"] * 120)}   # no Titan watch sits in this band, so no page exists
        urls = [c["url"] for c in shop.published_collections()]
        self.assertEqual(urls, ["/watches/titan/under-2000/", "/watches/titan/under-3000/", "/watches/sonata/under-1000/"])

    def test_hidden_from_hub_when_not_featured(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        shop.approved = {u: dict(e) for u, e in shop.approved.items()}
        shop.approved["/watches/titan/under-2000/"]["featured_on_watch_hub"] = False
        self.assertNotIn("/watches/titan/under-2000/", shop.hub_html()[1])


class HubExtras(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def test_explore_more_and_how_sat_helps_sit_below_the_watches(self):
        import re
        top, bottom = self.shop.hub_html()
        self.assertEqual(top, "")                      # the top of the page stays short
        self.assertNotIn("<details", bottom)           # no accordion
        self.assertIn("Continue your watch journey", bottom)
        self.assertEqual(bottom.count('href="/watches/guide/"'), 1)      # one card, one link to the guide
        how = bottom.split('id="lx-how"')[1]
        words = len(re.sub(r"<[^>]+>", " ", how).split())
        self.assertTrue(70 <= words <= 140, words)    # useful, crawlable text stays on the page
        for title in ("Compare clearly", "No guessing", "Check before buying"):
            self.assertIn(f"<h3>{title}</h3>", bottom)

    def test_no_card_contains_nested_or_repeated_links(self):
        import re
        body = self.shop.landing()["_body"]
        for block in re.findall(r'<a class="card [^"]*(?:lx-intent|lx-budget|lx-mcard|col-card)[^"]*".*?</a>', body, flags=re.S):
            self.assertEqual(block.count("<a "), 1, block[:80])           # one card = one anchor
        for section in ("lx-intent-row", "lx-budget-row"):
            hrefs = re.findall(r'<a class="card [^"]*lx-(?:intent|budget)[^"]*" href="([^"]+)"', body.split(section)[1].split("</ul>")[0])
            self.assertEqual(len(hrefs), len(set(h + str(i) for i, h in enumerate(hrefs))))

    def test_counts_are_generated(self):
        c = next(c for c in self.shop.published_collections() if c["url"] == "/watches/titan/under-2000/")
        html = self.shop.hub_html()[1]
        self.assertIn(f'<strong class="card-title">Best Titan Watches Under \u20b92,000</strong><span class="card-count">{c["count"]} watches</span>', html)
        self.assertEqual(c["count"], sum(1 for p in self.shop.products if p["brand"] == "titan" and "under-2000" in self.shop.qualifies(p)))

    def test_hub_page_order_is_watches_then_help(self):
        body = self.shop.landing()["_body"]
        self.assertNotIn('<nav class="hub-quick"', body)
        self.assertLess(body.index("data-collection-grid"), body.index('<section class="hub-after"'))
        self.assertNotIn("hub-details", body)

    def test_cards_show_only_the_compact_facts(self):
        p = next(q for q in self.shop.products if q["id"] == "titan-analog-offwhite-b01clf3bfw")
        card = self.shop.card(p)
        self.assertIn("<dt>Case size</dt>", card)
        self.assertNotIn("<dt>Best for</dt>", card)       # editorial: only when approved
        self.assertNotIn("Product details", card.split("watch-spec-rows")[0])
        p2 = dict(p, best_for="Everyday wear")
        self.assertIn("<dt>Best for</dt><dd>Everyday wear</dd>", self.shop.card(p2))

    def test_collection_page_has_reviewed_date_and_affiliate_note(self):
        meta = self.shop.brand_budget_page("titan", "under-2000")
        self.assertIn("Last reviewed:", meta["_body"])
        self.assertIn("As an Amazon Associate I earn from qualifying purchases", meta["_body"])
        self.assertIn('href="/watches/guide/"', meta["_body"])      # internal link inside the buying advice

    def test_links_in_copy_only_to_real_pages(self):
        self.assertEqual(self.shop.linkify("See [guide](/watches/guide/) and [nope](/watches/seiko/under-1000/)"),
                         'See <a href="/watches/guide/">guide</a> and nope')

    def test_related_collections_appear_with_a_second_published_page(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        only = {"/watches/titan/under-2000/": shop.approved["/watches/titan/under-2000/"]}
        shop.approved = only
        self.assertEqual(shop.related_collections("/watches/titan/under-2000/"), "")      # only one published: nothing to relate
        shop.approved = dict(only)
        shop.approved["/watches/men/under-2000/"] = {"intro": " ".join(["word"] * 110)}
        html = shop.related_collections("/watches/titan/under-2000/")
        self.assertIn('href="/watches/men/under-2000/"', html)
        self.assertNotIn('href="/watches/titan/under-2000/"', html)


class Under3000(unittest.TestCase):
    @staticmethod
    def shop_with(own_band_count):
        """The live site with a fixed set of watches: 5 Titan men's watches in Under 2,000 plus some in Under 3,000."""
        shop = watches.Watches(build.SRC, build.CONFIG)
        base = next(p for p in shop.products if p["id"] == "titan-analog-offwhite-b01clf3bfw")
        shop.products = [dict(base, id=f"titan-low-{i}", budget="under-2000", product_name=f"Titan Low {i}", model=f"Low {i}") for i in range(5)]
        shop.products += [dict(base, id=f"titan-mid-{i}", budget="under-3000", product_name=f"Titan Mid {i}", model=f"Mid {i}") for i in range(own_band_count)]
        shop.approved = dict(shop.approved)
        shop.approved["/watches/men/under-3000/"] = {"intro": " ".join(["word"] * 120)}
        return shop

    def test_price_page_needs_watches_inside_its_own_band(self):
        shop = self.shop_with(2)
        meta = shop.budget_page("men", "under-3000")
        self.assertEqual(len([p for p in shop.products if "under-3000" in shop.qualifies(p)]), 7)
        self.assertTrue(meta["noindex"])      # only 2 watches sit in the band; the rest come from Under 2,000 and the page would repeat that one
        self.assertNotIn("/watches/men/under-3000/", [c["url"] for c in shop.published_collections()])

    def test_three_watches_in_the_band_open_the_page(self):
        shop = self.shop_with(3)
        self.assertFalse(shop.budget_page("men", "under-3000")["noindex"])
        self.assertIn("/watches/men/under-3000/", [c["url"] for c in shop.published_collections()])

    def test_titan_price_page_has_a_section_per_shopper_path(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        body = shop.brand_budget_page("titan", "under-2000")["_body"]
        self.assertIn("<h2>Best Titan Watches Under \u20b92,000 for Men</h2>", body)
        self.assertIn("<h2>Best Titan Watches Under \u20b92,000 for Women</h2>", body)

    def test_keyword_chips_follow_the_data(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        shop.keywords = {"/watches/titan/under-2000/": {"men": ["Titan leather strap watches for men under \u20b92,000", "Titan formal watches for men under \u20b92,000",
                                                                  "Titan slim watches for men under \u20b92,000"], "women": ["Titan rose gold watches for women under \u20b92,000"]}}
        shown = [p for p in shop.products if p["brand"] == "titan" and "rose-gold" not in p.get("band_colour", [])]
        html = shop.keyword_chips("/watches/titan/under-2000/", shown)
        self.assertIn('data-quick-chip="style" data-value="leather-strap" data-chip-gender="men"', html)
        self.assertIn(">Leather strap watches for men<", html)
        self.assertNotIn("formal", html.lower())      # needs an approved occasion tag first
        self.assertNotIn("slim", html.lower())        # no matching filter
        self.assertNotIn("rose-gold", html)           # none of these watches has a rose gold strap, so no chip
        with_rose = [p for p in shop.products if "rose-gold" in p.get("band_colour", []) and "women" in p["gender"]]
        self.assertIn('data-value="rose-gold"', shop.keyword_chips("/watches/titan/under-2000/", with_rose))


class Slider(unittest.TestCase):
    def test_slider_steps_are_the_bands_that_have_watches(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        body = shop.landing()["_body"]
        self.assertIn("data-price-slider", body)
        steps = shop.price_steps()
        for _, _, short, _ in steps:
            self.assertIn(f'<i class="sr-dot"></i><span>{short}</span></button>', body)
        # a band with no watch under it is not offered as a step
        empty = [info["label"] for slug_, info in shop.budgets.items() if not any(slug_ in shop.qualifies(p) for p in shop.products)]
        shown = {label for _, label, _, _ in steps}
        for label in empty:
            self.assertNotIn(label, shown)

    def test_slider_needs_two_steps_and_shows_no_prices(self):
        self.assertEqual(collection.price_slider([("under-2000", "Under \u20b92,000", "\u20b92k", 3)]), "")
        html = collection.price_slider([("a", "Under A", "A", 3), ("b", "Under B", "B", 1)])
        self.assertEqual(html.count('class="sr-step"'), 3)          # Any + the two bands
        self.assertIn('aria-label="Maximum budget"', html)
        self.assertIn("hidden", html)

    def test_slider_is_on_collection_pages_too(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        self.assertIn("data-price-slider", shop.brand_budget_page("titan", "under-3000")["_body"])


class Buckets(unittest.TestCase):
    def test_decimal_sizes_never_fall_between_buckets(self):
        b = watches.Watches.bucket
        self.assertEqual(b(watches.Watches.DIAL_SIZES, 40.2), "37-40")
        self.assertEqual(b(watches.Watches.DIAL_SIZES, 40.6), "41-44")
        self.assertEqual(b(watches.Watches.DIAL_SIZES, 45.6), "45-plus")
        self.assertEqual(b(watches.Watches.DIAL_SIZES, 36.4), "36-and-under")
        self.assertEqual(b(watches.Watches.DIAL_SIZES, None), "")
        self.assertEqual(b(watches.Watches.WATER, 29.6), "30-m")

    def test_rounding_is_only_for_the_filter_bucket(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        base = next(p for p in shop.products if p["id"] == "titan-analog-offwhite-b01clf3bfw")
        p = dict(base, case_diameter_mm=40.2, water_resistance_metres=29.6)
        card = shop.card(p)
        self.assertIn("<dt>Case size</dt><dd>40.2 mm</dd>", card)       # exact value shown
        self.assertIn("<dt>Water resistance</dt><dd>29.6 m</dd>", card)
        self.assertIn('data-dial="37-40"', card)                          # rounded value only picks the bucket
        self.assertIn('data-water="30-m"', card)
        self.assertEqual(p["case_diameter_mm"], 40.2)                     # stored data is never changed by filtering

    def test_unknown_size_and_depth_get_no_bucket(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        base = next(p for p in shop.products if p["id"] == "titan-analog-offwhite-b01clf3bfw")
        p = dict(base, case_diameter_mm=None, water_resistance_metres=None)
        card = shop.card(p)
        self.assertIn('data-dial=""', card)
        self.assertIn('data-water=""', card)
        self.assertNotIn("<dt>Case size</dt>", card)
        self.assertNotIn("<dt>Water resistance</dt>", card)


class MetalStrap(unittest.TestCase):
    def test_unspecified_metal_strap_is_still_a_metal_strap(self):
        p = watch_data.normalise({"id": "m", "brand": "titan", "product_name": "M", "gender": "women", "band_material": "Metal"}, BUDGETS)
        self.assertEqual(p["band_material"], "metal")
        self.assertIn("metal-strap", p["styles"])
        shop = watches.Watches(build.SRC, build.CONFIG)
        self.assertIn("metal", watches.Watches.FILTERS[2][3](shop, p))        # strap material filter has its own bucket for it


class DialColours(unittest.TestCase):
    def test_every_stored_dial_colour_can_be_filtered(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        offered = {value for value, _ in next(opts for key, _, opts, _ in shop.FILTERS if key == "dialcolour")}
        stored = {c for p in shop.products for c in p.get("dial_colour", [])}
        self.assertEqual(stored - offered, set())      # a colour on a watch must have a filter option, or the watch can never be found by it

    def test_every_stored_value_has_a_filter_option(self):
        """A value on a watch with no option in its filter group means the watch can never be found by it (as happened with champagne, oval and contemporary)."""
        shop = watches.Watches(build.SRC, build.CONFIG)
        for key, title, options, getter in shop.FILTERS:
            offered = {value for value, _ in options}
            stored = {v for p in shop.products for v in getter(shop, p) if v}
            self.assertEqual(stored - offered, set(), f"{title}: stored values without a filter option")



class CompactIntake(unittest.TestCase):
    TEXT = """Product: Titan Test Watch for Men
Amazon Link: https://www.amazon.in/dp/B000TEST01?tag=pareshsat-21&linkId=abc
ASIN: B000TEST01
Gender: Men
Price Band: Under \u20b93,000
Case Size: 40.2 mm
Strap: Leather
Movement: Quartz
Water Resistance: 30 m
Other Specs: Dial colour Black, Display Analog, Strap colour Brown; Features date, Wibble 7"""

    def test_compact_format_is_understood(self):
        raw, unknown = watch_data.parse_intake(self.TEXT, BUDGETS, {"titan": "Titan"})
        self.assertEqual(raw["brand"], "titan")                       # read from the product name when there is no Brand line
        self.assertEqual(raw["amazon_url"], "https://www.amazon.in/dp/B000TEST01?tag=pareshsat-21&linkId=abc")   # kept exactly
        self.assertEqual((raw["dial_colour"], raw["display_type"], raw["band_colour"]), ("Black", "Analog", "Brown"))
        self.assertEqual(raw["features"], ["date"])
        self.assertTrue(any("Wibble" in u for u in unknown))          # an unknown label is reported, never guessed
        self.assertTrue(raw["id"].startswith("titan-") and raw["id"].endswith("b000test01"))
        p = watch_data.normalise(raw, BUDGETS)
        self.assertEqual(p["budget"], "under-3000")

    def test_multi_word_values_after_a_comma_stay_with_their_spec(self):
        found, unknown = watch_data.parse_other_specs("Strap colour Silver, Rose gold, Dial colour Black, Features chronograph, date, Wibble 7")
        self.assertEqual(found["band_colour"], "Silver, Rose gold")
        self.assertEqual(found["dial_colour"], "Black")
        self.assertEqual(found["features"], "chronograph, date")
        self.assertEqual(unknown, ["Wibble 7"])

    def test_brand_line_wins_and_unknown_brand_is_not_invented(self):
        raw, _ = watch_data.parse_intake("Product: Acme Watch\nBrand: Zed", BUDGETS, {"titan": "Titan"})
        self.assertEqual(raw["brand"], "Zed")
        raw, _ = watch_data.parse_intake("Product: Acme Watch", BUDGETS, {"titan": "Titan"})
        self.assertNotIn("brand", raw)


class Colours(unittest.TestCase):
    def test_grey_is_not_turned_into_silver(self):
        p = watch_data.normalise({"id": "g", "brand": "titan", "product_name": "G", "gender": "men", "band_colour": "Gray", "dial_colour": "Grey"}, BUDGETS)
        self.assertEqual((p["band_colour"], p["dial_colour"]), (["grey"], ["grey"]))


class PremiumCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def test_catalog_budget_rail_has_any_plus_one_step_per_band_with_watches(self):
        body = self.shop.landing()["_body"]
        self.assertIn("price-bands", body)
        self.assertEqual(body.count('class="sr-step"'), len(self.shop.price_steps()) + 1)
        self.assertNotIn("ladder-step", body)
        self.assertNotIn("pb-chip", body)

    def test_gender_plate_counts_come_from_the_catalogue(self):
        body = self.shop.landing()["_body"]
        for g in ("men", "women"):
            n = sum(1 for p in self.shop.products if g in p["gender"])
            self.assertIn(f'<small class="gp-c">{n} watches</small>', body)

    def test_intent_cards_need_approval_and_a_matching_watch(self):
        import re
        shop = self.shop
        saved = shop.settings.get("intent_cards")
        try:
            shop.settings["intent_cards"] = [
                {"title": "Hidden", "text": "x", "approved": False, "filter": {"group": "budget", "value": "under-3000"}},
                {"title": "No filter", "text": "x", "approved": True, "filter": None},
                {"title": "No match", "text": "x", "approved": True, "filter": {"group": "style", "value": "no-such-style"}},
                {"title": "Shown", "text": "A line", "approved": True, "filter": {"group": "budget", "value": "under-3000"}}]
            html = shop.intent_cards(fill=False)
            self.assertEqual(html, "")                  # one real card is not enough for a rail
            html = shop.intent_cards()                  # data-backed cards top the rail up
            self.assertIn("Shown", html)
            for name in ("Hidden", "No filter", "No match"):
                self.assertNotIn(name, html)
            self.assertLessEqual(len(re.findall(r'class="card [^"]*lx-intent"', html)), 4)
            self.assertGreaterEqual(len(re.findall(r'class="card [^"]*lx-intent"', html)), 2)
            shop.settings["intent_cards"] = []
            self.assertEqual(shop.intent_cards(fill=False), "")
            html2 = shop.intent_cards()
            self.assertIn("watches with a", html2)
            self.assertNotIn("chronograph", html2.lower())      # editorial fields never feed a data-backed card
            self.assertNotIn("lx-i-art", html2)                 # compact cards, no large product pictures
        finally:
            shop.settings["intent_cards"] = saved

    def test_popular_collections_come_from_published_pages_and_hide_under_two(self):
        import re
        shop = self.shop
        pubs = [c for c in shop.published_collections() if c["featured_on_watch_hub"]]
        html = shop.popular_collections(pubs)
        self.assertIn("Popular watch collections", html)
        self.assertEqual(len(re.findall(r'class="card card-secondary col-card"', html)), len(pubs))
        for c in pubs:
            self.assertIn(f'href="{c["url"]}"', html)
            self.assertTrue(c["heading"].startswith("Best "))
            self.assertTrue(c["summary"])
        self.assertEqual(shop.popular_collections(pubs[:1]), "")
        self.assertEqual(shop.popular_collections([]), "")

    def test_card_shows_the_band_range_and_marks_its_own_band(self):
        p = next(q for q in self.shop.products if q["id"] == "titan-analog-offwhite-b01clf3bfw")
        card = self.shop.card(p)
        self.assertIn(f'data-own="{p["budget"]}"', card)
        self.assertEqual(self.shop.band_range(dict(p, budget="under-3000")), "\u20b92,000\u2013\u20b93,000")
        self.assertEqual(self.shop.band_range(dict(p, budget="under-2000")), "\u20b91,000\u2013\u20b92,000")
        self.assertEqual(self.shop.band_range(dict(p, budget="")), "")

    def test_dial_art_uses_listed_colours_and_stays_neutral_when_unknown(self):
        known = self.shop.dial_art({"dial_colour": ["green"], "band_colour": ["brown"], "band_material": "leather", "features": ["chronograph", "date"]})
        self.assertIn("#1f4d3a", known)                  # green dial
        self.assertIn("#5b3a25", known)                  # brown strap
        unknown = self.shop.dial_art({"dial_colour": [], "band_colour": [], "band_material": "", "features": []})
        self.assertIn("#d8d1c2", unknown)                # neutral, not a guessed colour
        self.assertIn('aria-hidden="true"', known)       # decorative: the page text carries the facts

    def test_every_listed_colour_has_a_drawing_colour(self):
        for key, _, options, getter in self.shop.FILTERS:
            if key == "dialcolour":
                self.assertEqual({v for v, _ in options} - set(self.shop.DIAL_HEX), set())


class CardSystem(unittest.TestCase):
    """One canonical collection record feeds every card, so titles, counts and order cannot disagree between the menu, hub, popular block and links."""
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def test_every_collection_has_canonical_titles(self):
        for c in self.shop.published_collections():
            self.assertTrue(c["display_title"].startswith("Best "), c["display_title"])
            self.assertTrue(c["seo_title"] and c["short_label"] and c["description"])
            self.assertIn("\u00b7", c["short_label"])               # the short label is the compact chip form, never the full title
            self.assertNotEqual(c["short_label"], c["display_title"])

    def test_collection_name_is_one_function(self):
        self.assertEqual(self.shop.collection_name(brand="titan", band="under-3000", best=True), "Best Titan Watches Under \u20b93,000")
        self.assertEqual(self.shop.collection_name(brand="titan", band="under-3000"), "Titan Watches Under \u20b93,000")

    def test_ordered_collections_follow_priority_and_budget(self):
        recs = self.shop.published_collections()
        bumped = [dict(c, priority=1, featured=(c["href"] == "/watches/titan/under-3000/")) for c in recs]
        self.assertEqual(self.shop.ordered_collections(bumped)[0]["href"], "/watches/titan/under-3000/")      # featured first
        flat = [dict(c, featured=False, priority=100) for c in recs]
        order = list(self.shop.budgets)
        titan = [c for c in self.shop.ordered_collections(flat) if c.get("brand") == "titan"]
        self.assertEqual([c["price_band"] for c in titan], sorted([c["price_band"] for c in titan], key=order.index))   # budget progression
        low = [dict(c, priority=50 if c["href"] == "/watches/titan/under-3000/" else 100) for c in flat]
        self.assertEqual(self.shop.ordered_collections(low)[0]["href"], "/watches/titan/under-3000/")         # priority number wins

    def test_service_helpers_group_the_same_records(self):
        recs = self.shop.published_collections()
        self.assertEqual(self.shop.collection_counts(), {c["href"]: c["count"] for c in recs})
        by_budget = self.shop.collections_by_budget()
        self.assertEqual(sum(len(v) for v in by_budget.values()), sum(1 for c in recs if c.get("price_band")))
        for band, items in by_budget.items():
            self.assertTrue(all(c["price_band"] == band for c in items))
        for brand, items in self.shop.collections_by_brand().items():
            self.assertTrue(all(c["brand"] == brand for c in items))
        for key, title, items in self.shop.available_filters():
            self.assertTrue(items and all(n > 0 for _, _, n in items), key)       # no option without a watch

    def test_budget_tier_colour_progression(self):
        tiers = [self.shop.budget_tier(v) for v in (1000, 2000, 3000, 5000, 10000, 20000, 50000)]
        self.assertEqual(tiers, [1, 2, 3, 4, 5, 6, 7])
        self.assertEqual(self.shop.budget_tier(999999), 7)

    def test_one_anchor_per_card_and_no_plain_text_collection_names(self):
        import re
        bottom = self.shop.hub_html()[1]
        for card in re.findall(r'<a class="card .*?</a>', bottom, flags=re.S):
            self.assertEqual(card.count("<a "), 1)
        text_only = re.sub(r'<a .*?</a>', "", bottom, flags=re.S)
        for c in self.shop.published_collections():
            self.assertNotIn(c["display_title"], text_only)                         # a collection name always sits inside a link

    def test_same_title_in_budget_popular_curated_and_menu_cards(self):
        body = self.shop.landing()["_body"]
        bottom = self.shop.hub_html()[1]
        popular = self.shop.popular_collections(self.shop.menu_discovery())
        for c in self.shop.published_collections():
            self.assertIn(f'<strong class="card-title">{c["display_title"]}</strong>', bottom)    # curated block: the published collections
        for t in self.shop.budget_discovery():
            self.assertIn(f'<span class="visually-hidden">: {t.get("heading") or t["display_title"]}</span>', body)  # budget card: visible text plus the full heading
        for t in self.shop.menu_discovery():
            self.assertIn(f'<strong class="card-title">{t.get("heading") or t["display_title"]}</strong>', popular)  # filter sheet: the same tiers, full headings
            self.assertIn(f'<strong>{t["display_title"]}</strong>', build.ui.menu_row(t))        # category menu row

    def test_page_titles_follow_the_canonical_record(self):
        saved = dict(self.shop.approved)
        try:
            self.shop.approved["/watches/titan/under-3000/"] = dict(self.shop.approved["/watches/titan/under-3000/"], seo_title="Custom Titan Title")
            self.assertEqual(self.shop.page_title("/watches/titan/under-3000/", brand="titan", band="under-3000"), "Custom Titan Title")
            self.assertEqual(self.shop.brand_budget_page("titan", "under-3000")["title"], "Custom Titan Title")
        finally:
            self.shop.approved.clear()
            self.shop.approved.update(saved)
        self.assertEqual(self.shop.page_title("/watches/brands/titan/", brand="titan"), "Titan Watches")     # not published: plain name

    def test_curated_block_hides_below_two_collections(self):
        shop = self.shop
        saved = dict(shop.approved)
        try:
            for url in list(shop.approved)[1:]:
                del shop.approved[url]
            self.assertNotIn("Curated for every budget", shop.hub_html()[1])
        finally:
            shop.approved.clear()
            shop.approved.update(saved)


class BudgetDiscovery(unittest.TestCase):
    """Shopper price tiers come from the whole live catalogue; approved SEO pages are a separate system that only decides where a tier links."""
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def test_tiers_are_counted_from_every_live_watch(self):
        shop = self.shop
        tiers = shop.budget_discovery()
        ids = [t["id"] for t in tiers]
        self.assertEqual(ids, [b for b in shop.settings["budget_discovery"]["tiers"] if b in ids] + ["premium"])
        for t in tiers:
            if t["kind"] == "budget":
                live = [p for p in shop.products if t["id"] in shop.qualifies(p)]
            else:
                live = [p for p in shop.products if p.get("budget") in shop.premium_bands()]
            self.assertEqual(t["count"], len(live), t["id"])                                   # cumulative for Under tiers, own bands above the last tier for Premium
            self.assertEqual(sorted(t["brand_slugs"]), sorted({p["brand"] for p in live}))
            self.assertTrue(t["description"] and t["display_title"] and t["short_label"])

    def test_under_tiers_are_cumulative_and_premium_is_not(self):
        tiers = {t["id"]: t for t in self.shop.budget_discovery()}
        counts = [tiers[i]["count"] for i in self.shop.settings["budget_discovery"]["tiers"] if i in tiers]
        self.assertEqual(counts, sorted(counts))                                               # a cheaper watch also counts under every higher tier
        cut = self.shop.settings["budget_discovery"]["premium_after"]
        own = {p["id"] for p in self.shop.products if p.get("budget") in self.shop.premium_bands()}
        self.assertTrue(own.isdisjoint({p["id"] for p in self.shop.products if cut in self.shop.qualifies(p)}))
        self.assertEqual(tiers["premium"]["count"], len(own))

    def test_a_watch_without_a_known_band_joins_no_tier(self):
        shop = self.shop
        before = {t["id"]: t["count"] for t in shop.budget_discovery()}
        ghost = dict(next(p for p in shop.products if p.get("budget")), id="ghost-watch", budget="", price_band="")
        shop.products.append(ghost)
        try:
            self.assertEqual({t["id"]: t["count"] for t in shop.budget_discovery()}, before)
        finally:
            shop.products.remove(ghost)

    def test_a_tier_links_to_the_filter_until_its_page_is_published(self):
        shop = self.shop
        saved = dict(shop.approved)
        try:
            t = {x["id"]: x for x in shop.budget_discovery()}
            self.assertEqual((t["under-10000"]["href"], t["under-10000"]["destination"]), ("/watches/?price=under-10000", "filter"))
            self.assertEqual(t["premium"]["href"], "/watches/?price=" + shop.premium_top() + "&from=" + shop.settings["budget_discovery"]["premium_after"])
            shop.approved["/watches/under-10000/"] = {"intro": " ".join(["word"] * 120)}
            t = {x["id"]: x for x in shop.budget_discovery()}
            self.assertEqual((t["under-10000"]["href"], t["under-10000"]["destination"], t["under-10000"]["has_page"]), ("/watches/under-10000/", "seo-page", True))
            self.assertEqual(t["under-5000"]["destination"], "filter")                          # only the approved tier switches
            shop.approved["/watches/under-5000/"] = {"intro": "far too short"}
            self.assertEqual({x["id"]: x for x in shop.budget_discovery()}["under-5000"]["destination"], "filter")   # an approval without 100 words is not published
        finally:
            shop.approved.clear()
            shop.approved.update(saved)

    def test_seo_pages_exist_only_for_approved_tiers(self):
        shop = self.shop
        urls = {m["url"] for m in shop.pages()}
        for u in ("/watches/under-1000/", "/watches/under-5000/", "/watches/under-10000/", "/watches/under-20000/", "/watches/premium/"):
            self.assertNotIn(u, urls)                                                           # nothing is generated just because a tier exists
        saved = dict(shop.approved)
        try:
            shop.approved["/watches/under-5000/"] = {"intro": " ".join(["word"] * 120)}
            page = next(m for m in shop.pages() if m["url"] == "/watches/under-5000/")
            self.assertFalse(page["noindex"])
            self.assertEqual(page["title"], "Best Watches Under \u20b95,000 in India")
            shop.approved["/watches/premium/"] = {"intro": " ".join(["word"] * 120)}
            prem = next(m for m in shop.pages() if m["url"] == "/watches/premium/")
            self.assertIn('data-preset-from="under-20000"', prem["_body"])                      # the premium page opens with the premium filter
        finally:
            shop.approved.clear()
            shop.approved.update(saved)

    def test_menu_mix_and_premium_name(self):
        menu = self.shop.menu_discovery()
        self.assertEqual([t["id"] for t in menu], self.shop.settings["budget_discovery"]["menu"][:5])
        self.assertEqual(menu[-1]["display_title"], "Premium Watches")                      # the short label in the menu
        self.assertEqual(menu[-1]["heading"], "Premium Watches Above \u20b920,000")           # the full heading everywhere else
        self.assertEqual(menu[0]["heading"], menu[0]["display_title"])                      # Under tiers have one name
        self.assertEqual(menu[0]["display_title"], "Best Watches Under \u20b93,000")
        self.assertEqual(menu[0]["seo_title"], "Best Watches Under \u20b93,000 in India")

    def test_hub_shows_every_tier_as_one_crawlable_card(self):
        import re
        body = self.shop.landing()["_body"]
        tiers = self.shop.budget_discovery()
        cards = re.findall(r'<a class="card card-primary lx-budget tier-(\d)" href="([^"]+)"[^>]*>.*?</a>', body, flags=re.S)
        self.assertEqual(len(cards), len(tiers))
        aff = self.shop.hub_affiliate()
        expected = [(self.shop.tier_affiliate(t, aff)["url"] if aff and not t["has_page"] else t["href"]).replace("&", "&amp;") for t in tiers]   # its own Amazon search unless the tier has a published page
        self.assertEqual([c[1] for c in cards], expected)
        self.assertEqual([int(c[0]) for c in cards], sorted(int(c[0]) for c in cards))          # the colour never steps back as the price rises
        self.assertEqual(cards[-1][0], "7")                                                     # Premium is the deepest tier
        self.assertIn('data-count="%d"' % len(tiers), body)
        for block in re.findall(r'<a class="card card-primary lx-budget.*?</a>', body, flags=re.S):
            self.assertEqual(block.count("<a "), 1)

    def test_budget_cards_hide_empty_tiers(self):
        self.assertEqual(self.shop.budget_cards([]), "")
        self.assertEqual(self.shop.budget_cards([dict(self.shop.budget_discovery()[0], count=0)]), "")


class ReviewFixes(unittest.TestCase):
    """Regression tests for the findings of the budget-discovery review."""
    LONG = " ".join(["word"] * 120)

    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def approved(self, **entries):
        shop = self.shop
        saved = dict(shop.approved)
        self.addCleanup(lambda: (shop.approved.clear(), shop.approved.update(saved)))
        shop.approved.update(entries)

    def test_menu_keeps_every_approved_destination_type(self):
        import io, contextlib
        self.approved(**{"/watches/under-3000/": {"intro": self.LONG}})
        urls = ["/watches/under-1000/", "/watches/under-3000/", "/watches/titan/under-3000/", "/watches/brands/titan/", "/watches/style/leather-strap/",
                "/watches/men/under-3000/", "/watches/premium/", "/watches/men/"]
        pages = [{"url": u, "title": "Best " + u.strip("/").replace("/", " ") + " in India", "noindex": False} for u in urls]
        old = build.SHOP[0]
        build.SHOP[0] = self.shop
        try:
            build.mega_data(pages)
            m = build.MEGA["watches"]
        finally:
            build.SHOP[0] = old
        listed = {u for _, u in m["price"] + m["brand"] + m["feature"]}
        card_urls = {c["href"] for c in m["cards"][:5]}
        for u in ("/watches/under-1000/", "/watches/titan/under-3000/", "/watches/brands/titan/", "/watches/style/leather-strap/", "/watches/men/under-3000/"):
            self.assertIn(u, listed | card_urls, u)                        # no approved destination type disappears
        self.assertIn("/watches/under-3000/", card_urls)                   # a published tier is a card ...
        self.assertNotIn("/watches/under-3000/", listed)                   # ... and is not repeated as text
        self.assertTrue("/watches/premium/" in listed | card_urls)

    def test_premium_sorts_after_every_under_tier(self):
        self.approved(**{u: {"intro": self.LONG} for u in ("/watches/under-1000/", "/watches/under-3000/", "/watches/premium/")})
        recs = [c for c in self.shop.published_collections() if c["url"] in ("/watches/under-1000/", "/watches/under-3000/", "/watches/premium/")]
        flat = [dict(c, featured=False, priority=100) for c in recs]
        self.assertEqual([c["url"] for c in self.shop.ordered_collections(flat)], ["/watches/under-1000/", "/watches/under-3000/", "/watches/premium/"])
        ids = [t["id"] for t in self.shop.budget_discovery()]
        self.assertEqual(ids[-1], "premium")
        self.assertEqual(ids[:-1], sorted(ids[:-1], key=list(self.shop.budgets).index))

    def test_approved_overrides_beat_generated_defaults(self):
        base = {t["id"]: t for t in self.shop.budget_discovery()}
        self.assertEqual(base["under-5000"]["display_title"], "Best Watches Under \u20b95,000")
        self.approved(**{"/watches/under-5000/": {"intro": self.LONG, "display_title": "Custom Display", "seo_title": "Custom SEO", "short_label": "Custom short", "summary": "Custom summary."},
                         "/watches/under-3000/": {"intro": "too short", "display_title": "Draft Title"}})
        t = {x["id"]: x for x in self.shop.budget_discovery()}
        self.assertEqual((t["under-5000"]["display_title"], t["under-5000"]["seo_title"], t["under-5000"]["short_label"], t["under-5000"]["description"]),
                         ("Custom Display", "Custom SEO", "Custom short", "Custom summary."))
        self.assertEqual(t["under-3000"]["display_title"], "Draft Title")                    # an approved override applies even before the page is publishable
        self.assertEqual(t["under-3000"]["seo_title"], "Best Watches Under \u20b93,000 in India")   # fields without an override keep the generated default
        self.assertEqual(t["under-2000"]["display_title"], "Best Watches Under \u20b92,000")
        self.assertEqual(self.shop.page_title("/watches/under-5000/", band="under-5000"), "Custom SEO")

    def test_more_brands_wording(self):
        f = watches.Watches.brand_list_text
        self.assertEqual(f(["A"]), "A")
        self.assertEqual(f(["A", "B", "C"]), "A, B and C")
        self.assertEqual(f(["A", "B", "C", "D"]), "A, B, C and 1 more brand")
        self.assertEqual(f(["A", "B", "C", "D", "E"]), "A, B, C and 2 more brands")
        for t in self.shop.budget_discovery():
            self.assertNotIn("1 more brands", t["description"] + t["brand_line"])

    def test_premium_copy_is_neutral_and_not_editorial(self):
        t = {x["id"]: x for x in self.shop.budget_discovery()}["premium"]
        self.assertEqual(t["description"], "Explore higher-budget watches from the premium end of the current SAT catalogue.")
        self.assertEqual(self.shop.settings["budget_discovery"]["descriptions"], {})            # no unapproved production copy in settings
        for word in ("fashion", "statement", "luxury", "higher-end"):
            self.assertNotIn(word, t["description"].lower())
        self.approved(**{"/watches/premium/": {"intro": self.LONG, "summary": "Approved line."}})
        self.assertEqual({x["id"]: x for x in self.shop.budget_discovery()}["premium"]["description"], "Approved line.")   # approved copy wins

    def test_premium_heading_and_single_chip_data(self):
        import json as _json
        shop = self.shop
        self.assertEqual(shop.premium_heading(), "Premium Watches Above \u20b920,000")
        cfg = _json.loads(shop.premium_ui())
        self.assertEqual(cfg, {"from": "under-20000", "top": shop.premium_top(), "label": "\u20b920,000+", "heading": "Premium Watches Above \u20b920,000"})
        body = shop.landing()["_body"]
        self.assertIn("data-premium=", body)                                                   # the script gets one label for the pair of internal filters
        self.assertIn("&quot;label&quot;: &quot;\u20b920,000+&quot;", body)
        self.assertEqual(shop.page_title("/watches/premium/", premium=True), "Premium Watches Above \u20b920,000")   # an unpublished premium page is headed by the full heading
        saved = dict(shop.approved)
        self.addCleanup(lambda: (shop.approved.clear(), shop.approved.update(saved)))
        shop.approved["/watches/premium/"] = {"intro": " ".join(["word"] * 120)}
        self.assertEqual(shop.page_title("/watches/premium/", premium=True), "Best Premium Watches in India")   # once published the SEO title is used
        self.assertIn("data-premium=", shop.premium_page()["_body"])

    def test_no_premium_watch_means_no_premium_data(self):
        shop = self.shop
        own = [p for p in shop.products if p.get("budget") in shop.premium_bands()]
        for p in own:
            shop.products.remove(p)
        try:
            self.assertEqual(shop.premium_ui(), "")
            self.assertNotIn("data-premium=", shop.landing()["_body"])
        finally:
            shop.products.extend(own)

    def test_collections_report_lists_every_tier_including_premium(self):
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            build.watch_collections()
        out = buf.getvalue()
        tiers = self.shop.budget_discovery()
        for t in tiers:
            self.assertIn(t["page_url"], out)
            self.assertIn(str(t["count"]), out)
        self.assertIn("Premium", out)
        self.assertIn("/watches/premium/", out)
        self.assertIn("not approved (filter link only)", out)
        self.assertIn("Michael Kors", out)                                                       # brands are listed for the premium tier

    def test_seo_status_follows_the_publishing_rules(self):
        self.approved(**{"/watches/under-5000/": {"intro": "short intro"}, "/watches/under-10000/": {"intro": self.LONG}})
        t = {x["id"]: x for x in self.shop.budget_discovery()}
        self.assertEqual(self.shop.tier_seo_status(t["under-1000"]), "not approved (filter link only)")
        self.assertIn("2 of 100 words", self.shop.tier_seo_status(t["under-5000"]))
        self.assertEqual(self.shop.tier_seo_status(t["under-10000"]), "published and indexable")

    def test_missing_or_malformed_discovery_settings_never_crash(self):
        shop = self.shop
        saved = shop.settings.get("budget_discovery", "__none__")
        self.addCleanup(lambda: shop.settings.__setitem__("budget_discovery", saved) if saved != "__none__" else shop.settings.pop("budget_discovery", None))
        base = [t["id"] for t in shop.budget_discovery()]
        for bad in ("__missing__", None, "text", [], {}, {"tiers": "nope", "premium_after": "no-such-band", "menu": 5, "descriptions": []}):
            if bad == "__missing__":
                shop.settings.pop("budget_discovery", None)
            else:
                shop.settings["budget_discovery"] = bad
            self.assertEqual([t["id"] for t in shop.budget_discovery()], base, bad)               # safe defaults give the same tiers
            self.assertTrue(shop.menu_discovery())
            self.approved(**{"/watches/premium/": {"intro": self.LONG}})
            page = shop.premium_page()                                                            # an approved Premium page builds with no settings at all
            self.assertIn('data-preset-from="under-20000"', page["_body"])
        shop.settings["budget_discovery"] = {"tiers": ["not-a-band"]}
        self.assertEqual(shop.budget_discovery(), [])                                             # nothing to show is not an error
        self.assertEqual(shop.budget_cards(shop.budget_discovery()), "")

    def test_meta_descriptions_are_unique_per_tier_and_overridable(self):
        tiers = self.shop.budget_discovery()
        metas = [self.shop.tier_meta(t) for t in tiers]
        self.assertEqual(len(metas), len(set(metas)))
        for t, m in zip(tiers, metas):
            self.assertLessEqual(len(m), 155, m)
            self.assertIn(str(t["count"]), m)
            self.assertIn(t["brands"][0], m)
        self.approved(**{"/watches/under-5000/": {"intro": self.LONG, "meta_description": "Approved meta for five thousand."}})
        self.assertEqual(self.shop.all_brands_budget_page("under-5000")["description"], "Approved meta for five thousand.")
        self.assertNotEqual(self.shop.all_brands_budget_page("under-1000")["description"], self.shop.all_brands_budget_page("under-2000")["description"])


class HubAffiliateCards(unittest.TestCase):
    """The hero background and every budget card open the owner's Amazon link; nothing on them scrolls the page or filters it."""
    URL = "https://www.amazon.in/s?k=watch&i=watches&linkCode=ll2&tag=pareshsat-21&linkId=d365214107ba31edaa9fc39bb8fa609b&ref_=as_li_ss_tl"
    LONG = " ".join(["word"] * 120)

    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def cards(self, body):
        import re
        return re.findall(r'<a class="card card-primary lx-budget tier-\d" href="([^"]+)"([^>]*)>', body)

    def test_the_link_is_stored_exactly_as_supplied(self):
        self.assertEqual(self.shop.settings["hub_affiliate"]["url"], self.URL)
        self.assertEqual(self.shop.hub_affiliate()["url"], self.URL)

    def test_every_budget_card_and_the_hero_open_the_link_in_a_new_tab(self):
        import re, html, urllib.parse
        body = self.shop.landing()["_body"]
        cards = self.cards(body)
        self.assertEqual(len(cards), len(self.shop.budget_discovery()))
        base = urllib.parse.parse_qs(urllib.parse.urlsplit(self.URL).query)
        for href, rest in cards:
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(html.unescape(href)).query)
            for keep in ("tag", "linkCode", "linkId", "ref_", "i"):
                self.assertEqual(q[keep], base[keep], keep)                                   # the owner's tracking parameters are untouched
            self.assertNotEqual(html.unescape(href), self.URL)                               # but the search is the card's own
            self.assertIn('target="_blank"', rest)
            self.assertIn('rel="sponsored nofollow noopener"', rest)
        hero = re.findall(r'<a class="lx-hero-link" href="([^"]+)"([^>]*)>', body)
        self.assertEqual(len(hero), 1)
        self.assertEqual(html.unescape(hero[0][0]), self.URL)                                  # the hero uses the link exactly as supplied
        self.assertIn("(paid link)", hero[0][1])
        self.assertIn("(opens an Amazon search for", body)

    def test_each_card_searches_amazon_for_its_own_price(self):
        import html, urllib.parse
        shop = self.shop
        aff = shop.hub_affiliate()
        for t in shop.budget_discovery():
            link = shop.tier_affiliate(t, aff)
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(link["url"]).query)
            if t["kind"] == "premium":
                low = shop.budgets[shop.discovery_config()["premium_after"]]["max"]
                self.assertEqual((q["k"][0], q["rh"][0]), (f"watches above {low}", f"p_36:{low * 100}-"), t["id"])      # Amazon prices are in paise
            else:
                top = shop.budgets[t["id"]]["max"]
                self.assertEqual((q["k"][0], q["rh"][0]), (f"watches under {top}", f"p_36:-{top * 100}"), t["id"])
        keys = {shop.tier_affiliate(t, aff)["url"] for t in shop.budget_discovery()}
        self.assertEqual(len(keys), len(shop.budget_discovery()))                              # no two cards share a search

    def test_search_wording_is_configurable_and_safe(self):
        import urllib.parse
        shop = self.shop
        saved = shop.settings["hub_affiliate"]
        self.addCleanup(lambda: shop.settings.__setitem__("hub_affiliate", saved))
        t = next(x for x in shop.budget_discovery() if x["id"] == "under-2000")
        shop.settings["hub_affiliate"] = dict(saved, keyword="best watch for under Rs {max}", price_filter=False)
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(shop.tier_affiliate(t, shop.hub_affiliate())["url"]).query)
        self.assertEqual(q["k"], ["best watch for under Rs 2000"])
        self.assertNotIn("rh", q)                                                             # the price limit can be switched off
        shop.settings["hub_affiliate"] = {"url": "https://www.amazon.in/s?i=watches&tag=pareshsat-21"}   # a base link with no search words
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(shop.tier_affiliate(t, shop.hub_affiliate())["url"]).query)
        self.assertEqual((q["k"], q["tag"]), (["watches under 2000"], ["pareshsat-21"]))
        self.assertIsNone(shop.tier_affiliate(t, None))

    def test_nothing_on_these_cards_scrolls_or_filters_the_page(self):
        import re
        body = self.shop.landing()["_body"]
        for href, rest in self.cards(body):
            self.assertFalse(href.startswith("#") or href.startswith("/"), href)             # no in-page anchor, no on-site filter URL
        js = (build.SRC / "js" / "components" / "collection.js").read_text(encoding="utf-8")
        for name in ("lx-budget", "lx-hero-link", "b-main"):
            self.assertNotIn(name, js)                                                       # no script handles a click on them
        for block in re.findall(r'<a class="card card-primary lx-budget.*?</a>', body, flags=re.S):
            self.assertEqual(block.count("<a "), 1)                                          # one link per card, none inside another

    def test_a_tier_with_its_own_published_page_still_opens_that_page(self):
        shop = self.shop
        saved = dict(shop.approved)
        self.addCleanup(lambda: (shop.approved.clear(), shop.approved.update(saved)))
        shop.approved["/watches/under-10000/"] = {"intro": self.LONG}
        cards = self.cards(shop.landing()["_body"])
        own = [rest for href, rest in cards if href == "/watches/under-10000/"]
        self.assertEqual(len(own), 1)
        self.assertNotIn("target=", own[0])                                                    # an on-site link opens in the same tab
        self.assertEqual(sum(1 for href, rest in cards if href.startswith("https://www.amazon.in/s?")), len(shop.budget_discovery()) - 1)

    def test_plain_on_site_links_without_affiliate_mode_or_url(self):
        shop = self.shop
        saved_active, saved_cfg = shop.affiliate_active, shop.settings.get("hub_affiliate")
        self.addCleanup(lambda: (setattr(shop, "affiliate_active", saved_active), shop.settings.__setitem__("hub_affiliate", saved_cfg)))
        shop.affiliate_active = False
        body = shop.landing()["_body"]
        self.assertNotIn("lx-hero-link", body)
        self.assertEqual([h for h, r in self.cards(body)], [t["href"].replace("&", "&amp;") for t in shop.budget_discovery()])
        shop.affiliate_active = True
        for bad in (None, {}, {"url": ""}, {"url": "http://insecure.example/"}, "text"):
            shop.settings["hub_affiliate"] = bad
            self.assertIsNone(shop.hub_affiliate(), bad)
            self.assertNotIn("lx-hero-link", shop.landing()["_body"])

    def test_only_the_hub_carries_the_link(self):
        self.assertNotIn("lx-hero-link", self.shop.brand_page("titan")["_body"])
        self.assertNotIn(self.URL.replace("&", "&amp;"), self.shop.brand_page("titan")["_body"])

    def test_built_page_keeps_the_link_untouched_and_shows_no_paid_tag_on_it(self):
        import re, html
        page = build.DIST / "watches" / "index.html"
        if not page.exists():
            self.skipTest("run build.py first")
        text = page.read_text(encoding="utf-8")
        hub = [m for m in re.finditer(r'<a [^>]*href="([^"]*)"[^>]*>', text) if html.unescape(m.group(1)).startswith("https://www.amazon.in/s?k=") and ("lx-hero-link" in m.group(0) or "lx-budget" in m.group(0))]
        self.assertEqual(len(hub), 1 + len(self.shop.budget_discovery()))                    # the hero plus one per tier
        self.assertEqual(sum(1 for m in hub if html.unescape(m.group(1)) == self.URL), 1)    # only the hero is the supplied link verbatim
        for m in hub:
            self.assertIn('rel="sponsored nofollow noopener"', m.group(0))
        self.assertEqual(len(re.findall(r'(?:lx-hero-link|lx-budget tier-\d)"[^>]*>(?:(?!</a>).)*</a><small class="paid-link">', text, flags=re.S)), 0)   # no visible "Paid link" tag on them


class UniqueIds(unittest.TestCase):
    def test_two_cards_never_share_svg_ids(self):
        import re
        shop = watches.Watches(build.SRC, build.CONFIG)
        ids = []
        for p in shop.products[:12]:
            ids += re.findall(r'\bid="([^"]+)"', shop.card(p))
        self.assertEqual(len(ids), len(set(ids)))


class WatchTheme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def test_each_watch_gets_its_own_colours(self):
        green = {"dial_colour": ["green"], "band_colour": ["gold"], "band_material": "stainless-steel"}
        blue = {"dial_colour": ["blue"], "band_colour": ["silver"], "band_material": "stainless-steel"}
        self.assertNotEqual(self.shop.watch_theme(green), self.shop.watch_theme(blue))
        for theme in (self.shop.watch_theme(green), self.shop.watch_theme(blue), self.shop.watch_theme({})):
            self.assertRegex(theme, r"--wb:#[0-9a-f]{6};--wc:#[0-9a-f]{6};--wa:#[0-9a-f]{6}")   # unknown colours still give a neutral theme

    def test_card_and_product_page_carry_the_theme(self):
        p = next(q for q in self.shop.products if q["id"] == "titan-analog-offwhite-b01clf3bfw")
        self.assertIn("--wb:", self.shop.card(p))
        page = self.shop.product_page(p)["_body"]
        self.assertIn('class="section watch-pdp-wrap" style="--wb:', page)
        self.assertIn("watch-pdp-photo", page)
        self.assertIn("{{breadcrumb}}", page)

    def test_tilt_script_is_on_the_pages_that_show_drawings(self):
        self.assertIn("watch-tilt", self.shop.landing()["js"])
        p = self.shop.products[0]
        self.assertIn("watch-tilt", self.shop.product_page(p)["js"])

    def test_drawing_has_depth_layers(self):
        art = self.shop.dial_art({"id": "x", "dial_colour": ["blue"], "band_colour": ["silver"], "band_material": "stainless-steel", "features": ["chronograph"]})
        self.assertIn('translate(0 4.5)', art)           # case thickness
        self.assertIn("stroke-width=\"1.1\"", art)       # bevelled bezel edge
        self.assertIn("opacity=\".28\"", art)            # hand shadows


class Duplicates(unittest.TestCase):
    def test_same_id_asin_or_name_is_flagged(self):
        a = {"id": "titan-a-b000000001", "product_name": "Titan A", "amazon_url": "https://www.amazon.in/dp/B000000001?tag=x"}
        self.assertEqual(watch_data.duplicates({"id": "other", "product_name": "Other", "asin": "B000000001"}, [a]), ["same ASIN B000000001 as titan-a-b000000001"])
        self.assertTrue(watch_data.duplicates({"id": "titan-a-b000000001", "product_name": "Zed"}, [a]))
        self.assertTrue(watch_data.duplicates({"id": "x", "product_name": "titan a"}, [a]))
        self.assertEqual(watch_data.duplicates({"id": "y", "product_name": "New", "asin": "B000000002"}, [a]), [])

    def test_live_catalogue_has_no_duplicates(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        asins = [watch_data.asin_of(p) for p in shop.products if watch_data.asin_of(p)]
        self.assertEqual(len(asins), len(set(asins)))

if __name__ == "__main__":
    unittest.main()
