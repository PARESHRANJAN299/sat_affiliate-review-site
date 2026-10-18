"""Official Nykaa affiliate widgets: strict validation, unchanged URLs, safe rendering and graceful fallbacks."""
import copy
import html
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import fashion

FIRST_URL = ('https://affiliate.nykaa.com/v2/get_product_widget?ad_id=6ad481f51bde18e19f3d2802&add_resources=True&affiliate_id=PARESHRA-445235'
             '&product_id=28560370&store=nykaa_fashion&text_color=000000&theme_variation=TEXT_AND_IMAGE&theme=affiliate'
             '&aff_link_type=affiliate%3Anap_dashboard%3Aproduct&hlp=hlpa')


def base(widgets, collections=None):
    data = {'allowed_widget_host': 'affiliate.nykaa.com', 'allowed_widget_path': '/v2/get_product_widget', 'allowed_affiliate_id': 'PARESHRA-445235', 'widgets': widgets}
    if collections is not None:
        data['collections'] = collections
    return data


COLLECTION = {'id': 'kurta-sets-search', 'category': 'womens-kurtas', 'title': 'Search results for Women’s kurtas set', 'suggestions': ['Pure cotton kurtas set for women', 'Indian kurta set for women pure cotton']}


class WidgetTests(unittest.TestCase):
    def setUp(self):
        self.record = {'id': 'nykaa-28560370', 'product_id': '28560370', 'category': 'womens-kurtas', 'source': 'nykaa-fashion', 'widget_url': FIRST_URL,
                       'width': 280, 'height': 360, 'active': True, 'featured': True}

    def problems(self, **changes):
        record = {**self.record, **changes}
        return fashion.validate_widgets(base([record]))

    def test_production_widgets_are_valid_and_urls_are_unchanged(self):
        items, problems = fashion.widgets(ROOT / 'src')
        self.assertEqual(problems, [])
        self.assertGreaterEqual(len(items), 3)
        self.assertEqual({item['category'] for item in items}, {'womens-kurtas'})
        first = next(item for item in items if item['product_id'] == '28560370')
        self.assertEqual(first['widget_url'], FIRST_URL)
        for item in items:
            self.assertIn('affiliate_id=PARESHRA-445235', item['widget_url'])
            self.assertIn('product_id=' + item['product_id'], item['widget_url'])

    def test_production_widgets_keep_file_order_and_have_no_leftover_collection(self):
        data = fashion.read_widgets(ROOT / 'src')
        items, problems = fashion.widgets(ROOT / 'src')
        self.assertEqual(problems, [])
        self.assertFalse(any('collection' in w for w in data['widgets']))
        listed = [w['product_id'] for w in data['widgets'] if w['active'] and not w['featured']]
        self.assertEqual([i['product_id'] for i in items if not i['featured']], listed)  # file order is kept

    def test_collection_rules(self):
        grouped = {**self.record, 'collection': 'kurta-sets-search'}
        items, problems = fashion.validate_widgets(base([grouped], [COLLECTION]))
        self.assertEqual((len(items), problems), (1, []))
        for name, data in {
            'undefined collection': base([grouped], []),
            'other category': base([grouped], [{**COLLECTION, 'category': 'bags'}]),
            'collection not text': base([{**self.record, 'collection': 5}], [COLLECTION]),
            'duplicate collection id': base([self.record], [COLLECTION, COLLECTION]),
            'extra collection field': base([self.record], [{**COLLECTION, 'html': '<b>'}]),
            'bad suggestions': base([self.record], [{**COLLECTION, 'suggestions': 'text'}]),
            'too many suggestions': base([self.record], [{**COLLECTION, 'suggestions': ['x'] * 13}]),
            'empty title': base([self.record], [{**COLLECTION, 'title': ' '}]),
            'collections not a list': {**base([self.record]), 'collections': {}},
        }.items():
            self.assertTrue(fashion.validate_widgets(data)[1], name)

    def test_valid_record_passes(self):
        items, problems = self.problems()
        self.assertEqual(problems, [])
        self.assertEqual(len(items), 1)

    def test_raw_html_and_unknown_fields_are_rejected(self):
        for field in ('widget_html', 'html', 'image_url', 'price'):
            items, problems = self.problems(**{field: '<iframe src="x"></iframe>'})
            self.assertEqual(items, [], field)
            self.assertTrue(any('unsupported fields' in p for p in problems), field)

    def test_only_the_official_widget_url_is_accepted(self):
        bad = {
            'other host': FIRST_URL.replace('affiliate.nykaa.com', 'evil.example'),
            'lookalike host': FIRST_URL.replace('affiliate.nykaa.com', 'affiliate.nykaa.com.evil.example'),
            'http': FIRST_URL.replace('https://', 'http://'),
            'other path': FIRST_URL.replace('/v2/get_product_widget', '/v2/other'),
            'other affiliate': FIRST_URL.replace('PARESHRA-445235', 'SOMEONE-ELSE'),
            'product mismatch': FIRST_URL.replace('product_id=28560370', 'product_id=1'),
            'other store': FIRST_URL.replace('nykaa_fashion', 'nykaa'),
            'quote break out': FIRST_URL + '"onload="alert(1)',
            'tag': FIRST_URL + '<script>',
            'space': FIRST_URL + ' x',
            'userinfo': FIRST_URL.replace('https://', 'https://user@'),
            'fragment': FIRST_URL + '#x',
        }
        for name, url in bad.items():
            items, problems = self.problems(widget_url=url)
            self.assertEqual(items, [], name)
            self.assertTrue(problems, name)

    def test_other_field_rules(self):
        self.assertTrue(self.problems(category='unknown')[1])
        self.assertTrue(self.problems(product_id='abc')[1])
        self.assertTrue(self.problems(active='true')[1])
        self.assertTrue(self.problems(width=5000)[1])
        self.assertTrue(self.problems(height=True)[1])
        self.assertTrue(fashion.validate_widgets(base([self.record, copy.deepcopy(self.record)]))[1])

    def test_get_it_on_nykaa_button_needs_an_approved_link(self):
        link = 'https://www.nykaafashion.example/p/28560370?aff=1&x=%3A'
        data = base([{**self.record, 'affiliate_url': link}])
        self.assertTrue(fashion.validate_widgets(data)[1])  # host not approved yet
        data['allowed_product_link_hosts'] = ['www.nykaafashion.example']
        items, problems = fashion.validate_widgets(data)
        self.assertEqual((len(items), problems), (1, []))
        self.assertEqual(items[0]['affiliate_url'], link)
        for bad in ('http://www.nykaafashion.example/p/1', 'https://www.nykaafashion.example.evil.example/p/1', 'https://evil.example/p/1',
                    'https://www.nykaafashion.example/p/1 x', 'javascript:alert(1)', 5):
            data['widgets'][0]['affiliate_url'] = bad
            self.assertTrue(fashion.validate_widgets(data)[1], bad)
        self.assertTrue(fashion.validate_widgets({**base([self.record]), 'allowed_product_link_hosts': ['Bad Host']})[1])

    def test_inactive_widgets_are_not_published(self):
        items, problems = self.problems(active=False)
        self.assertEqual((items, problems), ([], []))


