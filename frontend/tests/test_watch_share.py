"""Sharing a watch: a share control on every card and product page, a WhatsApp link that works without JavaScript, the SAT address (never Amazon)."""
import copy
import html
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import unittest
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build
import watches

JS = (ROOT / "src" / "js" / "components" / "watch-share.js").read_text(encoding="utf-8")
CSS = (ROOT / "src" / "css" / "components" / "watch-share.css").read_text(encoding="utf-8")
UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.!~*'()")


def encode_uri_component(text):
    """A hand-written copy of the browser's encodeURIComponent, so the test does not trust the builder's own helper."""
    return "".join(c if c in UNRESERVED else "".join("%%%02X" % b for b in c.encode("utf-8")) for c in text)


class Anchors(HTMLParser):
    """Collects every <a data-share-open> with its attributes and the tags it sits inside."""
    def __init__(self, text):
        super().__init__()
        self.found = []
        self.stack = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "data-share-open" in attrs:
            self.found.append({"attrs": attrs, "inside": [s for s in self.stack]})
        if tag not in ("br", "img", "input", "meta", "link", "path", "circle", "rect", "use"):
            self.stack.append((tag, attrs.get("class", "")))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break


class ShareMarkup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)
        cls.site = build.CONFIG["site_url"].rstrip("/")

    def expected(self, p):
        name = f'{self.shop.brands[p["brand"]]["name"]} {p["model"]}'
        url = f'{self.site}/watches/products/{p["id"]}/'
        return name, url, "https://wa.me/?text=" + encode_uri_component(f"Check this watch on SAT: {name}\n{url}")

    def test_every_card_has_one_share_control_next_to_the_heart(self):
        for p in self.shop.products:
            card = self.shop.card(p)
            found = Anchors(card).found
            self.assertEqual(len(found), 1, p["id"])
            name, url, wa = self.expected(p)
            a = found[0]["attrs"]
            self.assertEqual(a["href"], wa, p["id"])                                  # exactly: https://wa.me/?text= + encodeURIComponent(...)
            self.assertEqual(a["data-share-url"], url)
            self.assertEqual(a["data-share-name"], name)
            self.assertEqual(a["data-share-product"], p["id"])
            self.assertEqual(a["data-share-brand"], p["brand"])
            self.assertEqual(a["aria-label"], f"Share {name}")
            self.assertEqual(a["aria-haspopup"], "dialog")
            self.assertEqual(a["target"], "_blank")
            self.assertIn("noopener", a["rel"])
            self.assertIn("watch-visual", [c.split()[0] for t, c in found[0]["inside"] if c])   # sits in the picture, with the heart
            self.assertIn(f'data-fav="{p["id"]}"', card)                                # the heart is still there
            self.assertEqual(card.count("data-fav="), 1)

    def test_whatsapp_text_decodes_to_the_agreed_message(self):
        p = self.shop.products[0]
        name, url, wa = self.expected(p)
        query = urllib.parse.urlsplit(wa).query
        self.assertTrue(query.startswith("text=Check%20this%20watch%20on%20SAT%3A%20"))
        self.assertIn("%0A", query)                                                      # a real new line between the name and the address
        self.assertEqual(urllib.parse.parse_qs(query)["text"][0], f"Check this watch on SAT: {name}\n{url}")

    def test_quote_and_non_ascii_names_encode_like_encodeuricomponent(self):
        p = copy.deepcopy(self.shop.products[0])
        p["model"] = "Women's Crème & Co (Gold) #1 100%"
        name, url, wa = self.expected(p)
        self.assertEqual(self.shop.share_href(p), wa)
        self.assertIn("%C3%A8", wa)
        self.assertIn("%26", wa)
        self.assertIn("%23", wa)
        self.assertIn("%25", wa)

    def test_shared_address_follows_the_site_config_not_a_hard_coded_domain(self):
        config = copy.deepcopy(build.CONFIG)
        config["site_url"] = "https://example.test/"
        shop = watches.Watches(build.SRC, config)
        p = shop.products[0]
        self.assertEqual(shop.share_url(p), f'https://example.test/watches/products/{p["id"]}/')
        self.assertIn(urllib.parse.quote("https://example.test/watches/products/", safe="-_.!~*'()"), shop.share_href(p))
        self.assertNotIn("sat.net.in", Anchors(shop.card(p)).found[0]["attrs"]["href"])
        self.assertNotIn("sat.net.in", JS)
        self.assertNotIn("sat.net.in", CSS)

    def test_share_markup_never_carries_amazon_prices_or_ratings(self):
        for p in self.shop.products:
            a = Anchors(self.shop.card(p)).found[0]["attrs"]
            text = " ".join(html.unescape(str(v)) for v in a.values()) + " " + urllib.parse.unquote(a["href"])
            low = text.lower()
            for bad in ("amazon", "amzn", "linkcode", "tag=", "/dp/", "₹", "rs.", "m.r.p"):
                self.assertNotIn(bad, low, f'{p["id"]}: {bad}')
            for word in ("rating", "ratings", "review", "reviews", "offer", "offers", "discount", "emi", "bought"):   # whole words (premium is fine)
                self.assertIsNone(re.search(r"\b" + word + r"\b", low), f'{p["id"]}: {word}')
            amazon = ((p.get("merchants") or {}).get("amazon") or {}).get("url")
            if amazon:
                self.assertNotIn(amazon, text)
                self.assertNotIn(urllib.parse.quote(amazon, safe=""), text)

    def test_product_page_has_a_labelled_share_pill_in_the_hero(self):
        for p in self.shop.products:
            meta = self.shop.product_page(p)
            found = Anchors(meta["_body"]).found
            hero = [f for f in found if any("watch-pdp-info" in c.split() for t, c in f["inside"])]
            self.assertEqual(len(hero), 1, p["id"])
            name, url, wa = self.expected(p)
            self.assertEqual(hero[0]["attrs"]["href"], wa)
            self.assertIn("watch-share--label", hero[0]["attrs"]["class"])
            self.assertIn(">Share</span>", meta["_body"])
            self.assertEqual(hero[0]["attrs"]["aria-label"], f"Share {name}")
            self.assertIn("<h1>", meta["_body"])
            self.assertNotIn("data-fav=\"" + p["id"] + "\"", meta["_body"].split("watch-pdp-info")[1].split("</h1>")[0])   # the hero gains no heart

    def test_every_page_with_a_share_control_loads_its_script_and_style(self):
        pages = self.shop.pages()
        with_share = [m for m in pages if "data-share-open" in m["_body"]]
        self.assertGreater(len(with_share), len(self.shop.products))                    # product pages and every collection page
        for meta in with_share:
            self.assertIn("watch-share", meta["js"], meta["url"])
            self.assertIn("watch-share", meta["css"], meta["url"])
            self.assertEqual(meta["js"].count("watch-share"), 1)
        for meta in pages:
            if "data-share-open" not in meta["_body"]:
                self.assertNotIn("watch-share", meta["js"], meta["url"])
        urls = {m["url"] for m in with_share}
        self.assertIn("/watches/", urls)
        self.assertTrue(any(u.startswith("/watches/brands/") for u in urls))
        self.assertTrue(any(u.startswith("/watches/products/") for u in urls))

    def test_existing_scripts_stay_on_those_pages(self):
        pages = {m["url"]: m for m in self.shop.pages()}
        self.assertIn("collection", pages["/watches/"]["js"])
        self.assertIn("watch-tilt", pages["/watches/"]["js"])
        product = next(m for u, m in pages.items() if u.startswith("/watches/products/"))
        self.assertIn("watch-tilt", product["js"])

    def test_hub_affiliate_links_are_untouched(self):
        body = self.shop.landing()["_body"]
        self.assertEqual(body.count("data-no-paid-label"), len(re.findall(r'data-no-paid-label="1"', body)))
        for tag in re.findall(r"<a\b[^>]*>", body):
            if "data-share-open" in tag:
                continue
            if 'target="_blank"' in tag:
                self.assertIn("sponsored", tag)


