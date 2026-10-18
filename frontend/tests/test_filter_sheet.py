"""The /watches/ filter experience on phones: markup, labelled sections, openers, dialog fallback, CSS and script invariants.
The real-browser checks (positions at 320 to 1280 px, taps, focus, swipe) live in the QA script that drives headless Chrome; these tests keep the
contract it relies on from drifting."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build
import collection
import watches

JS = (ROOT / "src/js/components/collection.js").read_text(encoding="utf-8")
CSS = (ROOT / "src/css/components/watch-sheet.css").read_text(encoding="utf-8")
RAIL = (ROOT / "src/css/components/price-slider.css").read_text(encoding="utf-8")
LUXE = (ROOT / "src/css/components/watch-luxe.css").read_text(encoding="utf-8")


def panel_of(body):
    return re.search(r'<dialog class="collection-filters".*?</dialog>', body, re.S).group(0)


class Sheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)
        cls.body = cls.shop.landing()["_body"]
        cls.panel = panel_of(cls.body)

    def sections(self):
        """[(slug, title, html)]: each section runs to the start of the next (a section holds an inner <section class="pc">, so no lazy </section> match)."""
        chunks = re.split(r'(?=<section class="cf-sec" data-cf-section=)', self.panel)[1:]
        return [(re.search(r'data-cf-section="([a-z-]+)"', c).group(1), re.search(r'cf-sec-t">([^<]+)<', c).group(1), c) for c in chunks]

    def test_rows_sit_under_four_labelled_sections_in_order(self):
        secs = self.sections()
        self.assertEqual([title for _, title, _ in secs], [title for title, _ in self.shop.FILTER_SECTIONS])
        self.assertEqual([title for _, title, _ in secs], ["Shop", "Fit", "Technical", "Style"])
        by = {title: re.findall(r'data-fgroup="([a-z]+)"', inner) for _, title, inner in secs}
        self.assertEqual(by["Shop"], ["budget", "brand", "gender"])
        self.assertEqual(by["Fit"], [k for k in ("dial", "strapmat", "dialcolour") if k in by["Fit"]])
        self.assertGreaterEqual(len(by["Fit"]), 2)
        self.assertEqual(by["Technical"][:3], [k for k in ("movement", "water", "display") if k in by["Technical"]])
        self.assertEqual(by["Style"][0], "style")                                            # Style first, then every remaining group
        every = [k for _, _, inner in secs for k in re.findall(r'data-fgroup="([a-z]+)"', inner)]
        self.assertEqual(len(every), len(set(every)))                                        # no row is drawn twice
        self.assertEqual(every, re.findall(r'data-fgroup="([a-z]+)"', self.panel))           # and none sits outside a section

    def test_a_group_with_no_data_is_never_drawn(self):
        self.assertNotIn('data-fgroup="occasion"', self.panel)                              # no watch has approved occasion tags
        for tag in ("Office", "Formal", "Everyday"):
            self.assertNotIn(f'<span>{tag}</span>', self.panel)

    def test_budget_rail_and_collections_strip_sit_in_the_shop_section(self):
        shop = self.sections()[0][2]
        self.assertLess(shop.index("data-price-slider"), shop.index('class="pc"'))           # the strip is below the rail
        self.assertLess(shop.index('class="pc"'), shop.index('data-fgroup="brand"'))
        self.assertIn("Popular watch collections", shop)

    def test_sheet_has_all_its_parts(self):
        for hook in ("data-cf-head", "data-cf-body", "data-cf-active", "data-cf-quick", "data-cf-zero", "data-cf-foot", "data-cf-undo", "data-cf-count", "data-apply-label",
                     'class="linklike cf-reset" data-filter-clear', 'aria-label="Close filters"', 'class="cf-grab"'):
            self.assertIn(hook, self.panel)
        self.assertIn("matches</span>", self.panel)                                          # live "N matches" in the header
        self.assertIn(">Clear one filter<", self.panel)
        self.assertLess(self.panel.index("data-cf-head"), self.panel.index("data-cf-body"))
        self.assertLess(self.panel.index("data-cf-body"), self.panel.index("data-cf-foot"))  # header, scrolling body, footer: footer is last

    def test_every_opener_is_a_dialog_button_with_a_target(self):
        openers = re.findall(r'<button type="button"([^>]*data-filter-open[^>]*)>', self.body)
        self.assertGreaterEqual(len(openers), 2)
        jumps = []
        for attrs in openers:
            self.assertIn('aria-haspopup="dialog"', attrs)
            m = re.search(r'data-jump="([a-z]+)"', attrs)
            if m:
                jumps.append(m.group(1))
        self.assertEqual(sum(1 for a in openers if "data-jump" not in a), 1)                 # exactly one Filter button above the grid
        for jump in jumps:                                                                   # a quick tile always lands on something that exists
            target = {"budget": "data-price-slider", "more": 'data-fgroup="dial"'}.get(jump, f'data-fgroup="{jump}"')
            self.assertIn(target, self.panel, jump)
        self.assertIn("JUMPS = { more: 'dial' }", JS)

    def test_bar_above_the_grid_has_filter_then_sort_after_the_heading(self):
        bar = re.search(r'<header class="collection-head sel-head">.*?</header>', self.body, re.S).group(0)
        self.assertLess(bar.index("<h2"), bar.index("collection-filter-open"))
        self.assertLess(bar.index("collection-filter-open"), bar.index("collection-sort"))   # Filter and Sort side by side, Filter first
        self.assertIn("data-filter-badge", bar)
        self.assertIn("data-collection-count", bar)

    def test_water_resistance_has_a_conservative_info_sheet(self):
        info = self.panel.split('data-info="water"', 1)[1].lower()                          # the layers are the last children of the dialog
        self.assertIn("water-resistant", info)
        self.assertIn("seller", info)
        self.assertNotIn("waterproof", info)
        self.assertIn('data-info-open="water"', self.panel)
        self.assertIn('aria-label="What does water resistance mean?"', self.panel)

    def test_no_waterproof_and_no_commerce_words_anywhere_in_the_sheet(self):
        sources = {"sheet markup": self.panel, "collection.py": (ROOT / "collection.py").read_text(encoding="utf-8"), "script": JS, "css": CSS, "rail css": RAIL,
                   "FILTER_INFO": repr(self.shop.FILTER_INFO), "FILTER_SECTIONS": repr(self.shop.FILTER_SECTIONS)}
        for name, text in sources.items():
            self.assertNotIn("waterproof", text.lower(), name)
        text = re.sub(r"<[^>]+>", " ", self.panel).lower()
        for pattern in (r"m\.r\.p", r"% off", r"discount", r"\bstars?\b", r"out of 5", r"\bcustomer", r"\breview", r"\bemi\b", r"\bbought\b", r"\boffers?\b", r"\bdeals?\b", r"\bsale\b", r"\bcheck price\b"):
            self.assertIsNone(re.search(pattern, text), pattern)
        self.assertNotIn("₹", re.sub(r"under ₹[\d,]+|₹[\d,]+k?|₹[\d,]+ and above", "", text))   # only band names, never an amount of its own

    def test_collections_strip_is_compact_links(self):
        self.assertRegex(CSS, r"\.pc-list \.card-sub, [^{]*\.pc-list \.card-go \{ display: none; \}")
        self.assertRegex(CSS, r"\.pc-list li \.card[^{]*\{[^}]*min-height: 44px")
        self.assertNotIn("width: 250px", LUXE)                                               # the large 250 px cards are gone
        self.assertEqual(len(re.findall(r'class="card card-secondary col-card"', self.panel)), len(self.shop.menu_discovery()))

    def test_the_second_dialog_is_gone(self):
        self.assertNotIn("collection-sub", CSS + LUXE + JS)
        self.assertNotIn("createElement('dialog')", JS)                                      # sub-sheets are layers inside the one dialog
        self.assertIn("cf-sub", JS)
        self.assertIn("panel.appendChild(layer)", JS)


class ScriptContract(unittest.TestCase):
    def test_dialog_fallback_hook(self):
        self.assertIn("typeof panel.showModal === 'function'", JS)
        self.assertRegex(JS, r"try \{ panel\.showModal\(\); native = true; \} catch \(e\) \{ native = false; \}")
        self.assertEqual(JS.count("panel.showModal()"), 1)                                   # never called outside the try
        for hook in ("is-fallback", "cf-backdrop", "aria-modal", "setAttribute('open', '')", "typeof panel.close !== 'function'"):
            self.assertIn(hook, JS)
        self.assertIn(".is-fallback", CSS)
        self.assertIn(".cf-backdrop", CSS)

    def test_open_close_contract(self):
        for hook in ("goBack", "'cancel'", "event.key === 'Escape'", "Date.now() - state.openedAt", "pageshow", "event.persisted", "back.focus({ preventScroll: true })",
                     "panel.focus({ preventScroll: true })", "reduce.matches", "lockPage", "unlockPage", "--cf-sbw", "setInert", "closeLayer", "openLayer"):
            self.assertIn(hook, JS, hook)
        self.assertIn("{ passive: true }", JS)                                               # swipe listeners are passive
        for ev in ("touchstart", "touchmove", "touchend", "touchcancel"):
            self.assertIn(f"'{ev}'", JS)

    def test_option_counts_are_live_and_zero_options_are_switched_off(self):
        for hook in ("function refreshOptions", "box.disabled = dead", "No watch matches your other choices", "label.classList.toggle('is-on'", "No matches", "Clear one filter",
                     "function quickRefine", "Active selections", "Quick refine", "function sheetState"):
            self.assertIn(hook, JS, hook)
        self.assertIn("if (store) refreshOptions(st);", JS)                                  # store-only: other categories keep their own counts
        self.assertIn("if (store) sheetState(", JS)

    def test_script_is_data_driven(self):
        for word in ("Shop", "Technical", "Titan", "Casio", "Fossil", "waterproof"):
            self.assertNotIn(f"'{word}'", JS)                                                # no section name or brand is hard-coded
        self.assertNotRegex(JS, r"['\"]under-")                                              # no price band is hard-coded

    def test_existing_hooks_survive(self):
        for hook in ("tile.target === '_blank'", "sat-saved-watches", "presetGender", "presetFrom", "premium.label", "data-style-toggle", "data-brand-tile", "dataset.sizes"):
            self.assertIn(hook, JS, hook)


class Css(unittest.TestCase):
    def rule(self, selector):
        m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
        self.assertIsNotNone(m, selector)
        return m.group(1)

    def test_sheet_is_attached_to_the_bottom_at_most_640_wide(self):
        rule = self.rule(".watch-store .collection .collection-filters[open]")
        for part in ("position: fixed", "inset: auto 0 0 0", "width: 100%", "max-width: 640px", "margin: 0 auto", "display: flex", "flex-direction: column", "overflow: hidden", "overscroll-behavior: contain"):
            self.assertIn(part, rule)
        self.assertRegex(rule, r"max-height: 88vh; height: min\(88dvh, 760px\); max-height: 88dvh")   # vh first, dvh after: dvh wins where supported
        self.assertNotIn("100vw", rule)

    def test_footer_clears_the_home_indicator(self):
        self.assertRegex(self.rule(".watch-store .collection .cf-foot"), r"padding: 12px 20px calc\(14px \+ env\(safe-area-inset-bottom, 0px\)\)")
        self.assertIn("env(safe-area-inset-bottom, 0px)", self.rule(".sub-foot"))

    def test_only_the_body_scrolls_and_never_sideways(self):
        rule = self.rule(".watch-store .collection .cf-body")
        for part in ("overflow-x: hidden", "overflow-y: auto", "overscroll-behavior: contain", "min-height: 0"):
            self.assertIn(part, rule)
        self.assertIn("overscroll-behavior: contain", self.rule(".sub-body"))
        self.assertIn("html.collection-modal-open { overflow: hidden; padding-right: var(--cf-sbw, 0px)", CSS)

    def test_motion_is_short_and_respects_reduced_motion(self):
        self.assertRegex(self.rule(".watch-store .collection .collection-filters[open]"), r"animation: cf-sheet-in \.24s cubic-bezier")
        self.assertIn("cf-fade-in .24s ease-out", CSS)
        self.assertRegex(CSS, r"@keyframes cf-sheet-in \{ from \{ transform: translate3d\(0, 28px, 0\); opacity: 0; \}")   # transform and opacity only
        tail = CSS[CSS.index("@media (prefers-reduced-motion: reduce)"):]
        for name in ("collection-filters[open]", "::backdrop", ".cf-sub", ".cf-info-card", ".cf-backdrop"):
            self.assertIn(name, tail)
        self.assertIn("animation: none", tail)

    def test_tap_targets_are_44px_and_double_tap_zoom_is_off(self):
        self.assertIn("min-height: 44px", self.rule(".watch-store .collection .fopt"))
        self.assertIn("min-height: 60px", self.rule(".watch-store .collection .fg-toggle"))
        self.assertIn("width: 44px; height: 44px", self.rule(".watch-store .collection .cf-x"))
        self.assertIn("min-height: 44px", self.rule(".watch-store .collection .cf-reset"))
        self.assertIn("min-height: 44px", self.rule(".sub-back"))
        self.assertIn("min-height: 44px", self.rule(".sub-card"))
        self.assertIn("min-height: 44px", self.rule(".watch-store .collection .collection-filter-open, .watch-store .collection .collection-sort"))
        self.assertGreaterEqual(int(re.search(r"\.sr-step \{[^}]*min-height: (\d+)px", RAIL).group(1)), 44)
        self.assertGreaterEqual(CSS.count("touch-action: manipulation"), 10)
        self.assertIn("touch-action: none", self.rule(".watch-store .collection .cf-head"))   # the header is the swipe handle

    def test_rail_labels_are_legible(self):
        self.assertRegex(RAIL, r"\.sr-step span \{ font: 600 \.66rem")                       # 10.5 px
        self.assertRegex(RAIL, r"@media \(max-width: 359px\) \{ \.sr-step span \{ font-size: \.625rem")   # never below 10 px
        self.assertIn("var(--arrow, 0px)", RAIL)                                             # the tooltip arrow follows the marker when the tip is held inside the sheet

    def test_drawer_from_1000px_keeps_working(self):
        drawer = CSS[CSS.index("@media (min-width: 1000px)"):]
        for part in ("inset: 0 0 0 auto", "width: min(440px, 100vw)", "border-radius: 26px 0 0 26px", "cf-drawer-in", "cf-drawer-out"):
            self.assertIn(part, drawer)

    def test_old_filter_rules_are_not_left_behind_in_watch_luxe(self):
        for gone in (".collection-filters", ".cf-head", ".fopt", ".fg-toggle", ".sub-card", "lx-sheet", ".sel-head"):
            self.assertNotIn(gone, LUXE, gone)
        self.assertIn(".pc-list li > .card", LUXE)                                           # the shared card-fill rule stays

    def test_page_includes_the_sheet_stylesheet_after_watch_luxe(self):
        meta = watches.Watches(build.SRC, build.CONFIG).landing()
        self.assertEqual(meta["css"][-2:], ["watch-luxe", "watch-sheet"])


class RenderStore(unittest.TestCase):
    GROUPS = [{"key": "brand", "title": "Brand", "checked": [], "items": [("a", "Alpha", 3), ("b", "Beta", 2)]},
              {"key": "movement", "title": "Movement", "checked": [], "items": [("q", "Quartz", 4), ("m", "Mech", 1)]},
              {"key": "water", "title": "Water", "checked": [], "items": [("w", "30 m", 2), ("x", "50 m", 3)], "info": {"link": "What?", "title": "Water, plainly", "paragraphs": ["One.", "Two."]}},
              {"key": "extra", "title": "Extra", "checked": [], "items": [("e", "E", 1), ("f", "F", 1)]},
              {"key": "empty", "title": "Empty", "checked": [], "items": [("z", "Z", 0)]}]

    def render(self, **kw):
        return collection.render_store(['<article class="watch-card"></article>'] * 3, self.GROUPS, uid="t", title="T", noun="watch", plural="watches", **kw)

    def test_sections_order_groups_and_catch_the_rest_in_the_last(self):
        html = self.render(sections=[("One", ["movement", "brand"]), ("Two", ["water"]), ("Empty section", ["nothing"])])
        titles = re.findall(r'cf-sec-t">([^<]+)<', html)
        self.assertEqual(titles, ["One", "Two"])                                              # a section with no group is not drawn
        one, two = re.findall(r'<section class="cf-sec".*?</section>', html, re.S)[:2]
        self.assertEqual(re.findall(r'data-fgroup="(\w+)"', one), ["movement", "brand"])
        self.assertEqual(re.findall(r'data-fgroup="(\w+)"', two), ["water", "extra"])         # the leftover group joins the last drawn section
        self.assertNotIn('data-fgroup="empty"', html)                                         # a group with no live option is not drawn

    def test_slots_go_before_their_group_and_orphans_stay_at_the_top(self):
        html = self.render(sections=[("One", ["brand"])], slots={"brand": '<i id="rail"></i>', "gone": '<i id="orphan"></i>'})
        self.assertLess(html.index('id="rail"'), html.index('data-fgroup="brand"'))
        self.assertLess(html.index('id="orphan"'), html.index('class="cf-sec"'))

    def test_info_layer_only_for_groups_that_carry_it(self):
        html = self.render(sections=[("One", ["water"])])
        self.assertEqual(html.count('class="cf-info"'), 1)
        self.assertEqual(html.count("data-info-open="), 1)
        self.assertIn("Water, plainly", html)

    def test_without_sections_the_rows_stay_flat(self):
        html = self.render()
        self.assertNotIn("cf-sec-t", html)
        self.assertEqual(re.findall(r'data-fgroup="(\w+)"', html), ["brand", "movement", "water", "extra"])

    def test_other_categories_are_untouched(self):
        html = collection.render([], [{"key": "k", "title": "K", "items": [("a", "A", 1)]}], uid="u", title="U")
        self.assertNotIn("cf-body", html)
        self.assertIn("data-filter-panel", html)
        self.assertNotIn("data-store", html)


class Polish(unittest.TestCase):
    """The tidy-up pass: copy that stays inside what the listings say, one label for resetting, one live region, quiet first screen."""
    @classmethod
    def setUpClass(cls):
        cls.shop = watches.Watches(build.SRC, build.CONFIG)
        cls.panel = panel_of(cls.shop.landing()["_body"])

    def test_one_reset_label_and_no_second_clear_in_the_footer(self):
        self.assertIn(">Reset all</button>", self.panel)
        foot = self.panel[self.panel.index("data-cf-foot"):]
        self.assertNotIn("cf-clear", foot.split("</div>", 1)[0])
        self.assertNotIn(">Clear<", self.panel)
        self.assertIn("'Reset all'", JS)                                                     # the Active selections link says the same

    def test_one_live_region_while_the_sheet_is_open(self):
        self.assertRegex(self.panel, r'<span class="cf-count" data-cf-count>')               # no role=status of its own
        self.assertEqual(self.panel.count('role="status"'), 0)
        self.assertIn("announce(n + (n === 1 ? ' match' : ' matches'))", JS)                 # the one polite region says the count once, after the last tap

    def test_info_button_names_its_subject_and_the_copy_matches_the_listings(self):
        self.assertRegex(self.panel, r'class="cf-info-open" data-info-open="water" aria-haspopup="dialog" aria-label="What does water resistance mean\?"')
        text = " ".join(self.shop.FILTER_INFO["water"]["paragraphs"]).lower()
        self.assertNotIn("maker", text)                                                      # no claim about who sets the rating: it is the seller's listing
        self.assertIn("seller's listing", text)

    def test_no_invented_case_size_line(self):
        self.assertNotIn("Common sizes", JS)
        self.assertNotIn("everyday wear", JS + CSS)

    def test_budget_rail_holds_no_space_for_a_tooltip_in_the_sheet(self):
        self.assertRegex(CSS, r"\.price-bands \.sr-wrap \{ margin: 0 -8px; padding: 2px 0 2px; \}")
        self.assertRegex(CSS, r"\.sr-tip \{ display: none; \}")
        self.assertIn("data-price-help", self.panel)                                         # the head row still says the chosen band

    def test_rail_labels_are_thinned_by_measuring_not_by_count(self):
        for hook in ("function thinLabels", "is-thin", "must[0] = 1", "must[steps.length - 1] = 1", "aria-pressed') === 'true') must[i] = 1", "addEventListener('resize'"):
            self.assertIn(hook, JS, hook)
        self.assertRegex(CSS, r"\.sr-step span\.is-thin \{[^}]*clip: rect")                  # hidden visually, still read out

    def test_quick_refine_is_tidy(self):
        for hook in ("one chip per idea", "Math.abs(k.n - pick.n) <= 2", "pick.group + ': ' + pick.label", "['budget', 'brand', 'gender']"):
            self.assertIn(hook, JS, hook)
        self.assertRegex(CSS, r"\.watch-store \.collection \.cf-q \{[^}]*min-height: 44px[^}]*font: 600 \.84rem")
        self.assertIn(".cf-active:not([hidden]) + .cf-quick .cf-qrow", CSS)                  # one swipeable row once something is chosen

    def test_empty_options_sort_after_live_ones(self):
        self.assertIn("is-empty') ? 1 : 0", JS)
        self.assertIn("a._at - b._at", JS)                                                   # live options keep their order

    def test_jump_scrolls_to_the_section_title(self):
        self.assertIn("var anchor = (target.classList.contains('price-slider') || firstRow) ? sec : target;", JS)

    def test_short_and_narrow_screens_are_handled(self):
        self.assertIn("@media (max-width: 359px)", CSS)
        self.assertIn("@media (max-height: 720px)", CSS)
        tail = CSS[CSS.index("@media (max-height: 480px)"):]
        for part in ("height: 100dvh", ".cf-grab { display: none; }", ".cf-quick { display: none; }"):
            self.assertIn(part, tail)

    def test_collections_strip_wraps_in_the_drawer_and_fades_on_phones(self):
        drawer = CSS[CSS.index("@media (min-width: 1000px)"):]
        self.assertRegex(drawer, r"\.pc-list \{ flex-wrap: wrap; overflow: visible;")
        self.assertRegex(CSS, r"\.pc-list \{[^}]*mask-image: linear-gradient")


if __name__ == "__main__":
    unittest.main()