class WidgetPageTests(unittest.TestCase):
    def build(self, widgets):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        src = Path(directory.name)
        (src / 'fashion').mkdir()
        (src / 'fashion/catalog.json').write_text(json.dumps({'approved_image_hosts': [], 'approved_affiliate_hosts': [], 'products': []}))
        if widgets is not None:
            (src / 'fashion/widgets.json').write_text(json.dumps(base(widgets)))
        return fashion.page(src, lambda *args: '')

    def record(self, product_id='28560370', url=FIRST_URL, **extra):
        return {'id': f'nykaa-{product_id}', 'product_id': product_id, 'category': 'womens-kurtas', 'source': 'nykaa-fashion', 'widget_url': url,
                'width': 280, 'height': 360, 'active': True, 'featured': False, **extra}

    def test_widget_renders_official_iframe_with_unchanged_url(self):
        page, problems = self.build([self.record()])
        body = page['_body']
        self.assertEqual(problems, [])
        urls = [html.unescape(u) for u in re.findall(r'<iframe src="([^"]+)"', body)]
        self.assertEqual(urls, [FIRST_URL])
        self.assertIn('class="nykaa-product-shell"', body)
        self.assertIn('title="Nykaa Fashion product"', body)
        self.assertIn('loading="lazy"', body.split('<iframe')[1])
        self.assertIn('height:360px;width:280px;overflow:hidden;', body)

    def test_kurta_section_is_retailer_powered_and_others_stay_empty(self):
        page, _ = self.build([self.record()])
        body = page['_body']
        kurtas = body.split('id="womens-kurtas"')[1].split('id="westernwear"')[0]
        self.assertIn('THE KURTA EDIT', kurtas)
        self.assertIn('Elegant Indian styles selected for everyday and occasion wear.', kurtas)
        self.assertIn('/images/fashion/models/ivory-banner-1536.jpg', kurtas)
        self.assertNotIn(fashion.EMPTY_NOTE, kurtas)
        self.assertEqual(body.count(fashion.EMPTY_NOTE), len(fashion.SECTIONS) - 1)
        self.assertEqual(body.count('<iframe'), 1)

    def test_each_card_has_a_sat_share_link_and_no_whatsapp_button(self):
        page, _ = self.build([self.record(), self.record('27826893', FIRST_URL.replace('28560370', '27826893'))])
        body = page['_body']
        self.assertEqual(body.count('class="nykaa-product-shell"'), 2)
        for pid in ('28560370', '27826893'):
            self.assertIn(f'id="pick-{pid}"', body)
            self.assertIn(f'data-url="https://sat.net.in/fashion/#pick-{pid}"', body)
        self.assertEqual(body.count('data-copy-pick'), 2)
        self.assertEqual(body.count('data-share-pick'), 2)
        self.assertNotIn('wa.me', body)
        self.assertNotIn('WhatsApp', body)
        self.assertIn('data-widget-rail', body)
        self.assertNotIn('nykaa-get', body)  # no button until an approved affiliate_url is supplied

    def test_get_it_on_nykaa_button_renders_with_sponsored_link(self):
        link = 'https://www.nykaafashion.example/p/28560370?aff=1&x=2'
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        src = Path(directory.name)
        (src / 'fashion').mkdir()
        (src / 'fashion/catalog.json').write_text(json.dumps({'approved_image_hosts': [], 'approved_affiliate_hosts': [], 'products': []}))
        data = base([self.record(affiliate_url=link)])
        data['allowed_product_link_hosts'] = ['www.nykaafashion.example']
        (src / 'fashion/widgets.json').write_text(json.dumps(data))
        body = fashion.page(src, lambda *args: '')[0]['_body']
        self.assertIn('class="nykaa-get"', body)
        self.assertIn('href="https://www.nykaafashion.example/p/28560370?aff=1&amp;x=2" target="_blank" rel="sponsored nofollow noopener"', body)
        self.assertIn('Get it on Nykaa', body)

    def test_a_hundred_widgets_preview_on_landing_and_all_list_on_category_page(self):
        many = [self.record(str(1000 + n), FIRST_URL.replace('28560370', str(1000 + n))) for n in range(100)]
        pages, problems = self.build_pages(many, collections=())
        self.assertEqual(problems, [])
        landing, category = pages[0], pages[1]
        self.assertEqual(landing['_body'].count('<iframe'), fashion.WIDGET_RAIL_LIMIT)
        self.assertEqual(category['_body'].count('<iframe'), 100)
        self.assertEqual(category['_body'].count('loading="lazy" style="height:360px'), 100)
        self.assertEqual(len(set(__import__('re').findall(r'id="(pick-\d+)"', category['_body']))), 100)
        self.assertEqual(landing['js'], ['fashion-widgets'])
        self.assertEqual(landing['_body'].count('class="nykaa-explore-link"'), 1)

    def build_pages(self, widgets, collections=(COLLECTION,), category_pages=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        src = Path(directory.name)
        (src / 'fashion').mkdir()
        (src / 'fashion/catalog.json').write_text(json.dumps({'approved_image_hosts': [], 'approved_affiliate_hosts': [], 'products': []}))
        data = base(widgets, list(collections))
        if category_pages is not None:
            data['category_pages'] = category_pages
        (src / 'fashion/widgets.json').write_text(json.dumps(data))
        return fashion.pages(src, lambda *args: '', 'https://sat.net.in')

    CATEGORY_PAGE = {'category': 'womens-kurtas', 'h1': 'Women’s Kurtas', 'intro': 'Intro text.', 'meta_title': 'Women’s Kurtas and Kurta Sets from Nykaa Fashion',
                     'meta_description': 'A description.', 'main_heading': 'Search results for Women’s Kurtas', 'explore_label': 'Explore Kurtis'}

    def test_landing_has_one_rail_and_one_explore_button(self):
        second = self.record('27421822', FIRST_URL.replace('28560370', '27421822'), collection='kurta-sets-search')
        pages, problems = self.build_pages([self.record(), second], category_pages=[self.CATEGORY_PAGE])
        landing = pages[0]['_body']
        self.assertEqual(problems, [])
        self.assertEqual(landing.count('data-rail-group'), 1)
        self.assertEqual(landing.count('data-widget-rail'), 1)
        self.assertEqual(landing.count('<iframe'), 1)  # the collection widget is not on the landing rail
        self.assertNotIn('<h3>', landing)
        self.assertEqual(landing.count('class="nykaa-explore-link" href="/fashion/womens-kurtas/"'), 1)
        self.assertIn('Explore Kurtis', landing)
        self.assertEqual(landing.count(fashion.WIDGET_AFFILIATE_NOTE), 1)
        self.assertEqual(landing.count('id="pick-28560370"'), 1)

    def test_category_page_lists_everything_as_search_results(self):
        second = self.record('27421822', FIRST_URL.replace('28560370', '27421822'), collection='kurta-sets-search')
        pages, _ = self.build_pages([self.record(), second], category_pages=[self.CATEGORY_PAGE])
        self.assertEqual([p['url'] for p in pages], ['/fashion/', '/fashion/womens-kurtas/'])
        category = pages[1]
        body = category['_body']
        self.assertTrue(category['noindex'])
        self.assertTrue(category['canonical_always'])
        self.assertEqual(category['title'], 'Women’s Kurtas and Kurta Sets from Nykaa Fashion')
        self.assertEqual(category['description'], 'A description.')
        self.assertEqual(category['breadcrumbs'], [['Fashion Edit', '/fashion/'], ['Women’s Kurtas', '/fashion/womens-kurtas/']])
        self.assertIn('{{breadcrumb}}', body)
        self.assertEqual(body.count('<h1>'), 1)
        self.assertEqual(body.count('<iframe'), 2)
        self.assertEqual(body.count('data-widget-grid'), 2)
        self.assertIn('Search results for Women’s Kurtas', body)
        self.assertIn('Search results for Women’s kurtas set', body)
        self.assertIn('Suggestions:', body)
        self.assertEqual(body.count(fashion.WIDGET_AFFILIATE_NOTE), 1)
        self.assertEqual(category['js'], ['fashion-widgets'])
        for pid in ('28560370', '27421822'):  # shares point at this page, never the Nykaa link
            self.assertIn(f'data-url="https://sat.net.in/fashion/womens-kurtas/#pick-{pid}"', body)
        self.assertNotIn('wa.me', body)

    def test_category_page_defaults_and_no_page_without_widgets(self):
        pages, _ = self.build_pages([self.record()], collections=(), category_pages=None)
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[1]['title'], 'Women’s Kurtas from Nykaa Fashion')
        self.assertIn('Search results for Women’s Kurtas', pages[1]['_body'])
        self.assertEqual(len(self.build_pages([], collections=())[0]), 1)

    def test_all_widgets_in_collections_still_fill_the_landing_rail(self):
        only = self.record(collection='kurta-sets-search')
        pages, _ = self.build_pages([only])
        self.assertEqual(pages[0]['_body'].count('<iframe'), 1)
        self.assertEqual(pages[0]['_body'].count(fashion.WIDGET_AFFILIATE_NOTE), 1)

    def test_category_page_fields_are_validated(self):
        ok = {'category': 'womens-kurtas', 'h1': 'Women’s Kurtas'}
        self.assertEqual(fashion.validate_widgets({**base([self.record()]), 'category_pages': [ok]})[1], [])
        for name, entry in {'unknown category': {'category': 'nope'}, 'extra field': {**ok, 'html': '<b>'}, 'long description': {**ok, 'meta_description': 'x' * 200},
                            'empty': {**ok, 'h1': ' '}, 'not text': {**ok, 'intro': 5}}.items():
            self.assertTrue(fashion.validate_widgets({**base([self.record()]), 'category_pages': [entry]})[1], name)
        self.assertTrue(fashion.validate_widgets({**base([self.record()]), 'category_pages': [ok, ok]})[1])
        self.assertTrue(fashion.validate_widgets({**base([self.record()]), 'category_pages': {}})[1])

    def test_disclosure_appears_only_with_widgets(self):
        with_widgets, _ = self.build([self.record()])
        without, _ = self.build(None)
        self.assertEqual(with_widgets['_body'].count(fashion.WIDGET_AFFILIATE_NOTE), 1)
        self.assertIn('data-disclosure="temporary"', with_widgets['_body'])
        self.assertNotIn(fashion.WIDGET_AFFILIATE_NOTE, without['_body'])
        self.assertIn(fashion.EMPTY_NOTE, without['_body'].split('id="womens-kurtas"')[1].split('id="westernwear"')[0])

    def test_no_retailer_data_is_copied_into_the_page(self):
        body = self.build([self.record()])[0]['_body']
        for forbidden in ('nykaa.com/', 'MRP', '% off', 'Add to cart', 'rating', 'widget_html'):
            self.assertNotIn(forbidden, body.replace(html.escape(FIRST_URL), ''))
        self.assertEqual(len(re.findall(r'<img[^>]+src="https?://', body)), 0)

    def test_invalid_widget_data_reports_errors_and_publishes_nothing(self):
        page, problems = self.build([self.record(url=FIRST_URL.replace('affiliate.nykaa.com', 'evil.example'))])
        self.assertTrue(problems)
        self.assertEqual(page['_body'].count('<iframe'), 0)


if __name__ == '__main__':
    unittest.main()