class ShareScript(unittest.TestCase):
    def test_events_and_payload(self):
        for name in ("product_share_open", "product_share_whatsapp", "product_share_copy", "product_share_more"):
            self.assertIn(name, JS)
        self.assertIn("sat:analytics", JS)
        self.assertIn("product_id", JS)
        self.assertIn("brand", JS)
        self.assertIn("source", JS)
        self.assertRegex(JS, r"window\.dataLayer && typeof window\.dataLayer\.push === 'function'")   # only pushed when the page already has one
        self.assertNotRegex(JS, r"window\.dataLayer\s*=")

    def test_no_third_party_calls_storage_or_personal_data(self):
        for bad in ("fetch(", "XMLHttpRequest", "sendBeacon", "createElement('script')", "localStorage", "sessionStorage", "document.cookie", "userAgent", "navigator.language", "location.search", "linkCode"):
            self.assertNotIn(bad, JS, bad)
        self.assertNotIn("amazon", JS.lower())
        self.assertNotIn("amazon", CSS.lower())

    def test_shares_the_sat_address_from_the_markup(self):
        self.assertIn("data-share-url", JS)
        self.assertIn("navigator.clipboard.writeText(url)", JS)
        self.assertIn("url: item.url", JS)
        self.assertIn("navigator.share", JS)
        self.assertIn("typeof navigator.share !== 'function'", JS)                       # More is hidden unless the browser can share
        self.assertIn("execCommand('copy')", JS)                                         # fallback when the clipboard API is missing
        self.assertIn("Link copied", JS)
        self.assertIn("Share this watch", JS)
        self.assertIn('aria-live="polite"', JS)

    def test_dialog_behaviour(self):
        self.assertIn("showModal", JS)
        self.assertIn("'cancel'", JS)                                                    # Escape
        self.assertIn("event.target === dialog", JS)                                     # a tap on the dimmed area closes
        self.assertIn("back.focus", JS)                                                  # focus returns to the icon
        self.assertIn("prefers-reduced-motion", JS)
        self.assertIn("event.preventDefault()", JS)                                      # the icon never follows its link to WhatsApp or the product

    def test_works_for_cards_added_or_moved_later(self):
        self.assertIn("document.addEventListener('click'", JS)
        self.assertNotRegex(JS, r"querySelectorAll\('\[data-share-open\]'\)\.forEach")

    def test_article_share_script_is_untouched(self):
        old = (ROOT / "src" / "js" / "components" / "share.js").read_text(encoding="utf-8")
        self.assertIn("[data-share]", old)
        self.assertNotIn("data-share-open", old)


