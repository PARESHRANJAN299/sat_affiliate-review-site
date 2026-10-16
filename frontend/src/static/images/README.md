# Images

Served from the site root, so `src/static/images/categories/sports-fitness.jpg` is `/images/categories/sports-fitness.jpg`.

```
images/
  categories/   one picture per top-level category: <category-slug>.jpg (4:3, about 736 x 552)
                and <category-slug>-thumb.jpg (square, 160 x 160, used in the menu)
  home/         lifestyle pictures for the home hero (4:5 portrait, 320 x 400, about 50 KB each); every .jpg in this folder joins the drifting rows, in file-name order (01-, 02-, 03- ... put one rotating picture in each of the three rows, so number them to mix the categories)
  banners/      one folder per category slug (clothing-accessories, sports-fitness, beauty-personal-care, home-kitchen) with 900 x 405 pictures (about 2.2:1, quality 55-60, under 80 KB each).
                They fade softly behind the category page header and rotate every few seconds, in file-name order (01-, 02- ...). Add or remove a .jpg to change them. Watches has no banner folder on purpose.
  products/     <product-id>.jpg  (square, about 800 x 800)
  brands/       <brand-slug>.svg or .png
```

Rules
* Use only photos you took, bought, or have a licence for. Do not use shop, brand or Amazon images unless their programme terms allow it.
* Lowercase names with hyphens, matching the slug or id used in the data files.
* Keep each file under 150 KB (JPEG quality about 80). Resize before adding.
* To use a category picture, set `"image"` (and `"thumb"` for the menu) in `src/categories.json`. Remove them to go back to the drawn icon.
