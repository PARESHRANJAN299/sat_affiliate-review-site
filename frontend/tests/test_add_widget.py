"""The add_widget helper: reads pasted iframe snippets, keeps only the src URL, and writes nothing unless everything validates."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import add_widget
import fashion


def snippet(pid, ad='6ad4aaaa', affiliate='PARESHRA-445235', style='height: 360px; width: 280px; overflow:hidden;'):
    url = (f'https://affiliate.nykaa.com/v2/get_product_widget?ad_id={ad}&amp;add_resources=True&amp;affiliate_id={affiliate}&amp;product_id={pid}&amp;store=nykaa_fashion'
           '&amp;text_color=000000&amp;theme_variation=TEXT_AND_IMAGE&amp;theme=affiliate&amp;aff_link_type=affiliate%3Anap_dashboard%3Aproduct&amp;hlp=hlpa')
    return f'<iframe src="{url}" style="{style}" frameborder="0"></iframe>'


class AddWidgetTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'widgets.json'
        shutil.copy(ROOT / 'src/fashion/widgets.json', self.path)
        self.before = json.loads(self.path.read_text())

    def widgets(self):
        return json.loads(self.path.read_text())['widgets']

    def test_adds_many_snippets_in_order_and_decodes_entities(self):
        added, skipped, problems = add_widget.add(snippet(11111111) + ',\n' + snippet(22222222), path=self.path)
        self.assertEqual((added, skipped, problems), (['11111111', '22222222'], [], []))
        items = self.widgets()
        self.assertEqual([w['product_id'] for w in items[-2:]], ['11111111', '22222222'])
        self.assertNotIn('&amp;', items[-1]['widget_url'])
        self.assertIn('affiliate_id=PARESHRA-445235&product_id=22222222&store=nykaa_fashion', items[-1]['widget_url'])
        self.assertEqual((items[-1]['category'], items[-1]['active'], items[-1]['featured']), ('womens-kurtas', True, False))
        self.assertEqual(fashion.validate_widgets(json.loads(self.path.read_text()))[1], [])

    def test_bare_urls_and_size_from_style(self):
        url = add_widget.extract(snippet(33333333))[0]
        added, _, _ = add_widget.add(url + '\n', path=self.path)
        self.assertEqual(added, ['33333333'])
        self.assertEqual((self.widgets()[-1]['width'], self.widgets()[-1]['height']), (280, 360))
        add_widget.add(snippet(44444444, style='height: 400px; width: 300px; overflow:hidden;'), path=self.path)
        self.assertEqual((self.widgets()[-1]['width'], self.widgets()[-1]['height']), (300, 400))

    def test_existing_products_are_skipped_not_duplicated(self):
        add_widget.add(snippet(55555555), path=self.path)
        count = len(self.widgets())
        added, skipped, problems = add_widget.add(snippet(55555555), path=self.path)
        self.assertEqual((added, skipped, problems), ([], ['55555555'], []))
        self.assertEqual(len(self.widgets()), count)

    def test_invalid_input_writes_nothing(self):
        before = self.path.read_text()
        for bad in (snippet(66666666, affiliate='SOMEONE-ELSE'), 'no widget here',
                    '<iframe src="https://affiliate.nykaa.com/v2/other?affiliate_id=PARESHRA-445235&product_id=1&store=nykaa_fashion"></iframe>',
                    '<iframe src="https://affiliate.nykaa.com/v2/get_product_widget?affiliate_id=PARESHRA-445235&store=nykaa_fashion"></iframe>'):
            added, _, problems = add_widget.add(bad, path=self.path)
            self.assertEqual(added, [], bad[:40])
            self.assertTrue(problems, bad[:40])
            self.assertEqual(self.path.read_text(), before)

    def test_one_bad_record_blocks_the_whole_batch(self):
        before = self.path.read_text()
        added, _, problems = add_widget.add(snippet(77777777) + snippet(88888888, affiliate='SOMEONE-ELSE'), path=self.path)
        self.assertEqual(added, [])
        self.assertTrue(problems)
        self.assertEqual(self.path.read_text(), before)

    def test_audience_is_recorded_only_when_given(self):
        add_widget.add(snippet(31111111), category='westernwear', path=self.path, audience='men')
        add_widget.add(snippet(32222222), category='westernwear', path=self.path)
        items = {w['product_id']: w for w in self.widgets()}
        self.assertEqual(items['31111111']['audience'], 'men')
        self.assertNotIn('audience', items['32222222'])
        self.assertEqual(fashion.validate_widgets(json.loads(self.path.read_text()))[1], [])

    def test_set_audience_marks_listed_products_and_rejects_unknown_ids(self):
        add_widget.add(snippet(41111111) + snippet(42222222) + snippet(43333333), category='westernwear', path=self.path)
        changed, unknown = add_widget.set_audience(['41111111', ' 43333333'], 'men', self.path)
        self.assertEqual((sorted(changed), unknown), (['41111111', '43333333'], []))
        items = {w['product_id']: w for w in self.widgets()}
        self.assertEqual([items[i].get('audience') for i in ('41111111', '42222222', '43333333')], ['men', None, 'men'])
        before = self.path.read_text()
        self.assertEqual(add_widget.set_audience(['42222222', '99999999'], 'men', self.path), ([], ['99999999']))
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(add_widget.set_audience(['41111111'], 'men', self.path)[0], [])  # already men: nothing to change
        self.assertEqual(fashion.validate_widgets(json.loads(self.path.read_text()))[1], [])

    def test_brand_is_required_for_footwear_and_can_be_set_later(self):
        before = self.path.read_text()
        added, _, problems = add_widget.add(snippet(61111111), category='footwear', path=self.path, audience='men')
        self.assertEqual(added, [])
        self.assertTrue(problems)
        self.assertEqual(self.path.read_text(), before)
        added, _, problems = add_widget.add(snippet(61111111), category='footwear', path=self.path, audience='men', brand='nike')
        self.assertEqual((added, problems), (['61111111'], []))
        self.assertEqual(add_widget.add(snippet(62222222), category='footwear', path=self.path, audience='men', brand='adidas')[0], [])
        changed, unknown = add_widget.set_fields(['61111111'], brand='puma', path=self.path)
        self.assertEqual((changed, unknown), (['61111111'], []))
        self.assertEqual({w['product_id']: w.get('brand') for w in self.widgets()}['61111111'], 'puma')
        self.assertTrue(all('brand' not in w for w in self.widgets() if w['category'] != 'footwear'))
        self.assertEqual(add_widget.add(snippet(63333333), category='westernwear', path=self.path, brand='nike')[0], [])  # no options in this category

    def test_front_marks_new_products_featured_and_they_sort_first(self):
        add_widget.add(snippet(71111111), path=self.path)
        add_widget.add(snippet(72222222), path=self.path, front=True)
        items = {w['product_id']: w for w in self.widgets()}
        self.assertTrue(items['72222222']['featured'])
        self.assertFalse(items['71111111']['featured'])
        live = fashion.widgets(self.path.parent.parent)[0] if False else fashion.validate_widgets(json.loads(self.path.read_text()))[0]
        order = [w['product_id'] for w in live if w['category'] == 'womens-kurtas']
        self.assertLess(order.index('72222222'), order.index('71111111'))  # the front card comes before products added earlier

    def test_set_front_moves_an_existing_product_after_the_current_front_cards(self):
        for pid in (81111111, 82222222, 83333333, 84444444):
            add_widget.add(snippet(pid), path=self.path)
        add_widget.set_fields(['82222222'], path=self.path, front=True)
        add_widget.set_fields(['84444444', '81111111'], path=self.path, front=True)
        live = [w['product_id'] for w in fashion.validate_widgets(json.loads(self.path.read_text()))[0] if w['product_id'] in ('81111111', '82222222', '83333333', '84444444')]
        self.assertEqual(live, ['82222222', '84444444', '81111111', '83333333'])  # front cards first, in the order they were sent
        self.assertEqual(add_widget.set_fields(['99999999'], path=self.path, front=True), ([], ['99999999']))

    def test_dry_run_and_unknown_fields_untouched(self):
        before = self.path.read_text()
        added, _, problems = add_widget.add(snippet(99999999), path=self.path, dry_run=True)
        self.assertEqual((added, problems), (['99999999'], []))
        self.assertEqual(self.path.read_text(), before)
        add_widget.add(snippet(99999999), path=self.path)
        after = json.loads(self.path.read_text())
        for key in ('allowed_widget_host', 'allowed_affiliate_id', 'category_pages', 'allowed_product_link_hosts'):
            self.assertEqual(after.get(key), self.before.get(key))


if __name__ == '__main__':
    unittest.main()
