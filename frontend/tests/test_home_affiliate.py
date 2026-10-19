"""Homepage collage: each picture opens an Amazon search for what it shows, through the owner's affiliate link."""
import html
import json
import re
import sys
import unittest
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import build
import watches

ROOT = Path(__file__).resolve().parent.parent
URL = "https://www.amazon.in/s?k=watch&i=watches&linkCode=ll2&tag=pareshsat-21&linkId=d365214107ba31edaa9fc39bb8fa609b&ref_=as_li_ss_tl"


def tiles(markup):
    return re.findall(r'<a class="tile" href="([^"]+)"([^>]*)>\s*<img src="/images/home/([^"]+)"', markup)


class HomeCollageAffiliate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)
        cls.wall = json.loads((build.SRC / "home-wall.json").read_text(encoding="utf-8"))
        cls.saved = build.SHOP[0]

    @classmethod
    def tearDownClass(cls):
        build.SHOP[0] = cls.saved

    def collage(self, shop):
        build.SHOP[0] = shop
        return build.home_collage()

    def test_every_picture_opens_its_own_amazon_search_in_a_new_tab(self):
        base = urllib.parse.parse_qs(urllib.parse.urlsplit(URL).query)
        wall = {t["file"]: t for t in self.wall["tiles"]}
        found = tiles(self.collage(self.shop))
        self.assertTrue(found)
        for href, rest, img in found:
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(html.unescape(href)).query)
            self.assertEqual(q["k"], [wall[img]["search"]], img)                             # what the picture shows
            self.assertEqual(q["i"], [self.wall["indexes"][wall[img]["category"]]], img)     # the matching Amazon category
            for keep in ("tag", "linkCode", "linkId", "ref_"):
                self.assertEqual(q[keep], base[keep], keep)                                  # the owner's tracking parameters are untouched
            self.assertIn('target="_blank"', rest)
            self.assertIn('rel="sponsored nofollow noopener"', rest)
            self.assertIn('data-no-paid-label="1"', rest)
            self.assertFalse(href.startswith("/"))                                           # no on-site page, nothing scrolls

    def test_every_picture_has_its_own_search_words_and_a_known_category(self):
        files = sorted(p.name for p in (build.SRC / "static" / "images" / "home").glob("*.jpg"))
        listed = [t["file"] for t in self.wall["tiles"]]
        self.assertEqual(sorted(listed), files)                                              # no picture is left without a link
        slugs = {c["slug"] for c in build.CATEGORIES}
        for t in self.wall["tiles"]:
            self.assertTrue(t["search"].strip(), t["file"])
            self.assertIn(t["category"], slugs)
            self.assertIn(t["category"], self.wall["indexes"])
        self.assertEqual(len({t["search"] for t in self.wall["tiles"]}), len(self.wall["tiles"]))   # no two pictures share a search

    def test_searches_stay_inside_the_category_the_picture_belongs_to(self):
        wall = {t["file"]: t for t in self.wall["tiles"]}
        by_index = {}
        for href, rest, img in tiles(self.collage(self.shop)):
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(html.unescape(href)).query)
            by_index.setdefault(q["i"][0], set()).add(wall[img]["category"])
        for index, cats in by_index.items():
            self.assertEqual(len(cats), 1, index)                                            # one Amazon category per site category

    def test_site_category_pages_without_affiliate_links(self):
        shop = watches.Watches(build.SRC, build.CONFIG)
        shop.affiliate_active = False
        found = tiles(self.collage(shop))
        self.assertTrue(found)
        for href, rest, img in found:
            self.assertTrue(href.startswith("/"), href)                                      # a plain link to the category page
            self.assertNotIn("_blank", rest)
        self.assertTrue(tiles(self.collage(None)))                                           # and the same when the shop is not loaded

    def test_missing_search_words_fall_back_to_the_category_name(self):
        shop = self.shop
        saved = build.read
        wall = json.loads(json.dumps(self.wall))
        wall["tiles"][0].pop("search")
        build.read = lambda p: json.dumps(wall) if str(p).endswith("home-wall.json") else saved(p)
        try:
            href, rest, img = tiles(self.collage(shop))[0]
        finally:
            build.read = saved
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(html.unescape(href)).query)
        self.assertEqual(q["k"], ["Watches"])

    def test_built_home_page_has_no_visible_paid_tag_on_the_pictures(self):
        page = build.DIST / "index.html"
        if not page.exists():
            self.skipTest("run build.py first")
        text = page.read_text(encoding="utf-8")
        self.assertTrue(tiles(text))
        for href, rest, img in tiles(text):
            self.assertIn("amazon.in/s?", html.unescape(href))
        self.assertEqual(len(re.findall(r'class="tile"[^>]*>(?:(?!</a>).)*</a><small class="paid-link">', text, flags=re.S)), 0)


if __name__ == "__main__":
    unittest.main()


class HomeCategoryTiles(unittest.TestCase):
    """The home 'Shop by Category' strip: five tiles that fit on a phone without sideways scrolling."""

    def test_tiles_are_markup_links_with_arrow(self):
        page = (ROOT / "dist" / "index.html").read_text(encoding="utf-8")
        tiles = re.findall(r'<a class="home-cat" href="([^"]+)"', page)
        self.assertEqual(len(tiles), 5)
        self.assertEqual(page.count('class="home-cat-go"'), 5)

    def test_phone_layout_is_a_grid_not_a_scroller(self):
        css = (ROOT / "src" / "css" / "pages" / "home.css").read_text(encoding="utf-8")
        phone = css[css.index("@media (max-width: 719px)", css.index(".home-cat-strip")):]
        phone = phone[:phone.index("}\n@media")]
        self.assertIn("grid-template-columns: repeat(2", phone)
        self.assertNotIn("overflow-x", phone)
        lux = (ROOT / "src" / "css" / "layout" / "mobile-luxury.css").read_text(encoding="utf-8")
        self.assertNotIn("home-cat-strip", lux)


class TileAffordance(unittest.TestCase):
    """Collage pictures that open Amazon say so: every one carries data-shop (hover label) and the CSS adds an always-visible arrow badge."""

    def test_tiles_carry_the_shop_label_and_css_adds_the_badge(self):
        page = (ROOT / "dist" / "index.html").read_text(encoding="utf-8")
        tiles = re.findall(r'<a class="tile" href="https://www\.amazon\.in/s\?[^"]+"[^>]*>', page)
        self.assertGreater(len(tiles), 50)
        for t in tiles:
            self.assertRegex(t, r'data-label="Shop [a-z][a-z &;]+ on Amazon \u2197" data-go="\u2197"')
            self.assertIn('data-cat="', t)
        css = (ROOT / "src" / "css" / "pages" / "home.css").read_text(encoding="utf-8")
        self.assertIn('a.tile[target="_blank"]::before', css)
        self.assertIn("content: attr(data-label)", css)
        self.assertIn("content: attr(data-go)", css)
