# SAT Sports Gear (sat.net.in)

Independent sports & fitness gear review site for Indian buyers. Monetized via Amazon Associates, Flipkart Affiliate, and direct sports-brand affiliate programs (Decathlon, Puma, etc.). Part of the **SAT** brand, separate from the SAT India device-recovery project.

## Folder structure

```
.
├── index.html                      # Homepage
├── about.html
├── contact.html
├── privacy-policy.html
├── affiliate-disclosure.html
├── css/
│   └── style.css                   # Shared styles for all pages
├── articles/
│   └── best-badminton-rackets.html # First review article
├── robots.txt                      # Points to sat.net.in sitemap
├── sitemap.xml                     # All 6 current pages
└── .nojekyll                       # Skips Jekyll processing on GitHub Pages
```

No build step: plain HTML/CSS, deployable as-is.

## Run locally

```bash
cd sat-sports-site
python3 -m http.server 8000
```

Open `http://localhost:8000`.

## Deploy

**Production: Cloudflare Pages** (works with a private repo)

Cloudflare dashboard → **Workers & Pages → Create → Pages → Connect to Git** → select this repo.
Build command: *(blank)* · Build output directory: `/`
Then **Custom domains → Add domain** → `sat.net.in`.

Every push to `main` redeploys automatically.

**GitHub Pages** needs a public repo on a free GitHub account, so it is not used while this repo is private.

## Status

Done:
- Article written from manufacturer/retailer specs and published buyer ratings (research-based, not hands-on; the article says so)
- No ₹ prices anywhere: tier labels only
- FAQ and buying guide written; privacy policy dated

Still to do before promoting the site:
- [ ] Attach `sat.net.in` (affiliate networks reject free/sub-path domains)
- [ ] Apply to affiliate networks (Amazon Associates, Flipkart, vCommission/Cuelinks for Puma, MyProtein, etc.)
- [ ] Replace the retailer search-page links in `articles/best-badminton-rackets.html` with approved affiliate links, and add `sponsored` to their `rel`
- [ ] Add hands-on impressions once the rackets have actually been played with
- [ ] Re-check Decathlon BR 100 specs on the India page (weight/balance are UAE-only today)

## Rules to remember (Amazon Associates compliance)

- Never hand-type or scrape a live price. Show a price only if pulled via Amazon's PA-API; otherwise show no number.
- The purchase must complete on the retailer's own page. Never build a cart or checkout here.
- Keep the affiliate disclosure visible on every article and on its own page.
- Write original copy. Do not reuse Amazon's titles, bullets, descriptions or images.
- 3 qualifying Amazon sales within 180 days of approval are needed to keep account/API access.

## Expansion plan

Sports first (narrow-first strategy). Next: personal & beauty care, then musical instruments and devices, only after the first category has traffic and a few ranking articles.
