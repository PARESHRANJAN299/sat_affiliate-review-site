"""Catalogue contracts: genuine records, useful no-JS pages and exact affiliate destinations."""
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build
import collection
import watches


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.links.append(dict(attrs))


class CollectionTests(unittest.TestCase):
    def test_full_amazon_destination_survives_every_renderer(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        product = next(p for p in shop.products if p['id'] == 'fossil-decker-ch2885')
        destination = product['merchants']['amazon']['url']
        matches = []
        for page in shop.pages():
            for link in Links(build.tag_outbound_links(page['_body'])).links:
                if 'B00EVZ83J0' in link.get('href', ''):
                    self.assertEqual(link['href'], destination)
                    self.assertIn('sponsored', link.get('rel', ''))
                    matches.append(link)
        self.assertGreater(len(matches), 0)
        self.assertIsNone(product['budget'])

    def test_collection_is_useful_without_javascript_and_escapes_text(self):
        item = {'name': '<Model>', 'description': 'Details & research', 'url': '/guide/', 'filters': {'brand': 'A & B'}}
        card = collection.card(item)
        rendered = collection.render([card], collection.groups([item['filters']], [('brand', 'Brand')]), uid='example', title='Products')
        self.assertIn('&lt;Model&gt;', rendered)
        self.assertNotIn('<Model>', rendered)
        self.assertIn('href="/guide/"', rendered)
        self.assertNotIn('<article hidden', rendered)
        self.assertIn('aria-controls="example-filters"', rendered)
        self.assertIn('id="example-filters"', rendered)

    def test_all_categories_show_real_advice_or_existing_recommendations(self):
        for category in build.CATEGORIES:
            if category['slug'] == 'watches':
                continue
            rendered = build.category_collection(category)
            self.assertIn('data-collection', rendered)
            self.assertNotIn('Sample product', rendered)
            self.assertNotIn('Coming soon', rendered)
            if category['slug'] == 'sports-fitness':
                expected = sum(len(json.loads(path.read_text())['picks']) for path in (build.SRC / 'guides').glob('*/guide.json'))
                self.assertEqual(rendered.count('<article '), expected)
            else:
                self.assertEqual(rendered.count('<article '), len(category['families']))

    def test_watch_routes_share_style_first_browser_and_correct_server_selection(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        class Cards(HTMLParser):
            def __init__(self, text):
                super().__init__(); self.visible = []; self.feed(text)
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "article" and attrs.get("class") == "watch-card" and "hidden" not in attrs:
                    self.visible.append(attrs["data-id"])
        for gender in ("men", "women"):
            page = shop.gender_page(gender)
            self.assertEqual(set(Cards(page["_body"]).visible), {p["id"] for p in shop.products if gender in p["gender"]})
            self.assertLess(page["_body"].index("watch-style-row"), page["_body"].index("watch-quick-row"))
            self.assertLess(page["_body"].index("watch-quick-row"), page["_body"].index("collection-controls"))
            self.assertIn('data-page-size="24"', page["_body"])
            self.assertNotIn("affiliate-box", page["_body"])
            self.assertNotIn("Model reference", page["_body"])

    def test_compact_disclosure_preserves_destination_and_uses_short_label(self):
        destination = 'https://www.amazon.in/dp/TEST?tag=example-21'
        source = '<aside class="affiliate-box" id="affiliate-note"><p>Repeated banner</p></aside><a href="' + destination + '" rel="sponsored nofollow">View on Amazon</a>'
        rendered = build.compact_affiliate_notices(source)
        self.assertNotIn("Repeated banner", rendered)
        self.assertIn('id="affiliate-note"', rendered)
        self.assertIn('class="paid-link">Paid link', rendered)
        self.assertEqual(Links(rendered).links[0]["href"], destination)

    def test_future_product_records_populate_filters_and_exact_link(self):
        for category in build.CATEGORIES:
            if category['slug'] in ('watches', 'sports-fitness'):
                continue
            product = {'id': 'test-only', 'name': 'Test product', 'family': category['families'][0]['slug'], 'brand': 'Test brand', 'pros': ['Fit for everyday use'], 'retailers': {'amazon': {'url': 'https://www.amazon.in/dp/TEST?tag=example-21&linkCode=ll2'}}, 'audience': ['men'], 'price_band': 'Test band'}
            rendered = build.category_collection(category, [product])
            self.assertIn('data-brand="test-brand"', rendered)
            self.assertIn('data-budget="test-band"', rendered)
            self.assertIn('data-audience="men"', rendered)
            amazon = [link['href'] for link in Links(rendered).links if 'amazon.in' in link.get('href', '')]
            self.assertEqual(amazon, [product['retailers']['amazon']['url']])



class TitleTests(unittest.TestCase):
    def test_watch_pages_keep_their_own_title(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        pages = {m["url"]: m for m in shop.pages()}
        self.assertEqual(pages["/watches/"]["title"], "Watches for every day.")
        self.assertIn("Casio", pages["/watches/brands/casio/"]["title"])
        self.assertIn("Formal", pages["/watches/style/formal/"]["title"])
        for url, meta in pages.items():
            self.assertNotEqual(meta["title"], "Case material", url)

if __name__ == '__main__':
    unittest.main()
