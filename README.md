# Sports & Gear Review Site (name and domain not decided yet)

Independent sports & fitness gear review site for Indian buyers, monetised through affiliate programs. The code uses the working name "SAT" and the placeholder domain `sat.net.in`; both live in one file (`frontend/src/site.config.json`), so renaming is a one-file change.

## Repository layout

```
frontend/
├── build.py                  # builds src/ into dist/ (stdlib only)
├── src/
│   ├── site.config.json      # site name, URL, email, nav, footer links
│   ├── templates/base.html   # shared page shell (head, SEO tags)
│   ├── partials/             # header.html, footer.html
│   ├── css/
│   │   ├── base/             # variables, reset, accessibility, print
│   │   ├── layout/           # container, section, header, footer
│   │   ├── components/       # buttons, cards, product-block, faq, ...
│   │   └── pages/            # home, article, hub, not-found
│   ├── js/
│   │   ├── core/             # main.js (every page)
│   │   ├── components/       # outbound-links.js
│   │   └── pages/            # page-specific JS (add when needed)
│   ├── pages/                # one folder per URL: index.html (body) + page.json (SEO meta)
│   └── static/               # copied to the site root (favicon.svg)
└── dist/                     # generated, git-ignored, what gets deployed
backend/                      # planned: Python API (affiliate redirects, contact form)
```

## Build and preview

```bash
cd frontend
python3 build.py            # writes dist/
python3 build.py --serve    # build, then serve http://localhost:8000
```

The build bundles and minifies the split CSS/JS into one file per page (fast pages), renders every page through the template, and generates `sitemap.xml`, `robots.txt` and `_headers`. It fails on broken internal links or missing sources and warns when a title or description is too long.

## Adding a page

1. Create `frontend/src/pages/<folder>/index.html` (page body only) and `page.json` (url, title, description, which component CSS to include, breadcrumbs, dates).
2. Use `{{breadcrumb}}`, `{{site_name}}` and `{{contact_email}}` placeholders in the body.
3. Run the build. The page gets its canonical URL, Open Graph tags, structured data and sitemap entry automatically.

## URLs

Clean folder URLs, no `.html`: `/badminton/best-badminton-rackets/`. Do not change these after launch.

## Deploy (Cloudflare Pages, works with a private repo)

Cloudflare dashboard -> Workers & Pages -> Create -> Pages -> Connect to Git -> select this repo.
- Root directory: `frontend`
- Build command: `python3 build.py`
- Build output directory: `dist`
- Environment variable: `PYTHON_VERSION` = `3.11`

Then add the final domain under Custom domains. GitHub Pages is not used while the repo is private.

## Still to do before promoting the site

- [ ] Decide the final name and domain; edit `site.config.json`, rebuild
- [ ] Add real play-testing notes and photos, a named author and bio (the biggest ranking factor for review sites)
- [ ] Apply to affiliate networks; swap retailer search links for affiliate links and add `sponsored` to their `rel`
- [ ] After Amazon Associates approval, add Amazon's required statement to the affiliate disclosure and footer (not claimed yet)
- [ ] Add an Open Graph image
- [ ] Re-check Decathlon BR 100 specs on the India page (weight/balance are UAE-only today)
- [ ] Build `backend/` (affiliate redirect route, contact form)

## Rules to remember (Amazon Associates compliance)

- Never hand-type or scrape a live price. Show a price only if pulled via Amazon's PA-API; otherwise show no number.
- The purchase must complete on the retailer's own page. Never build a cart or checkout here.
- Keep the affiliate disclosure visible on every article and on its own page.
- Write original copy. Do not reuse Amazon's titles, bullets, descriptions or images.
- 3 qualifying Amazon sales within 180 days of approval are needed to keep account/API access.
