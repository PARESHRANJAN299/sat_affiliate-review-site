# Watches data

Add a watch by creating `src/watches/products/<id>.json`. Nothing else needs editing.

```json
{
  "id": "titan-example-model",
  "brand": "titan",
  "model": "Model name",
  "gender": ["men"],
  "budget": "under-3000",
  "styles": ["classic", "analog", "leather-strap"],
  "dial_style": "White, Roman numerals",
  "strap": "Leather",
  "case_size_mm": 38,
  "water_resistance": "30 m",
  "best_for": "Best Overall",
  "verdict": "One honest line.",
  "paragraphs": ["Short paragraph in plain English."],
  "good": ["..."],
  "not_good": ["..."],
  "image": "/images/watches/titan-example-model.jpg",
  "query": "Titan Model name watch",
  "merchants": {
    "amazon":      {"url": "https://www.amazon.in/dp/..."},
    "flipkart":    {"url": ""},
    "brand_store": {"url": "https://..."}
  },
  "sources": [{"label": "Maker page", "url": "https://..."}],
  "editors_pick": false,
  "rating": null
}
```

* `brand`, `styles` and `gender` must match `config.json`. Set `budget` to a matching budget slug only when appropriate; use `null` when no price band has been verified. A watch without a band remains in its brand, audience and style collections.
* Put the complete Amazon-generated affiliate URL in `merchants.amazon.url`. Supplied direct links are preserved, including their tracking parameters, and displayed as “View on Amazon.” When a direct product link is present, unrelated shop-search buttons are not added. Without any direct URLs, legacy shop-search links remain available.
* **Prices:** do not type prices. `budget` is only the list the watch belongs to ("Under ₹3,000"). Live prices need Amazon's official API after approval.
* **Images:** use your own photos or product images supplied through a permitted source. Do not substitute an AI illustration for a real product photograph. Without a photo, the card uses a compact text layout with the real model name and specifications.
* **Ratings:** leave `rating` null until real ratings exist. The card shows no rating until it has a verified source.
* New shops go in `merchants.json`; new brands, budgets and styles go in `config.json`.
* A page is `noindex` until it has `min_products_to_index` watches (default 3).

Watch details link to `/watches/products/<id>/`, so a missing price band never produces a broken product URL. `card_specs`, `model_code` and `movement` provide concise card text without an image.


## Filterable collections

The watch collection pages use the shared `collection.py`, `collection.css` and `collection.js` components. Search, brand, audience, style and verified budget filters are built from published products. Adding a ready product automatically adds its filter options and count. Route context sets the initial selection (men, women, brand, style or budget); Clear all widens it to the full collection. The main page starts with all watches. All products and detail links remain available without JavaScript. Watches uses a native filter dialog on phones and a drawer on desktop; other categories retain their existing desktop sidebar. Sorting uses names or editorial order, never unverified prices.

The other category pages use the same component. They show published product records when available, existing sports guide recommendations otherwise, and buying advice for categories without product records. They do not generate stock, prices, ratings or affiliate product links.


The watch browser puts style tiles first, then quick brand/budget selectors, then audience/search/sort controls. The same browser powers audience, brand, style and budget routes. Products have dedicated `/watches/products/<id>/` detail pages. Published cards without an authorised photograph use a compact text layout rather than an oversized model-code panel.

JavaScript paginates matching watches in batches of 24; filters and sorting reset pagination. With JavaScript disabled, route-matching products remain server rendered and style/brand/audience links remain available. Filter counts describe published catalogue records, not live retailer inventory. The `unlisted` budget value means the current price must be checked with the retailer.

Repeated disclosure banners are removed by `compact_affiliate_notices()` in the builder. Retailer buttons carry a short “Paid link” label; the full disclosure and Amazon Associate statement remain in the footer and disclosure page.

## The watch data engine (one record per watch)

Every watch is one file in `src/watches/products/`. Brands, filters, counts, price bands, the Shop by brand row, product pages and the list of possible SEO collections are all generated from those files. **Nothing is entered twice, and a watch is never duplicated for another view.**

### Adding a watch
1. Paste what you know as plain `Key: value` lines into a text file (see `intake-example.txt`), for example `Product`, `Brand`, `Gender`, `Case diameter`, `Strap`, `Strap colour`, `Dial colour`, `Movement`, `Water resistance`, `Warranty`, `Amazon URL`, `Price band`, `Styles`, `Occasions`, `Labels`, `Source`.
2. Run `python3 build.py --watch-intake your-file.txt` for the report: Accepted or Rejected, missing required and optional fields, warnings, categories assigned automatically, filter groups it switches on, and the SEO collections it could belong to.
3. Add `--write` to save the normalised record. Missing facts are left out and shown as "not stated". They are never guessed.

