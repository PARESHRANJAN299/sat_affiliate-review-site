"""Watch data engine: normalisation, no guessing, hierarchical price, dynamic filters, collection gating, intact Amazon links."""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build
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
        self.assertNotIn("Under \u20b93,000", html)  # no published collection for that band
        self.assertLessEqual({"budget", "brand", "people", "guides"}, keys)
        self.assertNotIn("style", keys)               # no published style collection yet

    def test_unapproved_or_thin_collections_never_surface(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        shop.approved = dict(shop.approved)
        shop.approved["/watches/men/under-5000/"] = {"intro": "too short"}
        shop.approved["/watches/titan/under-3000/"] = {"intro": " ".join(["word"] * 120)}   # no page exists for this pair
        urls = [c["url"] for c in shop.published_collections()]
        self.assertEqual(urls, ["/watches/titan/under-2000/"])

    def test_hidden_from_hub_when_not_featured(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        shop.approved = {u: dict(e) for u, e in shop.approved.items()}
        shop.approved["/watches/titan/under-2000/"]["featured_on_watch_hub"] = False
        self.assertNotIn("/watches/titan/under-2000/", shop.hub_html()[0])


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
