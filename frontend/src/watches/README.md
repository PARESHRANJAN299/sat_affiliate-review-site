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

## Filter fields (optional, add only what the maker's page states)

The filter panel on `/watches/` builds itself from the watch files. Besides brand, budget and style it can use:
* `purpose`: a list from `casual`, `formal`, `swimming`, `hiking`, `running` (only if the listing names the occasion or use).
* `case_material`: one of `alloy-steel`, `brass`, `metal`, `plastic`, `polycarbonate`, `resin`, `stainless-steel` (only if the page states it).
* Water resistance depth comes from the existing `water_resistance` text ("50 m", "5 ATM" is read as 50 m). The groups are Up to 29 m, 30 to 40 m, 41 to 51 m and 52 m and above.

A watch without a field simply does not appear when that filter is ticked. Filter options with no watch yet are hidden, except brands, which stay visible and dimmed so visitors can see which brands are coming.