### Fields
**Required:** `id`, `brand`, `product_name`, `gender`. **Buying link:** `amazon_url` (your full tagged link, used exactly as pasted, never edited), `image_source`. **Price:** `price_band` (a configured band such as `under-2000`, never a price). A watch in a band also appears under every higher band.
**Facts (from the maker or listing):** `case_diameter_mm`, `case_thickness_mm`, `band_material`, `band_colour`, `dial_colour`, `case_shape`, `movement`, `display_type`, `water_resistance_atm`, `water_resistance_metres` (ATM x 10 is used when only ATM is given, and flagged), `warranty_type`, `warranty_duration`, `country_of_origin`.
**Editorial (our judgement, kept separate):** `styles`, `occasions`, `features`, `editorial_labels` (`best-value`, `office-pick`, `classic-pick`, `minimal-pick`, `first-watch-pick`), `best_for`, `editorial_notes`, `who_should_buy`, `who_should_skip`, plus the written `verdict`, `paragraphs`, `good`, `not_good`, `sources`.
**Verification:** `source_verified` (a source, or "owner-provided, not independently verified"), `last_verified`.

Analog, Leather Strap and Metal Strap styles are added automatically from `display_type` and `band_material`. Office, Formal, Minimal and similar are editorial and are never inferred. Colour names are normalised (for example OffWhite becomes White).

### Rules the build enforces
No `price`, `mrp`, `rating`, `reviews` or `discount` fields; no rupee prices, star ratings, "tested" claims or the word "waterproof" in any text; a configured price band; valid labels; an https `amazon_url`. Unsupported facts are never created.

### Filters, brands and counts
A filter option appears only when at least one live watch has it, and a group appears only when it has two or more different values. The Shop by brand row lists brands that have live watches. A product from a new brand creates the brand automatically (a warning tells you). `settings.json` controls `brand_order`, `featured_brands`, `hidden_brands`, `planned_filters` (an option shown dimmed before any watch has it) and `brand_names`. To add a new kind of filter, add one row to `Watches.FILTERS` in `watches.py`.

### SEO collections
A collection is a combination of up to two filters. `python3 build.py --collections` lists the combinations that have at least 3 watches. A collection page is indexed by Google only when it is listed in `collections.json` with its own introduction of at least 100 words (plus optional `who_for`, `advice`, `faqs`). Otherwise it stays a normal filter result with `noindex`. The hubs `/watches/`, `/watches/men/` and `/watches/women/` need no approval. A product page without a written review stays `noindex` until it has one.

### Questions shoppers ask
Each watch page shows at most 6 questions chosen by what the record states: fit (needs a case diameter), water resistance (needs a rating), strap material, quartz (needs the movement), style (needs `occasions`) and value (needs a price band). Answers use only the record's facts and plain definitions. A brand comparison appears only when both brands have live watches and `brand-notes.json` holds our own note for them.

## The Watches hub (`/watches/`)

The hub builds its discovery sections from the **published collections**: entries in `collections.json` that have their own introduction (100 words or more), a page that exists, and at least 3 watches. Each published collection carries metadata (`category`, `brand`, `price_band`, `gender`, `seo_status: indexable`, `featured_on_watch_hub`), taken from its URL and its watches. The hub shows:

- **Looking for watches by budget?** one row per price band, with a link to each published brand or gender page in that band.
- **Shop by Brand** and **Shop by Style**, only for brands and styles that have a published page.
- **Men or women?**, **Popular buying guides** (extra guides can be listed under `hub_guides` in `config.json`).

Every link goes to the collection's own URL, never to a JavaScript filter state. To keep a published page off the hub, set `"featured_on_watch_hub": false` in its `collections.json` entry. Deep filter combinations stay normal filter states with no page of their own. The home page shows a compact Watches block that links into the hub.

**Hub extras.** `/watches/` opens with a short intro (80 to 120 words), shows a generated count next to each collection link, and has a "How to choose" block (budget, case size, strap, water resistance). On phones the order is: intro, budget, brand, men and women, filters, Explore watches, then style, how to choose and guides. Collection pages show "Last reviewed" (the newest `last_verified` date among their watches; `--watch-intake --write` stamps today's date on new records), an affiliate note above the first Amazon button, and "Related watch collections" once a second collection is published. Links inside a collection's `intro`, `who_for` and `advice` are written as `[text](/path/)` and become links only when the path is a published collection, a hub or `/watches/guide/`. Cards show only case size, movement, strap, water resistance and, when the watch has an approved `best_for`, "Best for"; every other spec stays on the product page.

**Price-band slider.** Every watch catalogue page has a stepped slider (Any price, then one step per band that has a watch, for example Under ₹2,000 to Under ₹20,000). It shows bands only, never prices, and drives the same Price checkboxes, so the two stay in sync and "Under ₹X" keeps meaning "every watch under X". The bars show how many watches sit in each band. The component is `collection.price_slider(steps)` plus a few lines in `collection.js`; another category reuses it by passing its own bands. A band with no watch is not offered, and appears automatically with its first watch.

**Search phrases (`keywords.json`).** Per collection page, per shopper path. They are never printed as a list. A phrase becomes a "Popular for men / women" quick-filter chip only when it maps to a filter (strap, dial colour, movement, dial size, gold) and a watch matches. Editorial phrases (formal, office, classic, minimalist, elegant, everyday) map to the occasion and style filters, so they appear only once those tags are approved and assigned to watches.

**Price pages.** A price page lists every watch under the band but is indexable only with 3 or more watches whose own band is that band, plus an approved introduction.

**Home page slider.** The home page's Watches block has the same price-band slider ("Pick a budget"). "Show watches" opens `/watches/?price=<band>#watch-collection`, and the Watches page reads `?price=` to start with that band chosen (a normal filter state, no new page). Without JavaScript only the "Explore watches" link shows.
