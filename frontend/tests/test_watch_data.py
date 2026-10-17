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
        state = self.shop.filter_state(self.shop.products)
        self.assertEqual(state["movement"], 1)  # only quartz is known, so no Movement filter is shown
        self.assertGreaterEqual(state["brand"], 2)

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
        html, keys = self.shop.hub_html()
        self.assertIn('href="/watches/titan/under-2000/"', html)
        self.assertIn("Looking for watches by budget?", html)
        self.assertNotIn("Fossil", html)             # no published collection for it
        self.assertIn('href="/watches/titan/under-3000/"', html)
        self.assertNotIn("Under \u20b95,000", html)  # no published collection for that band
        self.assertLessEqual({"budget", "brand", "people", "guides"}, keys)
        self.assertNotIn("style", keys)               # no published style collection yet

    def test_unapproved_or_thin_collections_never_surface(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        shop.approved = dict(shop.approved)
        shop.approved["/watches/men/under-5000/"] = {"intro": "too short"}
        shop.approved["/watches/titan/under-1000/"] = {"intro": " ".join(["word"] * 120)}   # no Titan watch sits in this band, so no page exists
        urls = [c["url"] for c in shop.published_collections()]
        self.assertEqual(urls, ["/watches/titan/under-2000/", "/watches/titan/under-3000/"])

    def test_hidden_from_hub_when_not_featured(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        shop.approved = {u: dict(e) for u, e in shop.approved.items()}
        shop.approved["/watches/titan/under-2000/"]["featured_on_watch_hub"] = False
        self.assertNotIn("/watches/titan/under-2000/", shop.hub_html()[0])


class HubExtras(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)

    def test_intro_and_how_to_choose(self):
        html, keys = self.shop.hub_html()
        intro = html.split('<p class="hub-intro">')[1].split("</p>")[0]
        self.assertTrue(80 <= len(intro.split()) <= 120)
        self.assertIn("choose", keys)
        for title in ("Budget", "Case size", "Strap", "Water resistance"):
            self.assertIn(f"<h3>{title}</h3>", html)

    def test_counts_are_generated(self):
        c = next(c for c in self.shop.published_collections() if c["url"] == "/watches/titan/under-2000/")
        html, _ = self.shop.hub_html()
        self.assertIn(f'hub-count">{c["count"]}<', html)
        self.assertEqual(c["count"], sum(1 for p in self.shop.products if p["brand"] == "titan" and "under-2000" in self.shop.qualifies(p)))

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
        shown = [p for p in shop.products if p["brand"] == "titan"]
        html = shop.keyword_chips("/watches/titan/under-2000/", shown)
        self.assertIn('data-quick-chip="style" data-value="leather-strap" data-chip-gender="men"', html)
        self.assertIn(">Leather strap watches for men<", html)
        self.assertNotIn("formal", html.lower())      # needs an approved occasion tag first
        self.assertNotIn("slim", html.lower())        # no matching filter
        self.assertNotIn("rose-gold", html)           # no Titan women's watch has a rose gold strap yet


class Slider(unittest.TestCase):
    def test_slider_steps_are_the_bands_that_have_watches(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        body = shop.landing()["_body"]
        self.assertIn("data-price-slider", body)
        self.assertIn("<span>\u20b92k</span><span>\u20b93k</span><span>\u20b95k</span>", body)
        self.assertNotIn("\u20b91k", body)           # no watch sits in Under 1,000 yet, so that step is not offered

    def test_slider_needs_two_steps_and_shows_no_prices(self):
        self.assertEqual(collection.price_slider([("under-2000", "Under \u20b92,000", "\u20b92k", 3)]), "")
        html = collection.price_slider([("a", "Under A", "A", 3), ("b", "Under B", "B", 1)])
        self.assertIn('max="2"', html)
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
