"""Sports & Fitness pages: accurate intros, specific descriptions, product lists in structured data; nothing priced or rated."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FAMILIES = ["dumbbells", "kettlebells", "skipping-ropes"]


def page(u):
    return (ROOT / "dist" / u.strip("/") / "index.html").read_text(encoding="utf-8")


class SportsSeo(unittest.TestCase):
    def test_family_pages_with_products_are_indexable_with_specific_descriptions(self):
        seen = set()
        for f in FAMILIES:
            h = page(f"/sports-fitness/fitness/{f}/")
            self.assertNotIn('content="noindex', h, f)
            d = re.search(r'name="description" content="([^"]*)"', h).group(1)
            self.assertTrue(110 <= len(d) <= 160, (f, len(d), d))
            self.assertRegex(d, r"^Compare \d+ ")
            self.assertNotIn("₹", d)
            self.assertNotIn(d, seen)
            seen.add(d)

    def test_intro_no_longer_promises_maker_page_only_picks_once_products_are_listed(self):
        for f in FAMILIES:
            h = page(f"/sports-fitness/fitness/{f}/")
            self.assertNotIn("only after reading the maker", h, f)
            self.assertIn("The products below come from seller listings on Amazon", h, f)
        self.assertIn("only after reading the maker", page("/sports-fitness/fitness/yoga-mats/"))   # a type with no products keeps its advice-only wording

    def test_structured_data_lists_the_products_without_prices_or_ratings(self):
        for u in ["/sports-fitness/"] + [f"/sports-fitness/fitness/{f}/" for f in FAMILIES]:
            blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page(u), re.S)]
            coll = next(b for b in blocks if b["@type"] == "CollectionPage")
            items = coll["mainEntity"]["itemListElement"]
            self.assertGreaterEqual(len(items), 5, u)
            for i in items:
                self.assertTrue(i["url"].startswith("https://sat.net.in/sports-fitness/"), i)
            raw = json.dumps(blocks)
            for key in ("offers", "price", "aggregateRating", "review", "ratingValue"):
                self.assertNotIn(f'"{key}"', raw, (u, key))

    def test_main_page_title_and_description(self):
        h = page("/sports-fitness/")
        self.assertEqual(re.search(r"<title>(.*?)</title>", h).group(1), "Sports &amp; Fitness Buying Guides and Products for India — SAT")
        d = re.search(r'name="description" content="([^"]*)"', h).group(1)
        self.assertTrue(110 <= len(d) <= 160, (len(d), d))
        self.assertRegex(d, r"^Compare \d+ fitness products and \d+ guide recommendations")

    def test_the_existing_guide_recommendations_are_still_listed(self):
        picks = sum(len(json.loads(p.read_text(encoding="utf-8"))["picks"]) for p in (ROOT / "src" / "guides").glob("*/guide.json"))
        products = len(list((ROOT / "src" / "products" / "sports-fitness").glob("*.json")))
        self.assertEqual(page("/sports-fitness/").count("<article "), picks + products)


if __name__ == "__main__":
    unittest.main()
