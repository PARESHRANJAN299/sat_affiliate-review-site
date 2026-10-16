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
* **Images:** use your own photos or product images supplied through a permitted source. Do not substitute an AI illustration for a real product photograph. Without a photo, the card shows a clearly labelled model-reference panel and directs readers to retailer photographs.
* **Ratings:** leave `rating` null until real ratings exist. The card keeps space for it but shows nothing.
* New shops go in `merchants.json`; new brands, budgets and styles go in `config.json`.
* A page is `noindex` until it has `min_products_to_index` watches (default 3).

The Watches landing page reads `launch_collection` in `config.json` to show the selected brand and audience collection before budget and brand navigation. Watch details link to the brand page’s review anchor, so a missing price band never produces a broken product URL. `card_specs`, `model_code` and `movement` provide concise card text without an image.


## Filterable collections

The landing page uses the shared `collection.py`, `collection.css` and `collection.js` components. Search, brand, audience, style and verified budget filters are built from published products. Adding a ready product automatically adds its filter options and count. `launch_collection` sets the initial brand/audience selection; Clear all widens it to the full collection. All products and detail links remain available without JavaScript. Mobile filters use a native modal dialog; desktop filters remain beside the grid. Sorting uses names or editorial order, never unverified prices.

The other category pages use the same component. They show published product records when available, existing sports guide recommendations otherwise, and buying advice for categories without product records. They do not generate stock, prices, ratings or affiliate product links.
