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
