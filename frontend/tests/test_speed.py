"""Page weight: each watch card's illustration is a small immutable SVG file, not ~5.9 KB of inline markup, and every reference resolves."""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class CardArtFiles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.hub = (ROOT / "dist" / "watches" / "index.html").read_text(encoding="utf-8")

    def test_cards_use_image_files_not_inline_drawings(self):
        cards = re.findall(r"<article class=\"watch-card\".*?</article>", self.hub, re.S)
        self.assertGreaterEqual(len(cards), 100)
        for card in cards:
            self.assertNotIn('class="dial-art" viewBox', card)
            self.assertRegex(card, r'<img class="dial-art" src="/assets/art/[0-9a-f]{12}\.svg" alt="" width="140" height="150" loading="lazy" decoding="async">')

    def test_every_referenced_art_file_exists_and_is_a_standalone_svg(self):
        names = set(re.findall(r'/assets/art/([0-9a-f]{12})\.svg', self.hub))
        self.assertTrue(names)
        for name in names:
            text = (ROOT / "dist" / "assets" / "art" / f"{name}.svg").read_text(encoding="utf-8")
            self.assertTrue(text.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 20 140 150"'))
            self.assertNotIn("class=", text[:80])
            self.assertEqual(len(re.findall(r'id="[a-z]00000000"', text)), len(set(re.findall(r'id="[a-z]00000000"', text))))   # ids unique inside the file

    def test_art_files_are_cached_for_a_year(self):
        headers = (ROOT / "dist" / "_headers").read_text(encoding="utf-8")
        self.assertIn("/assets/*\n  Cache-Control: public, max-age=31536000, immutable", headers)

    def test_the_css_sizes_the_image_like_the_old_inline_drawing(self):
        css = (ROOT / "src" / "css" / "components" / "watch-luxe.css").read_text(encoding="utf-8")
        self.assertIn("watch-tile img.dial-art", css)
        self.assertIn("watch-tile svg.dial-art", css)   # the product page still draws it inline

    def test_hub_is_much_lighter_than_it_was(self):
        self.assertLess(len(self.hub.encode("utf-8")), 800_000)   # was about 1.26 MB with inline drawings
        self.assertLess(self.hub.count("<svg"), 400)


if __name__ == "__main__":
    unittest.main()
