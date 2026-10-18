# SAT Fashion data

The six collections belong only to `/fashion/`; the global five-category navigation is unchanged.

`catalog.json` configures approved sources and can contain product records; the private editor stores individual records in `products/*.json`. It starts with an empty product list and no approved hosts. No sample products, affiliate links, retailer images, prices, ratings, discounts or badges are published. The image in the editorial introduction is original AI-generated illustration, not a Nykaa product photograph.

Only add real records after the owner supplies approved Nykaa affiliate data and image sources. Record the exact approved image CDN hosts and affiliate-link hosts in `approved_image_hosts` and `approved_affiliate_hosts`. Approval of a hostname does not itself establish image or affiliate usage rights; keep the source's permission records with the supplied data.

Each product uses `id`, `brand`, `title`, `category`, `image_url`, `affiliate_url`, `active` and `featured`. `category` must be one of `womens-kurtas`, `westernwear`, `indianwear`, `footwear`, `active-sports` or `bags`. Booleans must be real JSON booleans. Inactive drafts are not rendered. Active records require HTTPS links on explicitly approved hosts. Featured products appear first within their own section. All labels and URLs are escaped; supplied affiliate URLs are retained.

Cards show approved images and the brand/title, and link to the SAT product-detail page. The detail page uses a “View on Nykaa” link with `target="_blank"` and `rel="sponsored nofollow noopener"`, with a nearby affiliate disclosure. No price/rating/discount fields are consumed.

The fashion destination currently uses `noindex, follow` and is excluded from the sitemap, preserving the existing sitemap exactly. Adding real records does not automatically change indexing: review the completed content and source approvals before a separate indexing/sitemap change.

## Individual products and the private editor

Run `python3 frontend/fashion_admin.py` and open `http://127.0.0.1:8790/admin/`. This editor is local-only, not a hosted admin service. It is not copied to the public site. Save creates/updates `src/fashion/products/<id>.json` and automatically rebuilds the local site. It does not commit, push, deploy or publish. A failed build rolls back the source change; stale edits are rejected. Saved slugs stay fixed to preserve product URLs.

Records use `id`, `slug`, `brand`, `title`, `category`, `subcategory`, `image_url`, `affiliate_url`, `description`, `attributes`, `featured` and `active`. `attributes` is a dictionary of supplied factual text. Optional `gallery` contains up to eight additional approved image URLs. Unknown prices, ratings, reviews, discounts and sizes are not invented; commerce claims are not accepted as factual attributes. Existing inline `catalog.json` records are still readable, but the editor saves one file per product.

Active records generate `/fashion/products/<slug>/` automatically. Grid and related cards link to these SAT pages, not to the retailer. Only the detail page's “View on Nykaa” CTA uses the stored affiliate URL. The canonical URL, WhatsApp link and related active products are generated from the record. Detail pages remain noindex for this pre-launch review, with self-referencing canonical URLs; the existing sitemap stays unchanged.

The mobile detail page has a large image, optional thumbnails, supplied facts, sharing controls, device-local saved items, a nearby affiliate disclosure and a sticky retailer CTA. There is no cart or checkout. The private editor requires a local origin and anti-CSRF token; approved source hosts are configured separately in `catalog.json` after source permission is obtained. Never run this local editor as a public web service.

## Landing page structure and imagery (2026-10-18)

- Order: Discover Your Style (page heading) (asymmetric mosaic on desktop, swipe cards on mobile), six collection sections, Featured Brands, editorial banner, trust strip, then the sitewide footer.
- Each collection in `fashion.SECTIONS` carries a layout (`feature`, `stagger`, `warm`, `rail`, `energetic`, `luxe`) that `render_products()` turns into a different composition. Every layout works with one product or many.
- SAT editorial artwork: `fashion.ART` maps each collection to an owner-supplied model cutout in `/images/fashion/models/` (1122px and 640px WebP). Bags uses original SVG art in `/images/fashion/editorial/`. These are SAT editorial images, never retailer product photos, and are recorded as `needs-confirmation` in `src/image-credits.json` until the owner records their provenance.
- A category tile uses the first approved product photo for that collection when one exists; otherwise it uses the editorial artwork.
- A collection with no approved products shows the editorial artwork, `EMPTY_NOTE` and buying tips (Women's Kurtas also shows four empty product slots). No product, price, rating or retailer content is invented to fill a slot.
- Featured Brands is derived from product data (`get_brands()`); with no data it shows `BRANDS_EMPTY_NOTE`. Brand pages are not generated.
- Image pipeline: remote images are only used from the exact hostnames in `approved_image_hosts`, which is empty until the permitted source is confirmed.
- Accessors: `get_products`, `get_product_by_slug`, `get_products_by_category`, `get_products_by_brand`, `get_featured_products`, `get_related_products`, `get_brands`.
- The landing page carries no affiliate sentence of its own (the sitewide footer disclosure covers it). TEMPORARY WORDING: `AFFILIATE_NOTE` on product pages is a placeholder, marked `data-disclosure="temporary"`; replace it when the final Nykaa-approved disclosure is confirmed.

## Official Nykaa affiliate widgets (retailer-powered sections)

- `src/fashion/widgets.json` holds one record per widget: `id`, `product_id`, `category`, `source`, `widget_url`, `width`, `height`, `active`, `featured`. `widget_url` is the exact `src` of the iframe from the Nykaa affiliate dashboard (all affiliate parameters unchanged). Never store iframe HTML: records with unsupported fields are rejected.
- `fashion.validate_widgets()` only accepts `https://affiliate.nykaa.com/v2/get_product_widget` URLs that carry the approved `affiliate_id`, the record's own `product_id` and `store=nykaa_fashion`, with no extra characters. A bad record fails the build.
- `widget_shell()` builds the iframe in code (lazy-loaded, titled, 280x360 by default). SAT styles only the wrapper `.nykaa-product-shell`; the card content (image, title, price) is Nykaa's, nothing is copied, scraped or re-typed.
- A collection with active widgets shows a wide SAT editorial banner, `WIDGET_AFFILIATE_NOTE` (easy-to-replace wording, marked `data-disclosure="temporary"`), and a left-to-right scroll rail of widgets: four cards are visible on a wide screen and any number (50 or more) scroll sideways, with arrow buttons when the rail overflows. Iframes are lazy-loaded. Collections without widgets keep their empty state. To add a product: append a record to `widgets.json`.
- Every card has Copy link and (where the browser supports it) Share buttons. There is no WhatsApp button; phones can share through the system Share sheet. They share the SAT page link `https://sat.net.in/fashion/#pick-<product_id>`, which scrolls the rail to that card. The raw Nykaa affiliate link is never shared. Script: `src/js/components/fashion-widgets.js`.
- "Get it on Nykaa" button: add the Nykaa affiliate product link from the dashboard as `affiliate_url` on a widget record. It is shown only when present, opens in a new tab with `rel="sponsored nofollow noopener"` and is never altered. Its host must be listed in `allowed_product_link_hosts` in `widgets.json` (empty until the owner supplies real links); an unapproved host fails the build.
- Collections: `widgets.json` can define `collections` (`id`, `category`, `title`, `suggestions`). A widget with `"collection": "<id>"` appears in that collection's own titled scroll rail (with its suggestions line) after the category's main rail; widgets without it stay in the main rail. Order follows the file.

