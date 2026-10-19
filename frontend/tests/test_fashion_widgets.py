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
        self.assertTrue({item['category'] for item in items} <= {slug for slug, *_ in fashion.SECTIONS})
        self.assertIn('womens-kurtas', {item['category'] for item in items})
        first = next(item for item in items if item['product_id'] == '28560370')
        self.assertEqual(first['widget_url'], FIRST_URL)
        for item in items:
            self.assertIn('affiliate_id=PARESHRA-445235', item['widget_url'])
            self.assertIn('product_id=' + item['product_id'], item['widget_url'])

    def test_production_widgets_keep_file_order_and_only_nike_uses_a_collection(self):
        data = fashion.read_widgets(ROOT / 'src')
        items, problems = fashion.widgets(ROOT / 'src')
        self.assertEqual(problems, [])
        self.assertTrue(all(w['collection'] == 'nike-shoes' for w in data['widgets'] if 'collection' in w))  # only the Nike list is in use
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
    def source(self, widgets, category_pages=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        src = Path(directory.name)
        (src / 'fashion').mkdir()
        (src / 'fashion/catalog.json').write_text(json.dumps({'approved_image_hosts': [], 'approved_affiliate_hosts': [], 'products': []}))
        if widgets is not None:
            data = base(widgets)
            if category_pages is not None:
                data['category_pages'] = category_pages
            (src / 'fashion/widgets.json').write_text(json.dumps(data))
        return src

    def build(self, widgets, category_pages=None):
        return fashion.page(self.source(widgets, category_pages), lambda *args: '')

    def record(self, product_id='28560370', url=FIRST_URL, **extra):
        return {'id': f'nykaa-{product_id}', 'product_id': product_id, 'category': 'womens-kurtas', 'source': 'nykaa-fashion', 'widget_url': url,
                'width': 280, 'height': 360, 'active': True, 'featured': False, **extra}

    def widget(self, pid, category='womens-kurtas', **extra):
        return self.record(pid, FIRST_URL.replace('28560370', pid), category=category, **extra)

    def panel(self, body, slug):
        """The markup of one category panel (from its section to the next section or the brands block)."""
        start = body.index(f'id="{slug}" data-category-panel')
        ends = [i for i in (body.find('<section class="fashion-section', start + 10), body.find('<section class="fashion-brands', start)) if i != -1]
        return body[start:min(ends)]

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

    def test_a_category_lists_every_widget_in_its_panel_with_no_rail_button_or_extra_page(self):
        many = [self.widget(str(1000 + n)) for n in range(100)]
        pages, problems = fashion.pages(self.source(many), lambda *args: '', 'https://sat.net.in')
        self.assertEqual((problems, [p['url'] for p in pages]), ([], ['/fashion/']))  # no separate page per category
        body = pages[0]['_body']
        kurtas = self.panel(body, 'womens-kurtas')
        self.assertEqual(kurtas.count('<iframe'), 100)  # all of them, not a preview
        self.assertEqual(len(set(re.findall(r'id="(pick-\d+)"', kurtas))), 100)
        self.assertEqual(kurtas.count('loading="lazy" style="height:360px'), 100)
        self.assertIn('data-widget-grid', kurtas)
        for removed in ('data-widget-rail', 'nykaa-explore', 'Explore Kurtis', 'data-rail-controls'):
            self.assertNotIn(removed, body)

    def test_kurta_panel_is_retailer_powered_and_others_stay_empty(self):
        page, _ = self.build([self.record()])
        body = page['_body']
        kurtas = self.panel(body, 'womens-kurtas')
        self.assertIn('THE KURTA EDIT', kurtas)
        self.assertIn('Elegant Indian styles selected for everyday and occasion wear.', kurtas)
        self.assertIn('/images/fashion/models/ivory-banner-1536.jpg', kurtas)
        self.assertNotIn(fashion.EMPTY_NOTE, kurtas)
        self.assertEqual(body.count(fashion.EMPTY_NOTE), len(fashion.SECTIONS) - 1)
        self.assertEqual(body.count('<iframe'), 1)

    def test_each_card_has_a_sat_share_link_and_no_whatsapp_button(self):
        page, _ = self.build([self.record(), self.widget('27826893')])
        body = page['_body']
        self.assertEqual(body.count('class="nykaa-product-shell"'), 2)
        for pid in ('28560370', '27826893'):
            self.assertIn(f'id="pick-{pid}"', body)
            self.assertIn(f'data-url="https://sat.net.in/fashion/#pick-{pid}"', body)
        self.assertEqual(body.count('data-copy-pick'), 2)
        self.assertEqual(body.count('data-share-pick'), 2)
        for absent in ('wa.me', 'WhatsApp', 'nykaa-get'):
            self.assertNotIn(absent, body)

    def test_get_it_on_nykaa_button_renders_with_sponsored_link(self):
        link = 'https://www.nykaafashion.example/p/28560370?aff=1&x=2'
        src = self.source([self.record(affiliate_url=link)])
        data = json.loads((src / 'fashion/widgets.json').read_text())
        data['allowed_product_link_hosts'] = ['www.nykaafashion.example']
        (src / 'fashion/widgets.json').write_text(json.dumps(data))
        body = fashion.page(src, lambda *args: '')[0]['_body']
        self.assertIn('class="nykaa-get"', body)
        self.assertIn('href="https://www.nykaafashion.example/p/28560370?aff=1&amp;x=2" target="_blank" rel="sponsored nofollow noopener"', body)
        self.assertIn('Get it on Nykaa', body)

    def test_audience_toggle_splits_women_and_men_inside_the_category_panel(self):
        widgets = [self.widget('111', 'westernwear'), self.widget('222', 'westernwear', audience='women'), self.widget('333', 'westernwear', audience='men')]
        page, problems = self.build(widgets, [{'category': 'westernwear', 'audience_toggle': True}])
        self.assertEqual(problems, [])
        western = self.panel(page['_body'], 'westernwear')
        self.assertEqual(western.count('data-audience-group'), 1)
        self.assertIn('data-audience-tab="women" aria-current="true">Women <span>2</span>', western)
        self.assertIn('data-audience-tab="men">Men <span>1</span>', western)
        women, men = western.split('data-audience-panel="women"')[1].split('data-audience-panel="men"')
        self.assertEqual((women.count('class="nykaa-product-shell"'), men.count('class="nykaa-product-shell"')), (2, 1))
        self.assertIn('id="pick-333"', men)
        self.assertIn('Women’s Westernwear', western)
        self.assertIn('Men’s Westernwear', western)
        self.assertLess(western.index('data-audience-tab="women"'), western.index('class="nykaa-product-shell"'))  # the toggle sits above every product

    def test_each_category_has_its_own_toggle_with_unique_ids(self):
        widgets = [self.widget('111', 'westernwear'), self.widget('222', 'footwear', audience='men')]
        settings = [{'category': 'westernwear', 'audience_toggle': True}, {'category': 'footwear', 'audience_toggle': True}]
        body = self.build(widgets, settings)[0]['_body']
        self.assertEqual(body.count('data-audience-group'), 2)
        ids = re.findall(r'<section class="nykaa-panel" id="([\w-]+)"', body)
        self.assertEqual(sorted(ids), ['footwear-men', 'footwear-women', 'westernwear-men', 'westernwear-women'])

    def test_a_toggle_opens_on_the_first_audience_that_has_products(self):
        body = self.build([self.widget('111', 'footwear', audience='men')], [{'category': 'footwear', 'audience_toggle': True}])[0]['_body']
        self.assertIn('data-audience-tab="men" aria-current="true">Men <span>1</span>', body)
        self.assertNotIn('data-audience-tab="women" aria-current', body)

    def test_toggle_opens_on_the_audience_with_the_most_products(self):
        settings = [{'category': 'footwear', 'audience_toggle': True}]
        mostly_men = [self.widget(str(n), 'footwear', audience='men') for n in range(5)] + [self.widget('9', 'footwear', audience='women')]
        self.assertIn('data-audience-tab="men" aria-current="true">Men <span>5</span>', self.build(mostly_men, settings)[0]['_body'])
        tie = [self.widget('1', 'footwear', audience='men'), self.widget('2', 'footwear', audience='women')]
        self.assertIn('data-audience-tab="women" aria-current="true"', self.build(tie, settings)[0]['_body'])  # the first tab wins a tie

    def test_empty_audience_shows_a_note_not_fake_products(self):
        body = self.build([self.widget('111', 'westernwear')], [{'category': 'westernwear', 'audience_toggle': True}])[0]['_body']
        men = body.split('data-audience-panel="men"')[1].split('</section>')[0]
        self.assertIn('data-audience-tab="men">Men <span>0</span>', body)
        self.assertNotIn('class="nykaa-product-shell"', men)
        self.assertIn('Men’s picks will appear here once approved Nykaa catalogue items are added.', men)

    def test_no_toggle_without_the_setting(self):
        body = self.build([self.widget('111', 'westernwear'), self.widget('333', 'westernwear', audience='men')])[0]['_body']
        self.assertNotIn('data-audience', body)
        self.assertEqual(body.count('class="nykaa-product-shell"'), 2)

    def test_audience_values_and_settings_are_validated(self):
        self.assertTrue(fashion.validate_widgets(base([{**self.record(), 'audience': 'kids'}]))[1])
        self.assertEqual(fashion.validate_widgets(base([{**self.record(), 'audience': 'men'}]))[1], [])
        for entry in ({'category': 'westernwear', 'audience_toggle': 'yes'}, {'category': 'nope'}, {'category': 'westernwear', 'h1': 'x'}):
            self.assertTrue(fashion.validate_widgets({**base([self.record()]), 'category_pages': [entry]})[1], entry)
        self.assertTrue(fashion.validate_widgets({**base([self.record()]), 'category_pages': [{'category': 'bags'}, {'category': 'bags'}]})[1])
        self.assertTrue(fashion.validate_widgets({**base([self.record()]), 'category_pages': {}})[1])

    def test_production_settings_and_labels(self):
        settings = fashion.category_page_config(ROOT / 'src')
        self.assertEqual(sorted(settings), sorted(slug for slug, *_ in fashion.SECTIONS if slug != 'womens-kurtas'))
        self.assertTrue(all(value.get('audience_toggle') for slug, value in settings.items() if slug != 'footwear'))
        self.assertFalse(settings['footwear'].get('audience_toggle'))  # all Footwear products of a brand sit in one list
        self.assertEqual(sorted(slug for slug, value in settings.items() if value.get('groups')), ['footwear'])  # only Footwear has brand options
        data = fashion.read_widgets(ROOT / 'src')
        western = [w for w in data['widgets'] if w['category'] == 'westernwear']
        self.assertTrue(western)
        self.assertTrue(all(w.get('audience') in ('women', 'men') for w in western))
        for slug, label in {'womens-kurtas': 'THE KURTA EDIT', 'westernwear': 'THE WESTERN EDIT', 'footwear': 'THE FOOTWEAR EDIT', 'indianwear': 'THE INDIAN EDIT',
                            'active-sports': 'THE ACTIVE EDIT', 'bags': 'THE BAG EDIT'}.items():
            self.assertEqual(fashion.EDIT_LABELS[slug], label)

    def test_every_category_is_set_up_the_same_way(self):
        for slug, label in {'indianwear': 'THE INDIAN EDIT', 'active-sports': 'THE ACTIVE EDIT', 'bags': 'THE BAG EDIT', 'footwear': 'THE FOOTWEAR EDIT'}.items():
            with self.subTest(slug=slug):
                src = self.source([self.widget('555', slug, audience='men', **({'brand': 'us-polo'} if slug == 'footwear' else {}))])
                data = json.loads((src / 'fashion/widgets.json').read_text())
                data['category_pages'] = fashion.read_widgets(ROOT / 'src')['category_pages']
                (src / 'fashion/widgets.json').write_text(json.dumps(data))
                pages, problems = fashion.pages(src, lambda *args: '', 'https://sat.net.in')
                self.assertEqual((problems, [p['url'] for p in pages]), ([], ['/fashion/']))
                section = self.panel(pages[0]['_body'], slug)
                self.assertIn(label, section)
                self.assertIn(f'fashion-widget-banner fashion-tint-{slug}', section)
                if slug == 'footwear':
                    self.assertNotIn('data-audience', section)
                else:
                    self.assertIn('data-audience-tab="men" aria-current="true">Men <span>1</span>', section)
                self.assertNotIn('Explore', section)
                self.assertTrue(pages[0]['noindex'])

    GROUPS = [{'id': 'us-polo', 'label': 'U.S. Polo Assn.', 'note': 'Sneakers'}, {'id': 'nike', 'label': 'Nike'}, {'id': 'puma', 'label': 'Puma'},
              {'id': 'indian-affordable', 'label': 'Affordable Indian brands', 'note': 'Campus, Sparx and Bata'}]

    def footwear(self, pid, brand, **extra):
        return self.widget(pid, 'footwear', **{'brand': brand, 'audience': 'men', **extra})

    def test_brand_options_split_a_category_and_work_with_the_women_men_toggle(self):
        widgets = [self.footwear('1', 'us-polo'), self.footwear('2', 'us-polo'), self.footwear('3', 'nike'), self.footwear('4', 'indian-affordable')]
        settings = [{'category': 'footwear', 'audience_toggle': True, 'groups': self.GROUPS}]
        page, problems = self.build(widgets, settings)
        self.assertEqual(problems, [])
        panel = self.panel(page['_body'], 'footwear')
        self.assertEqual(panel.count('data-brand-set'), 1)
        self.assertEqual(re.findall(r'data-brand-tab="([\w-]+)"[^>]*>([^<]+) <span>(\d+)', panel),
                         [('us-polo', 'U.S. Polo Assn.', '2'), ('nike', 'Nike', '1'), ('puma', 'Puma', '0'), ('indian-affordable', 'Affordable Indian brands', '1')])
        self.assertIn('data-brand-tab="us-polo" aria-current="true"', panel)  # opens on the first option with products
        polo = panel.split('data-brand-panel="us-polo"')[1].split('data-brand-panel="nike"')[0]
        self.assertEqual(polo.count('class="nykaa-product-shell"'), 2)
        self.assertIn('id="pick-1"', polo)
        self.assertNotIn('id="pick-3"', polo)
        self.assertIn('data-audience-tab="men" aria-current="true">Men <span>2</span>', polo)
        self.assertIn('Sneakers', polo)
        puma = panel.split('data-brand-panel="puma"')[1].split('data-brand-panel="indian-affordable"')[0]
        self.assertNotIn('nykaa-product-shell', puma)
        self.assertIn('Puma picks will appear here once approved Nykaa catalogue items are added.', puma)
        ids = re.findall(r'<section class="nykaa-panel" id="([\w-]+)"', panel)
        self.assertEqual(len(ids), len(set(ids)))  # each brand has its own Women / Men panel ids

    def test_brand_options_opens_on_the_first_option_that_has_products_and_shows_when_empty(self):
        settings = [{'category': 'footwear', 'groups': self.GROUPS}]
        body = self.build([self.footwear('9', 'puma')], settings)[0]['_body']
        self.assertIn('data-brand-tab="puma" aria-current="true"', body)
        empty = self.build(None, settings)[0]['_body']  # no widgets at all: the options still show, each empty
        self.assertEqual(empty.count('data-brand-tab='), 0)  # settings come from widgets.json, none here
        src = self.source([], settings)
        shown = fashion.page(src, lambda *args: '')[0]['_body']
        footwear = self.panel(shown, 'footwear')
        self.assertEqual(footwear.count('data-brand-tab='), 4)
        self.assertEqual(footwear.count('nykaa-product-shell'), 0)
        self.assertIn(fashion.EMPTY_NOTE, footwear)

    def test_brand_rules(self):
        groups = {'category': 'footwear', 'groups': self.GROUPS}
        data = lambda *w, setting=groups: {**base(list(w)), 'category_pages': [setting]}
        self.assertEqual(fashion.validate_widgets(data(self.footwear('1', 'nike')))[1], [])
        self.assertTrue(fashion.validate_widgets(data(self.widget('1', 'footwear')))[1])               # a grouped category needs a brand
        self.assertTrue(fashion.validate_widgets(data(self.footwear('1', 'adidas')))[1])               # unknown brand option
        self.assertTrue(fashion.validate_widgets({**base([self.widget('1', 'bags', brand='nike')]), 'category_pages': [groups]})[1])  # brand on another category
        for bad in ({'category': 'footwear', 'groups': [self.GROUPS[0]]}, {'category': 'footwear', 'groups': 'x'},
                    {'category': 'footwear', 'groups': [self.GROUPS[0], self.GROUPS[0]]}, {'category': 'footwear', 'groups': [{'id': 'A', 'label': 'x'}, self.GROUPS[1]]},
                    {'category': 'footwear', 'groups': [{'id': 'a', 'label': ''}, self.GROUPS[1]]}, {'category': 'footwear', 'groups': [{**self.GROUPS[0], 'html': '<b>'}, self.GROUPS[1]]}):
            self.assertTrue(fashion.validate_widgets({**base([self.record()]), 'category_pages': [bad]})[1], bad)

    def test_a_brand_option_can_have_its_own_women_men_toggle(self):
        groups = [{**g, 'audience_toggle': g['id'] == 'nike'} for g in self.GROUPS]
        widgets = [self.footwear('1', 'us-polo'), self.footwear('2', 'nike'), self.footwear('3', 'nike', audience='women')]
        page, problems = self.build(widgets, [{'category': 'footwear', 'groups': groups}])
        self.assertEqual(problems, [])
        panel = self.panel(page['_body'], 'footwear')
        nike = panel.split('data-brand-panel="nike"')[1].split('data-brand-panel="puma"')[0]
        polo = panel.split('data-brand-panel="us-polo"')[1].split('data-brand-panel="nike"')[0]
        self.assertIn('data-audience-tab="women" aria-current="true">Women <span>1</span>', nike)  # opens on the first list that has products
        self.assertIn('data-audience-tab="men">Men <span>1</span>', nike)
        self.assertNotIn('data-audience', polo)  # U.S. Polo Assn. stays one list
        self.assertEqual(polo.count('class="nykaa-product-shell"'), 1)
        self.assertTrue(fashion.validate_widgets({**base([self.record()]), 'category_pages': [{'category': 'footwear', 'groups': [{**groups[0], 'audience_toggle': 'yes'}, groups[1]]}]})[1])

    def test_production_nike_has_a_women_men_toggle_and_us_polo_does_not(self):
        groups = {g['id']: g for g in fashion.category_page_config(ROOT / 'src')['footwear']['groups']}
        self.assertTrue(groups['nike']['audience_toggle'])
        self.assertFalse(groups['us-polo']['audience_toggle'])

    def test_nike_products_sit_in_a_titled_search_results_list(self):
        collections = [{'id': 'nike-shoes', 'category': 'footwear', 'title': 'Search results for Nike Shoes', 'suggestions': []}]
        groups = [{**g, 'audience_toggle': g['id'] == 'nike'} for g in self.GROUPS]
        widgets = [self.footwear('1', 'nike', collection='nike-shoes'), self.footwear('2', 'nike', collection='nike-shoes'), self.footwear('3', 'nike'), self.footwear('4', 'us-polo')]
        src = self.source(widgets, [{'category': 'footwear', 'groups': groups}])
        data = json.loads((src / 'fashion/widgets.json').read_text())
        data['collections'] = collections
        (src / 'fashion/widgets.json').write_text(json.dumps(data))
        pages, problems = fashion.pages(src, lambda *args: '', 'https://sat.net.in')
        self.assertEqual(problems, [])
        panel = self.panel(pages[0]['_body'], 'footwear')
        nike = panel.split('data-brand-panel="nike"')[1].split('data-brand-panel="puma"')[0]
        polo = panel.split('data-brand-panel="us-polo"')[1].split('data-brand-panel="nike"')[0]
        self.assertEqual(nike.count('>Search results for Nike Shoes<'), 1)  # one visible heading
        titled = nike.split('>Search results for Nike Shoes<')[1]
        self.assertEqual(titled.count('class="nykaa-product-shell"'), 3)  # the two titled products, then the untitled one after them
        self.assertLess(titled.index('id="pick-2"'), titled.index('id="pick-3"'))
        self.assertNotIn('Search results', polo)
        bad = self.source([self.footwear('1', 'nike', collection='missing')], [{'category': 'footwear', 'groups': groups}])
        self.assertTrue(fashion.validate_widgets(json.loads((bad / 'fashion/widgets.json').read_text()))[1])

    def test_production_nike_list_is_titled(self):
        data = fashion.read_widgets(ROOT / 'src')
        self.assertIn(('nike-shoes', 'Search results for Nike Shoes'), [(c['id'], c['title']) for c in data['collections']])
        nike = [w for w in data['widgets'] if w.get('brand') == 'nike']
        self.assertTrue(nike)
        self.assertTrue(all(w.get('collection') == 'nike-shoes' for w in nike))

    def test_production_footwear_offers_the_four_agreed_options(self):
        groups = fashion.category_page_config(ROOT / 'src')['footwear']['groups']
        self.assertEqual([g['id'] for g in groups], ['us-polo', 'nike', 'puma', 'indian-affordable'])
        self.assertEqual([g['label'] for g in groups], ['U.S. Polo Assn.', 'Nike', 'Puma', 'Affordable Indian brands'])
        self.assertTrue(all(g['id'] not in ('', None) for g in groups))

    def test_disclosure_appears_only_with_widgets(self):
        with_widgets, _ = self.build([self.record()])
        without, _ = self.build(None)
        self.assertEqual(with_widgets['_body'].count(fashion.WIDGET_AFFILIATE_NOTE), 1)
        self.assertIn('data-disclosure="temporary"', with_widgets['_body'])
        self.assertNotIn(fashion.WIDGET_AFFILIATE_NOTE, without['_body'])
        self.assertIn(fashion.EMPTY_NOTE, self.panel(without['_body'], 'womens-kurtas'))

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
