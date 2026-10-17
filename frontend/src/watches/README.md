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

## Filter fields and how to add a filter

The page order for shoppers is: Shop by style, Shop by brand, Men | Women, Filters (a bottom sheet on phones, a sticky panel on the right on laptops), removable filter chips, then the watches.

The filter panel builds itself from the watch files. Every field is optional, and a value is filled in **only where the maker's page states it**. A watch without a value is not matched when that filter is ticked, and a group with no values is not shown.

| Filter | Watch-file field | Values |
|---|---|---|
| Brand | `brand` | slug from `config.json` brands |
| Price | `budget` | slug from `config.json` budgets (the band of the maker's listed price; never type a price) |
| Style | `styles` (list) | slugs from `config.json` styles |
| Occasion | `occasion` (list) | `office`, `formal`, `casual`, `everyday`, `party`, `gift` |
| Dial size | `case_size_mm` | grouped by the page: 36 and under, 37-40, 41-44, 45+ |
| Strap material | `strap_material` | `leather`, `stainless-steel`, `mesh`, `silicone-rubber`, `fabric-nylon` |
| Movement | `movement` | `quartz`, `automatic`, `mechanical` |
| Water resistance | `water_resistance` text | read from "50 m" or "5 ATM" (1 ATM = 10 m): Splash resistant (under 30 m), 30 m, 50 m, 100 m, 200 m and above. Say "water-resistant", never "waterproof" |
| Dial colour | `dial_colour` (list) | black, white, blue, green, silver, gold, brown |
| Strap colour | `strap_colour` (list) | black, brown, silver, gold, blue, rose-gold |
| Case shape | `case_shape` | round, square, rectangular |
| Features | `features` (list) | date, day-date, chronograph, luminous-hands, second-hand, minimal-dial |
| Case material | `case_material` | alloy-steel, brass, metal, plastic, polycarbonate, resin, stainless-steel |

**To add a new filter:** add one row to `Watches.FILTERS` in `watches.py` (key, title, options, and a function that returns the values of a watch), then add the field to the watch files. The cards, the panel, the counts, the chips and the browser script pick it up with no other change. A watch can have many styles and occasions, so no watch file is ever duplicated for a filtered view.

Filter options that no watch has yet are hidden, except brands, which stay visible and dimmed. The safeguards in `build.py --check` (no typed prices, ratings or "tested" claims, valid https links) apply to every watch file as before.

## Landing pages

Each budget, gender, brand and style has its own page (for example `/watches/men/under-3000/`, `/watches/brands/casio/`, `/watches/style/formal/`). A page stays hidden from Google until it lists at least `min_products_to_index` watches (3). Filters only add temporary `?` states and never replace these URLs.
