# Product data

One JSON file per product, in `src/products/<category-slug>/`, for example `src/products/beauty-personal-care/<id>.json`. The build renders it into its family page (comparison table, review and the picks slot). A family page opens to Google when it has 3 products.

```json
{
  "id": "unique-id",
  "family": "skin-care",
  "slot": "best_overall",
  "name": "Product name", "brand": "Brand",
  "product_type": "Moisturiser",
  "best_for": "Who it suits",
  "suits": "Skin type, hair type or use case",
  "features": ["..."], "key_ingredients": ["..."],
  "pros": ["..."], "cons": ["..."],
  "price_band": "\u20b9500\u2013\u20b91,000",
  "value_for_money": "...", "best_use_case": "...", "avoid": "...",
  "how_to_choose": "...", "alternatives": ["..."],
  "final_recommendation": "...",
  "retailers": {
    "amazon": {"url": "https://..."},
    "flipkart": {"url": ""},
    "brand_store": {"url": ""},
    "other": {"url": ""}
  },
  "sources": [{"label": "Maker page", "url": "https://..."}]
}
```

* `slot`: `best_overall`, `best_budget`, `best_value`, `best_daily`, `best_premium` or `best_beginner`.
* `price_band` is one of: Under \u20b9500, \u20b9500\u2013\u20b91,000, \u20b91,000\u2013\u20b92,000, Premium. Never type a live price.
* No ratings, reviews or testing claims unless they are true.
* Retailer links are plain until `affiliate_active` is true in `site.config.json`. Then links get `rel="sponsored"` and a disclosure line. The Amazon Associate sentence appears only when `amazon_associate_approved` is also true.
* Files in `_sample/` are template previews only and never appear as products.
