# Images

Served from the site root, so `src/static/images/categories/sports-fitness.jpg` is `/images/categories/sports-fitness.jpg`.

```
images/
  categories/   one picture per top-level category: <category-slug>.jpg (4:3, about 736 x 552)
                and <category-slug>-thumb.jpg (square, 160 x 160, used in the menu)
  products/     <product-id>.jpg  (square, about 800 x 800)
  brands/       <brand-slug>.svg or .png
```

Rules
* Use only photos you took, bought, or have a licence for. Do not use shop, brand or Amazon images unless their programme terms allow it.
* Lowercase names with hyphens, matching the slug or id used in the data files.
* Keep each file under 150 KB (JPEG quality about 80). Resize before adding.
* To use a category picture, set `"image"` (and `"thumb"` for the menu) in `src/categories.json`. Remove them to go back to the drawn icon.
