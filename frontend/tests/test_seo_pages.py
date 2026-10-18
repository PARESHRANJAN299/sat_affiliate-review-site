"""The real published state: six broad budget pages, two brand + budget pages and seven brand pages are indexable; titles, descriptions, share images and
structured data on the watches and category pages; nothing outside that scope changes."""
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BROAD = [f"/watches/under-{n}/" for n in (1000, 2000, 3000, 5000, 10000, 20000)]
BRAND_BUDGET = ["/watches/fastrack/under-2000/", "/watches/fossil/under-10000/"]
BRANDS = [f"/watches/brands/{b}/" for b in ("titan", "fossil", "fastrack", "timex", "sonata", "casio", "michael-kors")]
SECTIONS = ["Who this page is for", "Men and women", "Brands in this price range", "Buying advice", "Common questions"]


def page(url):
    return (ROOT / "dist" / url.strip("/") / "index.html").read_text(encoding="utf-8")


def head(url):
    return re.search(r"<head>(.*?)</head>", page(url), re.S).group(1)


def meta(url, name):
    m = re.search(rf'<meta name="{name}" content="([^"]*)"', head(url))
    return m.group(1) if m else None


class PublishedPages(unittest.TestCase):
    def test_pages_exist_are_indexable_and_in_the_sitemap(self):
        sitemap = ET.fromstring((ROOT / "dist" / "sitemap.xml").read_text(encoding="utf-8"))
        locs = {e.text for e in sitemap.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
        for url in BROAD + BRAND_BUDGET + BRANDS:
            h = head(url)
            self.assertNotIn("noindex", h, url)
            self.assertIn(f'<link rel="canonical" href="https://sat.net.in{url}">', h, url)
            self.assertIn(f"https://sat.net.in{url}", locs, url)

    def test_titles_h1_and_descriptions_are_unique_and_sized(self):
        titles, descs = set(), set()
        for url in BROAD + BRAND_BUDGET + BRANDS:
            t = re.search(r"<title>(.*?)</title>", head(url)).group(1)
            d = meta(url, "description")
            self.assertEqual(len(re.findall(r"<h1[ >]", page(url))), 1, url)
            self.assertGreaterEqual(len(d), 100, url)
            self.assertLessEqual(len(d), 160, url)
            self.assertNotIn(t, titles)
            self.assertNotIn(d, descs)
            titles.add(t), descs.add(d)

    def test_copy_sections_render_in_order(self):
        for url in BROAD:
            html = page(url)
            seen = [html.index(f"<h3>{s}</h3>") for s in SECTIONS]
            self.assertEqual(seen, sorted(seen), url)
        for url in BRANDS:   # brand pages: no men/women or brand-breakdown block
            html = page(url)
            self.assertIn("<h3>Who this page is for</h3>", html)
            self.assertNotIn("<h3>Brands in this price range</h3>", html)

    def test_no_prices_ratings_or_forbidden_words_in_the_new_copy(self):
        c = json.loads((ROOT / "src" / "watches" / "collections.json").read_text(encoding="utf-8"))["approved"]
        for url in BROAD + BRAND_BUDGET + BRANDS:
            text = json.dumps(c[url], ensure_ascii=False)
            for bad in ("waterproof", "independent", "M.R.P", "discount", "cashback", "EMI", "stars", "reviews say"):
                self.assertNotIn(bad, text, f"{url}: {bad}")
            self.assertIsNone(re.search(r"(?<!under )(?<!Under )(?<!above )₹\s?\d", text.replace("under ₹", "").replace("Under ₹", "")) , url)

    def test_premium_page_stays_unpublished(self):
        self.assertFalse((ROOT / "dist" / "watches" / "premium" / "index.html").exists())
        self.assertNotIn("/watches/premium/", (ROOT / "dist" / "sitemap.xml").read_text(encoding="utf-8"))

    def test_brand_page_titles_use_the_search_title_and_keep_the_visible_h1(self):
        t = re.search(r"<title>(.*?)</title>", head("/watches/brands/titan/")).group(1)
        self.assertEqual(t, "Titan Watches in India: Compare by Strap and Size — SAT")
        self.assertIn("<h1", page("/watches/brands/titan/"))
        self.assertNotIn("Compare by Strap and Size", re.search(r"<h1[^>]*>(.*?)</h1>", page("/watches/brands/titan/"), re.S).group(1))

    def test_hub_cards_still_open_amazon_even_though_tier_pages_exist(self):
        hub = page("/watches/")
        cards = re.findall(r'<a class="card card-primary lx-budget[^>]*href="([^"]+)"', hub)
        self.assertEqual(len(cards), 7)
        for href in cards:
            self.assertTrue(href.startswith("https://www.amazon.in/s?"), href)
            self.assertIn("tag=pareshsat-21", href)

    def test_menu_cards_link_to_the_published_pages(self):
        about = page("/about/")
        for n in (3000, 5000, 10000, 20000):
            self.assertIn(f'class="card card-compact mega-card" href="/watches/under-{n}/"', about)


class HeadsOfWatchesAndCategories(unittest.TestCase):
    IN_SCOPE = ["/watches/", "/watches/men/", "/watches/women/", "/watches/brands/titan/", "/watches/under-5000/", "/watches/titan/under-2000/",
                "/sports-fitness/", "/beauty-personal-care/", "/home-kitchen/", "/clothing-accessories/", "/products/"]

    def test_hub_title_and_description(self):
        t = re.search(r"<title>(.*?)</title>", head("/watches/")).group(1)
        self.assertEqual(t, "Watches in India: Compare by Budget, Brand and Style — SAT")
        d = meta("/watches/", "description")
        self.assertTrue(120 <= len(d) <= 160, d)
        self.assertRegex(d, r"^Compare \d+ watches from \d+ brands")
        self.assertNotIn("₹", d)

    def test_gender_pages_have_their_own_titles_and_specific_descriptions(self):
        self.assertIn("Men's Watches in India", re.search(r"<title>(.*?)</title>", head("/watches/men/")).group(1).replace("&#x27;", "'"))
        for url in ("/watches/men/", "/watches/women/", "/watches/style/analog/", "/watches/casio/under-5000/"):
            d = meta(url, "description")
            self.assertTrue(len(d) <= 160 and d.startswith("Compare "), (url, d))
            self.assertNotIn("confirm the current price", d)

    def test_share_image_tags_on_in_scope_pages(self):
        for url in self.IN_SCOPE:
            h = head(url)
            self.assertIn('<meta property="og:image" content="https://sat.net.in/images/og/', h, url)
            self.assertIn('<meta property="og:image:width" content="1200">', h)
            self.assertIn('<meta property="og:image:height" content="630">', h)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', h, url)
            img = re.search(r'og:image" content="https://sat.net.in([^"]+)"', h).group(1)
            self.assertTrue((ROOT / "dist" / img.lstrip("/")).exists(), img)
            self.assertLess((ROOT / "dist" / img.lstrip("/")).stat().st_size, 300_000, img)

    def test_out_of_scope_pages_keep_the_plain_card(self):
        for url in ("/", "/about/", "/contact/", "/fashion/"):
            h = head(url)
            self.assertNotIn("og:image", h, url)
            self.assertIn('<meta name="twitter:card" content="summary">', h, url)

    def test_structured_data_is_valid_and_has_no_price_offer_or_rating(self):
        for url in self.IN_SCOPE:
            blocks = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page(url), re.S)]
            types = [b["@type"] for b in blocks]
            self.assertIn("Organization", types, url)
            self.assertIn("BreadcrumbList", types, url)
            raw = json.dumps(blocks)
            for key in ("offers", "price", "aggregateRating", "review", "ratingValue"):
                self.assertNotIn(f'"{key}"', raw, (url, key))
        hub = [json.loads(b) for b in re.findall(r'<script type="application/ld\+json">(.*?)</script>', page("/watches/"), re.S)]
        coll = next(b for b in hub if b["@type"] == "CollectionPage")
        items = coll["mainEntity"]["itemListElement"]
        self.assertEqual(len(items), 30)
        for i in items:
            self.assertTrue(i["url"].startswith("https://sat.net.in/watches/products/"))
            self.assertTrue((ROOT / "dist" / i["url"].replace("https://sat.net.in/", "").strip("/") / "index.html").exists())


if __name__ == "__main__":
    unittest.main()