class ShareStyle(unittest.TestCase):
    def test_tap_target_and_sheet(self):
        self.assertRegex(CSS, r"\.watch-share \{[^}]*min-width: 44px; min-height: 44px")
        self.assertRegex(CSS, r"\.watch-share--icon \{[^}]*width: 44px; height: 44px")
        self.assertIn("env(safe-area-inset-bottom", CSS)
        self.assertIn("@media (max-width: 640px)", CSS)
        self.assertIn("translateY(100%)", CSS)                                           # slides up from the bottom
        self.assertIn("prefers-reduced-motion: reduce", CSS)
        self.assertIn("::backdrop", CSS)

    def test_never_wider_than_the_screen(self):
        self.assertNotIn("100vw", CSS)
        self.assertIn("max-width: 100%", CSS)
        self.assertIn("box-sizing: border-box", CSS)

    def test_watch_palette(self):
        for colour in ("#a88646", "#2b2c2f", "#fffdf8", "#d8c08a"):
            self.assertIn(colour, CSS)

    def test_a_closed_dialog_stays_hidden(self):
        self.assertNotRegex(CSS, r"\.watch-share-sheet \{[^}]*display: (?!none)")                 # display is only set on [open], so a closed sheet is never drawn


if __name__ == "__main__":
    unittest.main()
