# Product data

**Adding a product takes one file.** Copy `_sample/NEW-PRODUCT-TEMPLATE.json` to `src/products/<category>/<id>.json`, fill it in, then run

```
cd frontend && python3 build.py --check
```

The check takes about a second. It lists every product file with a plain message for anything to fix (for example: `family "tshirts" not found. Did you mean one of: t-shirts, shirts?`) and shows how many products each product type has against the working target of 15. Push when it says `0 errors`. A build with errors does not go live, so the live site stays as it is.

## What the site does with a product

* It appears on its product-type page (for example `/clothing-accessories/men/t-shirts/`) in a filterable list: price, brand, product type and the category filters below.
* Clothing & Accessories also shows it on the single `/clothing-accessories/` page under the **Women / Girls / Men** tab(s) named in `audience`.
* It is found by site search (name, brand, audience, filter words).
* The details window shows the full review text; without JavaScript the same review is on the page.
* A product-type page opens to Google when it has 3 products. Before that it stays hidden (`noindex`).
* The sample preview pages (`/…/listing-preview/`, `/…/review-template/`, `/watches/preview/`) are **not part of the live site**. To look at them while working, run `python3 build.py --previews --serve`.

## Fields

Required: `id` (same as the file name), `family`, `name`, `brand`, `price_band`. Clothing also needs `audience` (`women`, `girls`, `men`; a product can have more than one, but it must fit its product type: men's shirts are not for women).

* `price_band`: one of the bands of the category (for example `Under ₹500`, `₹500–₹1,000`, `₹1,000–₹2,000`, `Premium`; Home & Kitchen uses `Under ₹1,000`, `₹1,000–₹3,000`, `₹3,000–₹6,000`, `Premium`). **Never type a price.**
* `facets`: filter values, only from the lists in `src/facets.json`. To add a new value, add one line there first.
* `editor_pick`: `true` puts "Our pick" on the card and lists it first. `rank` (1, 2, 3...) orders the picks. Leave `rank` as `null` otherwise.
* `checked`: the day you last looked at the shop listing. It shows on the card. The check warns when it is older than 90 days.
* `image`: your own photo, or one you have the right to use, saved in `src/static/images/products/`. Do not copy shop or Amazon images. Without an image the card shows a neutral "Photo coming" tile.
* `retailers`: `amazon`, `flipkart`, `brand_store`, `other`, each `{ "url": "https://..." }`. Links must start with `https://`. They are plain links until `affiliate_active` is true in `site.config.json`; then they get `rel="sponsored"` and the disclosure line appears once above the list. The "As an Amazon Associate" sentence appears as soon as `amazon_tracking_id` is also set (see "Amazon links: sign-up day" below).
* `sources`: pages you read (they show under "Pages we read").
* `slot`: optional, one of `best_overall`, `best_budget`, `best_value`, `best_daily`, `best_premium`, `best_beginner` and the other keys of the category's pick slots.

## The check stops the build when it finds

a typed price anywhere in the text, a rating ("4.5 out of 5", "5 stars"), a claim that we tested the product ("personally tested", "lab tested"), a price claim ("lowest price"), a filter value that is not in `facets.json`, a retailer link that is not `https://`, an image file that does not exist, an unknown product type, or a duplicate `id`.

---

# Older notes (still valid)


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
* Retailer links are plain until `affiliate_active` is true in `site.config.json`. Then links get `rel="sponsored"` and a disclosure line. The Amazon Associate sentence appears on every page once `amazon_tracking_id` is set as well.
* Files in `_sample/` are template previews only and never appear as products.

## Amazon links: sign-up day (this is NOT "after approval")

Amazon approves you only **after** you have driven at least 3 qualifying sales within the first 180 days after you sign up, and those sales count only through your tagged links. Amazon rejects accounts whose links are not tagged, and requires the sentence "As an Amazon Associate I earn from qualifying purchases." on the site. So the links, the tag and the sentence must be live from the day you sign up, not after approval. (Source: affiliate-program.amazon.in/help/node/topic/G8TW5AE9XL2VX9VM and the Operating Agreement section 10.)

Before you sign up, keep `affiliate_active` false and `amazon_tracking_id` empty. Amazon links are then plain links and earn nothing. Run `python3 build.py --governance --simulate-signup` any time to see what would fail on sign-up day.

1. Open the product on amazon.in and copy the address. The clean form is `https://www.amazon.in/dp/<ASIN>` (the 10-character code after `/dp/`). Remove everything after the ASIN: no `ref=`, no `tag=`, no tracking codes. Never use a shortener such as bit.ly or amzn.to.
2. Put it in the product file: `"retailers": {"amazon": {"url": "https://www.amazon.in/dp/B0XXXXXXXX"}}`. Guides use the `stores` list; hand-written pages can just contain the plain amazon.in link.
3. Do not copy Amazon's pictures, star ratings, review text or prices onto SAT. Write your own words and use your own photo; show only the price band.
4. **Sign-up day:** Amazon gives you a tracking ID (it looks like `sat-21`). In `src/site.config.json` set `"amazon_tracking_id": "sat-21"` and `"affiliate_active": true`, run `python3 build.py --governance`, fix every FAIL, push, and check the live site in a private window. From then on every amazon.in link on product, guide and hand-written pages gets `?tag=sat-21` and `rel="sponsored"` automatically, the sentence appears in the footer of every page, next to Amazon buttons and on the disclosure page, and the build stops if the tracking ID is missing. Update the privacy page the same day (Amazon links, Amazon cookies). `amazon_associate_approved` is only a note for you: set it to true after Amazon's approval email; it changes nothing on the site.
5. Hand-written pages (for example Badminton Rackets) are tagged by the build too; you do not edit those links.

## Rules after you sign up (zero tolerance)

* Never buy through your own links or ask family or friends to; never offer money, discounts or points for using a link.
* No price alerts, price history or live prices; no Amazon prices, pictures, ratings or review text.
* No link shorteners, redirect pages or cloaked links; no Amazon logos; do not imply Amazon endorses SAT.
* No Amazon links in emails or messages; no bidding on Amazon trademarks.
* Keep content real and recent: at least 10 useful guides, each updated with real changes at least every 60 days.
* Declare every site or social page you use in the Associates account; use the tracking ID on those sites only.
* Run `python3 build.py --governance` before every push once links are live.
