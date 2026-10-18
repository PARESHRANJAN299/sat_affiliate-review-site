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

    def test_production_collection_and_order(self):
        data = fashion.read_widgets(ROOT / 'src')
        collections, problems = fashion.validate_collections(data)
        self.assertEqual(problems, [])
        search = next(c for c in collections if c['id'] == 'kurta-sets-search')
        self.assertEqual(search['title'], 'Search results for Women’s kurtas set')
        self.assertEqual(len(search['suggestions']), 6)
        items, _ = fashion.widgets(ROOT / 'src')
        self.assertEqual([i['product_id'] for i in items if i.get('collection') == 'kurta-sets-search'], ['27421822', '21706664'])
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

    def test_rail_scales_to_many_widgets(self):
        many = [self.record(str(1000 + n), FIRST_URL.replace('28560370', str(1000 + n))) for n in range(50)]
        page, problems = self.build(many)
        self.assertEqual(problems, [])
        self.assertEqual(page['_body'].count('<iframe'), 50)
        self.assertEqual(page['_body'].count('loading="lazy" style="height:360px'), 50)
        self.assertEqual(page['js'], ['fashion-widgets'])

    def build_with_collection(self, widgets, collections=(COLLECTION,)):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        src = Path(directory.name)
        (src / 'fashion').mkdir()
        (src / 'fashion/catalog.json').write_text(json.dumps({'approved_image_hosts': [], 'approved_affiliate_hosts': [], 'products': []}))
        (src / 'fashion/widgets.json').write_text(json.dumps(base(widgets, list(collections))))
        return fashion.page(src, lambda *args: '')

    def test_collection_gets_its_own_titled_rail_with_suggestions(self):
        second = self.record('27421822', FIRST_URL.replace('28560370', '27421822'), collection='kurta-sets-search')
        page, problems = self.build_with_collection([self.record(), second])
        body = page['_body']
        self.assertEqual(problems, [])
        self.assertEqual(body.count('data-rail-group'), 2)
        self.assertEqual(body.count('data-widget-rail'), 2)
        self.assertEqual(body.count('data-rail-controls'), 2)
        self.assertIn('<h3>Search results for Women’s kurtas set</h3>', body)
        self.assertIn('Suggestions:', body)
        self.assertIn('Pure cotton kurtas set for women', body)
        self.assertEqual(body.count('class="nykaa-sep"'), 1)
        self.assertEqual(body.count(fashion.WIDGET_AFFILIATE_NOTE), 1)
        self.assertEqual(len(set(re.findall(r'id="(pick-\d+)"', body))), 2)
        first_group, second_group = body.split('data-rail-group')[1:3]
        self.assertIn('pick-28560370', first_group)
        self.assertIn('pick-27421822', second_group)
        self.assertNotIn('<h3>', first_group)

    def test_collection_without_widgets_is_not_shown_and_all_grouped_still_shows_note(self):
        page, _ = self.build_with_collection([self.record()])
        self.assertNotIn('<h3>', page['_body'])
        only = self.record(collection='kurta-sets-search')
        page, _ = self.build_with_collection([only])
        self.assertEqual(page['_body'].count('data-rail-group'), 1)
        self.assertEqual(page['_body'].count(fashion.WIDGET_AFFILIATE_NOTE), 1)
        self.assertIn('<h3>Search results', page['_body'])

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
