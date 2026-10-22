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

    def test_home_tiles_use_approved_product_image_else_sat_editorial_art(self):
        self.data['products'] = [self.make('kurta-1', 'womens-kurtas')]
        self.save()
        html = fashion.discover_html(self.src)
        self.assertIn('<img class="fashion-photo" src="https://approved-images.example/image.jpg"', html)
        self.assertIn('/images/fashion/models/pink-dress-640.webp', html)
        self.assertEqual(html.count('class="fashion-category fashion-category-'), len(fashion.SECTIONS) + 1)  # plus the Watches tile
        for slug, *_ in fashion.SECTIONS:
            self.assertIn(f'href="/fashion/#{slug}"', html)
        self.assertIn('<h2 id="fashion-discover-title">Discover Your Style</h2>', html)

    def test_empty_catalogue_is_safe_and_has_no_retailer_content(self):
        self.save()
        page, errors = fashion.page(self.src, lambda *args: '')
        body = page['_body']
        self.assertEqual(errors, [])
        self.assertTrue(page['noindex'])
        for forbidden in ('affiliate_url', 'nykaa.com', 'View on Nykaa', 'class="fashion-product"', 'Add to cart'):
            self.assertNotIn(forbidden, body)
        self.assertEqual(body.count(fashion.EMPTY_NOTE), len(fashion.SECTIONS))
        for slug, stems in fashion.ART.items():
            for stem in stems:
                self.assertIn(fashion.art_file(stem), body)
            if not stems:
                self.assertIn(f'/images/fashion/editorial/{slug}.svg', body)
        self.assertEqual(fashion.ART['womens-kurtas'], ('ivory-kurta',))
        self.assertEqual(fashion.ART['westernwear'], ('pink-dress', 'orange-dress-pillar'))
        self.assertEqual(fashion.ART['indianwear'], ('purple-saree-support',))
        landing, *product_pages = fashion.pages(self.src, lambda *args: '', 'https://sat.net.in')[0]
        self.assertEqual(product_pages, [])

    def test_fashion_page_is_a_category_switcher_with_the_agreed_journey(self):
        self.save()
        body = fashion.page(self.src, lambda *args: '')[0]['_body']
        order = ['Discover Your Style', 'data-category-tab="womens-kurtas"', 'data-category-tab="bags"', 'id="womens-kurtas"', 'id="bags"',
                 'Featured Brands', 'Everyday fashion', 'Style. Confidence. You.', 'Explore Looks', 'A little research.']
        positions = [body.index(text) for text in order]
        self.assertEqual(positions, sorted(positions))
        self.assertIn(fashion.BRANDS_EMPTY_NOTE, body)
        self.assertEqual(body.count('<h1'), 1)
        self.assertEqual(body.count('data-category-tab='), len(fashion.SECTIONS))
        self.assertEqual(body.count('data-category-panel='), len(fashion.SECTIONS))
        self.assertEqual(body.count('data-category-tab="womens-kurtas" aria-current="true"'), 1)  # nothing listed yet: opens on the first collection
        self.assertEqual(body.count('href="#fashion-categories"'), 1)  # the banner button returns to the switcher
        self.assertNotIn('Back to styles', body)
        for removed in ('fashion-hero', 'THE SAT FASHION EDIT', 'Curated style', 'class="fashion-categories"', 'fashion-category-label'):
            self.assertNotIn(removed, body)  # no hero and no mosaic on this page any more

    def test_switcher_opens_on_the_first_collection_with_products(self):
        self.save()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        src = Path(directory.name)
        (src / 'fashion').mkdir()
        (src / 'fashion/catalog.json').write_text(json.dumps(self.data))
        widget = {'id': 'nykaa-1', 'product_id': '1', 'category': 'footwear', 'source': 'nykaa-fashion', 'active': True, 'featured': False, 'width': 280, 'height': 360,
                  'widget_url': 'https://affiliate.nykaa.com/v2/get_product_widget?affiliate_id=PARESHRA-445235&product_id=1&store=nykaa_fashion'}
        (src / 'fashion/widgets.json').write_text(json.dumps({'allowed_widget_host': 'affiliate.nykaa.com', 'allowed_widget_path': '/v2/get_product_widget', 'allowed_affiliate_id': 'PARESHRA-445235', 'widgets': [widget]}))
        body = fashion.page(src, lambda *args: '')[0]['_body']
        self.assertIn('data-category-tab="footwear" aria-current="true"', body)
        self.assertNotIn('data-category-tab="womens-kurtas" aria-current', body)

    def test_home_page_uses_the_discover_mosaic_and_not_the_old_fashion_block(self):
        home = (ROOT / 'src/pages/home/index.html').read_text()
        self.assertIn('{{fashion_discover}}', home)
        for gone in ('sat-fashion-gateway', 'Curated style', 'sat-fashion-visual', 'Explore the Fashion Edit'):
            self.assertNotIn(gone, home)
        css = json.loads((ROOT / 'src/pages/home/page.json').read_text())['css']
        self.assertIn('fashion-discover', css)
        self.assertIn('fashion-art', css)
        self.assertNotIn('fashion', css[:1])  # the heavy page stylesheet is not loaded on the home page
        self.assertLess((ROOT / 'src/css/components/fashion-discover.css').stat().st_size + (ROOT / 'src/css/components/fashion-art.css').stat().st_size, 8000)

    def test_featured_brands_are_derived_from_products(self):
        self.data['products'] = [self.make('x-1', 'bags', 'Zed'), self.make('x-2', 'bags', 'Zed'), self.make('y-1', 'footwear', 'Yan')]
        self.save()
        page, _ = fashion.page(self.src, lambda *args: '')
        self.assertIn('<strong>Zed</strong><span>2 styles</span>', page['_body'])
        self.assertIn('<strong>Yan</strong><span>1 style</span>', page['_body'])

    def test_landing_has_no_affiliate_sentence_and_product_page_keeps_temporary_note(self):
        self.data['products'] = [self.product]
        self.save()
        landing, _ = fashion.page(self.src, lambda *args: '')
        detail = fashion.product_page(self.product, [self.product], 'https://sat.net.in')
        self.assertNotIn('affiliate links', landing['_body'])
        self.assertNotIn('data-disclosure', landing['_body'])
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




class ReactTabsTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parent.parent
    SHA256 = {'react-18.3.1.production.min.js': 'd949f1c3687aedadcedac85261865f29b17cd273997e7f6b2bfc53b2f9d4c4dd',
              'react-dom-18.3.1.production.min.js': '35f4f974f4b2bcd44da73963347f8952e341f83909e4498227d4e26b98f66f0d'}

    def test_react_is_self_hosted_unmodified_and_loaded_before_the_page_bundle(self):
        import hashlib
        for name, digest in self.SHA256.items():
            data = (self.ROOT / 'src' / 'static' / 'vendor' / name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), digest, name)  # the official 18.3.1 build, unchanged
        body = fashion.page(self.ROOT / 'src', lambda *args: '')[0]['_body']
        react, dom = body.index('/vendor/react-18.3.1.production.min.js'), body.index('/vendor/react-dom-18.3.1.production.min.js')
        self.assertLess(react, dom)
        self.assertEqual(body.count('<script'), 2)
        self.assertNotIn('cdn', body.lower())
        self.assertEqual(fashion.page(self.ROOT / 'src', lambda *args: '')[0]['js'], ['fashion-tabs', 'fashion-widgets'])

    def test_plain_links_remain_as_the_fallback_and_the_old_switcher_steps_aside(self):
        body = fashion.page(self.ROOT / 'src', lambda *args: '')[0]['_body']
        self.assertEqual(body.count('data-category-tab='), len(fashion.SECTIONS))
        tabs_js = (self.ROOT / 'src' / 'js' / 'components' / 'fashion-tabs.js').read_text()
        widgets_js = (self.ROOT / 'src' / 'js' / 'components' / 'fashion-widgets.js').read_text()
        self.assertIn('window.__fashionTabsReact = true', tabs_js)
        self.assertIn('!window.__fashionTabsReact', widgets_js)
        self.assertNotIn('dangerouslySetInnerHTML', tabs_js)



class EditorialTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parent.parent

    def test_editorial_sections_use_the_owner_wording_and_make_no_retailer_promises(self):
        html = fashion.editorial_html()
        for text in ('Time, considered.', 'Watches selected for every style.', 'Made for real life', 'SAT brings fashion, fitness, watches and everyday discoveries into one considered place.',
                     'Simple choices.', 'Everyday edit'):
            self.assertIn(text, html)
        for promise in ('Free shipping', 'Easy returns', 'Secure payment', 'Fast delivery', 'GAZU'):
            self.assertNotIn(promise.lower(), html.lower())

    def test_every_link_goes_to_a_real_page_or_tab_and_every_photo_has_a_credit(self):
        import re
        html = fashion.editorial_html()
        pages = {'/watches/', '/sports-fitness/', '/products/', '/about/', '/watches/men/', '/watches/women/', '/watches/under-5000/', '/watches/under-20000/'}
        for href in re.findall(r'href="([^"#][^"]*)"', html):
            self.assertIn(href, pages, href)
            self.assertTrue((self.ROOT / 'dist' / href.strip('/') / 'index.html').exists() or not (self.ROOT / 'dist').exists(), href)
        credits = {r['file'] for r in json.loads((self.ROOT / 'src' / 'image-credits.json').read_text())['images']}
        for stem, (small, big, height, alt) in fashion.PEOPLE.items():
            for size in (small, big):
                self.assertTrue((self.ROOT / 'src' / 'static' / 'images' / 'fashion' / 'people' / f'{stem}-{size}.webp').exists())
                self.assertIn(f'/images/fashion/people/{stem}-{size}.webp', credits)



class HomeEditTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parent.parent

    def test_home_block_has_a_plain_first_slide_json_for_react_and_working_links(self):
        html = fashion.home_edit_html()
        self.assertEqual(html.count('class="he-slide'), 1)  # only the first slide is plain HTML; React adds the rest
        self.assertIn('STYLE FOR'.title() if False else 'Style for', html)
        data = json.loads(html.split('id="he-data">')[1].split('</script>')[0])
        self.assertEqual([slide['id'] for slide in data], ['everyday', 'calm', 'you'])
        for slide in data:
            self.assertIn(slide['href'], ('/products/', '/fashion/'))
            self.assertTrue(slide['image']['alt'])
        self.assertIn('href="/fashion/#footwear"', html)  # editorial links point at /fashion/ from the home page
        self.assertNotIn('Find your world', html)  # it repeated Discover Your Style
        self.assertNotIn('free shipping', html.lower())

    def test_home_images_exist_with_credits_and_fashion_page_has_no_editorial_block(self):
        credits = {r['file'] for r in json.loads((self.ROOT / 'src' / 'image-credits.json').read_text())['images']}
        for slide in fashion.HOME_EDIT_SLIDES:
            for part in slide['image']['srcset'].split(','):
                path = part.split()[0]
                self.assertTrue((self.ROOT / 'src' / 'static' / path.lstrip('/')).exists(), path)
                self.assertIn(path, credits)
        body = fashion.page(self.ROOT / 'src', lambda *args: '')[0]['_body']
        self.assertNotIn('ed-world', body)

if __name__ == '__main__':
    unittest.main()
