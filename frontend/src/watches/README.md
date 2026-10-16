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

* `brand`, `budget`, `styles`, `gender` must match `config.json`; the build fails if they do not.
* A watch with no merchant URL gets a plain shop search link. Add a URL per shop when you have one.
* **Prices:** do not type prices. `budget` is only the list the watch belongs to ("Under ₹3,000"). Live prices need Amazon's official API after approval.
* **Images:** use only your own photos or images you have the right to use. Do not copy shop or Amazon images.
* **Ratings:** leave `rating` null until real ratings exist. The card keeps space for it but shows nothing.
* New shops go in `merchants.json`; new brands, budgets and styles go in `config.json`.
* A page is `noindex` until it has `min_products_to_index` watches (default 3).


## The Watches page collection

`/watches/` opens with a slim banner and a **product collection**: a preset (set in `config.json` as `"featured_collection": {"brand": "fossil", "gender": "men"}`) is shown first, with a Men's/Women's switch, brand, budget and style filters (a side panel on laptops, a bottom sheet on phones) and sorting. Every watch file is in the page, so filters work on all of them; a visitor who changes a filter sees the matching watches from every brand. Change `featured_collection` to feature another brand or gender. Leave it out to show every watch.

**Adding a watch is still one file** in `src/watches/products/`. It then appears in the collection and the filters (counts update by themselves), on its brand, budget and style pages, in site search and the sitemap, and on its own page `/watches/<brand>/<model>/` (the brand prefix of the id is dropped, so `fossil-grant-fs4736` becomes `/watches/fossil/grant-fs4736/`).

Buttons say "View on Amazon" (a product link) or "Find on Amazon" (a search link). Put the product link in `merchants.amazon.url`; the build adds the tracking ID once `affiliate_active` is on.
