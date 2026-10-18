"""Fashion data permissions, clean rendering and internal section contracts."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fashion


class FashionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.src = Path(self.directory.name)
        (self.src / 'fashion').mkdir()
        self.data = {'approved_image_hosts': ['approved-images.example'], 'approved_affiliate_hosts': ['approved-affiliate.example'], 'products': []}
        self.product = {'id': 'owner-supplied-record', 'slug': 'embroidered-cotton-kurta-set', 'subcategory': 'Kurta Sets', 'description': 'Owner-supplied factual description.', 'attributes': {'Material': 'Cotton'}, 'brand': 'Brand & Co', 'title': 'Title <untrusted>', 'category': 'bags', 'image_url': 'https://approved-images.example/image.jpg', 'affiliate_url': 'https://approved-affiliate.example/visit?x=1&y=2', 'active': True, 'featured': True}

    def save(self):
        (self.src / 'fashion/catalog.json').write_text(json.dumps(self.data))

    def test_production_catalog_has_no_unapproved_products(self):
        products, errors = fashion.catalog(ROOT / 'src')
        self.assertEqual(products, [])
        self.assertEqual(errors, [])

    def test_all_six_internal_cards_have_real_anchor_destinations(self):
        self.save()
        page, errors = fashion.page(self.src, lambda *args: '<svg aria-hidden="true"></svg>')
        self.assertEqual(errors, [])
        self.assertTrue(page['noindex'])
        for slug, *_ in fashion.SECTIONS:
            self.assertIn('href="#' + slug + '"', page['_body'])
            self.assertIn('id="' + slug + '"', page['_body'])
        self.assertNotIn('class="fashion-product"', page['_body'])
        self.assertNotIn('View on Nykaa', page['_body'])

    def test_approved_records_keep_exact_link_and_escape_labels(self):
        self.data['products'] = [self.product]
        self.save()
        products, errors = fashion.catalog(self.src)
        self.assertEqual(errors, [])
        self.assertEqual(len(products), 1)
        card = fashion.product_card(products[0])
        self.assertIn('href="/fashion/products/embroidered-cotton-kurta-set/"', card)
        self.assertNotIn('approved-affiliate.example', card)
        detail = fashion.product_page(products[0], products, 'https://sat.net.in')
        self.assertIn('href="https://approved-affiliate.example/visit?x=1&amp;y=2"', detail['_body'])
        self.assertIn('target="_blank" rel="sponsored nofollow noopener"', detail['_body'])
        self.assertIn('Brand &amp; Co', card)
        self.assertIn('Title &lt;untrusted&gt;', card)

    def test_unapproved_or_lookalike_image_hosts_are_rejected(self):
        self.product['image_url'] = 'https://approved-images.example.unapproved.example/image.jpg'
        self.data['products'] = [self.product]
        self.save()
        products, errors = fashion.catalog(self.src)
        self.assertEqual(products, [])
        self.assertTrue(any('image_url' in error for error in errors))

    def test_drafts_do_not_publish_and_untrusted_commerce_fields_are_unused(self):
        self.product.update({'active': False, 'price': 'FAKE PRICE', 'rating': 'FAKE RATING', 'discount': 'FAKE DISCOUNT'})
        self.data['products'] = [self.product]
        self.save()
        self.assertEqual(fashion.catalog(self.src), ([], []))
        self.product['active'] = True
        card = fashion.product_card(self.product)
        self.assertNotIn('FAKE', card)

    def test_details_share_sat_url_and_related_cards_stay_internal(self):
        related = copy.deepcopy(self.product)
        related.update({'id':'related-record', 'slug':'related-product'})
        page = fashion.product_page(self.product, [self.product, related], 'https://sat.net.in')
        self.assertEqual(page['url'], '/fashion/products/embroidered-cotton-kurta-set/')
        self.assertTrue(page['canonical_always'])
        self.assertIn('fashion-sticky', page['_body'])
        self.assertIn('https%3A%2F%2Fsat.net.in%2Ffashion%2Fproducts%2Fembroidered-cotton-kurta-set%2F', page['_body'])
        self.assertIn('href="/fashion/products/related-product/"', page['_body'])
        self.assertNotIn('Add to cart', page['_body'])

    def make(self, pid, category, brand='Brand & Co', featured=False):
        item = copy.deepcopy(self.product)
        item.update({'id': pid, 'slug': pid, 'category': category, 'brand': brand, 'featured': featured})
        return item

    def test_accessors_and_derived_brands(self):
        items = [self.make('a-1', 'bags', 'Alpha'), self.make('a-2', 'footwear', 'alpha '), self.make('b-1', 'bags', 'Beta', True)]
        self.assertEqual(fashion.get_product_by_slug(items, 'b-1')['brand'], 'Beta')
        self.assertIsNone(fashion.get_product_by_slug(items, 'missing'))
        self.assertEqual([i['id'] for i in fashion.get_products_by_category(items, 'bags')], ['a-1', 'b-1'])
        self.assertEqual(len(fashion.get_products_by_brand(items, 'ALPHA')), 2)
        self.assertEqual([i['id'] for i in fashion.get_featured_products(items)], ['b-1'])
        self.assertEqual(fashion.get_brands(items), [('Alpha', 2), ('Beta', 1)])
        related = fashion.get_related_products(items, items[0])
        self.assertEqual(related[0]['id'], 'b-1')
        self.assertNotIn('a-1', [i['id'] for i in related])

    def test_each_collection_has_its_own_layout(self):
        self.assertEqual([section[5] for section in fashion.SECTIONS], ['feature', 'stagger', 'warm', 'rail', 'energetic', 'luxe'])
        self.data['products'] = [self.make(f'{slug}-{n}', slug) for slug, *_ in fashion.SECTIONS for n in range(2)]
        self.save()
        page, errors = fashion.page(self.src, lambda *args: '')
        self.assertEqual(errors, [])
        for marker in ('fashion-feature-lead', 'fashion-grid-stagger', 'fashion-grid-warm', 'class="fashion-rail"', 'fashion-grid-energetic', 'fashion-grid-luxe'):
            self.assertIn(marker, page['_body'])

    def test_one_product_renders_in_every_layout(self):
        for layout in ('feature', 'stagger', 'warm', 'rail', 'energetic', 'luxe'):
            html = fashion.render_products(layout, [self.product])
            self.assertEqual(html.count('class="fashion-product"'), 1)

    def test_category_tile_uses_approved_product_image_else_sat_editorial_art(self):
        self.data['products'] = [self.make('kurta-1', 'womens-kurtas')]
        self.save()
        page, _ = fashion.page(self.src, lambda *args: '')
        body = page['_body']
        self.assertIn('<img class="fashion-photo" src="https://approved-images.example/image.jpg"', body)
        self.assertIn('/images/fashion/models/pink-dress-640.webp', body)
        self.assertNotIn('/images/fashion/models/pink-dress', body.split('id="womens-kurtas"')[0].split('fashion-category-westernwear')[0])

    def test_empty_catalogue_is_safe_and_has_no_retailer_content(self):
        self.save()
        page, errors = fashion.page(self.src, lambda *args: '')
        body = page['_body']
        self.assertEqual(errors, [])
        self.assertTrue(page['noindex'])
        for forbidden in ('affiliate_url', 'nykaa.com', 'View on Nykaa', 'class="fashion-product"', 'Add to cart'):
            self.assertNotIn(forbidden, body)
        self.assertEqual(body.count(fashion.EMPTY_NOTE), len(fashion.SECTIONS))
        for slug, stem in fashion.ART.items():
            self.assertIn(f'/images/fashion/models/{stem}-640.webp' if stem else f'/images/fashion/editorial/{slug}.svg', body)
        landing, *product_pages = fashion.pages(self.src, lambda *args: '', 'https://sat.net.in')[0]
        self.assertEqual(product_pages, [])

    def test_homepage_journey_order_and_approved_copy(self):
        self.save()
        body = fashion.page(self.src, lambda *args: '')[0]['_body']
        order = ['THE SAT FASHION EDIT', 'Curated style,', 'Explore the Fashion Edit', 'Discover Your Style', 'id="womens-kurtas"', 'id="bags"',
                 'Featured Brands', 'Everyday fashion', 'Style. Confidence. You.', 'Explore Looks', 'A little research.', fashion.SITE_AFFILIATE_NOTE]
        positions = [body.index(text) for text in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn(fashion.BRANDS_EMPTY_NOTE, body)
        self.assertEqual(body.count('href="#fashion-categories"'), 2 + len(fashion.SECTIONS))  # hero CTA, banner CTA, one back link per section

    def test_featured_brands_are_derived_from_products(self):
        self.data['products'] = [self.make('x-1', 'bags', 'Zed'), self.make('x-2', 'bags', 'Zed'), self.make('y-1', 'footwear', 'Yan')]
        self.save()
        page, _ = fashion.page(self.src, lambda *args: '')
        self.assertIn('<strong>Zed</strong><span>2 styles</span>', page['_body'])
        self.assertIn('<strong>Yan</strong><span>1 style</span>', page['_body'])

    def test_temporary_disclosures_are_marked(self):
        self.data['products'] = [self.product]
        self.save()
        landing, _ = fashion.page(self.src, lambda *args: '')
        detail = fashion.product_page(self.product, [self.product], 'https://sat.net.in')
        self.assertIn('data-disclosure="temporary"', landing['_body'])
        self.assertIn(fashion.SITE_AFFILIATE_NOTE, landing['_body'])
        self.assertIn('data-disclosure="temporary"', detail['_body'])
        self.assertIn(fashion.AFFILIATE_NOTE, detail['_body'])

    def test_pages_stay_noindex_with_no_commerce_fields(self):
        self.data['products'] = [self.product]
        self.save()
        for item in fashion.pages(self.src, lambda *args: '', 'https://sat.net.in')[0]:
            self.assertTrue(item['noindex'])
            for word in ('Add to cart', 'Buy now', 'checkout', 'MRP', '% off'):
                self.assertNotIn(word, item['_body'])


    def test_duplicate_ids_and_non_boolean_flags_cannot_publish(self):
        self.data['products'] = [self.product, copy.deepcopy(self.product)]
        self.data['products'][1]['active'] = 'true'
        self.save()
        products, errors = fashion.catalog(self.src)
        self.assertEqual(len(products), 1)
        self.assertTrue(any('unique' in error for error in errors))
        self.assertTrue(any('booleans' in error for error in errors))


if __name__ == '__main__':
    unittest.main()
