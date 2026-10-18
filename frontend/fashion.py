"""Fashion destination. Published products require explicitly approved image/link hosts."""
import html
import json
import copy
from pathlib import Path
import re
from urllib.parse import urlsplit, quote

# (anchor, title, icon art, tagline, tips, layout). Layout picks the section composition in render_products().
SECTIONS = [
    ('womens-kurtas', 'Women’s Kurtas', 'kurtas-kurti-sets', 'Elegant styles for everyday and special occasions.', ['Compare fabric composition and care instructions.', 'Check the length, lining and size chart for the exact garment.'], 'feature'),
    ('westernwear', 'Westernwear', 'casual-dresses', 'Modern pieces for everyday style.', ['Think about how each piece fits your existing wardrobe.', 'Compare fit, fabric, closures and care requirements.'], 'stagger'),
    ('indianwear', 'Indianwear', 'kurtas', 'Tradition with a personal touch.', ['Check what is included in the set before buying.', 'Compare fabric, lining and embellishment care.'], 'warm'),
    ('footwear', 'Footwear', 'sports-shoes', 'Comfort for every step.', ['Use the brand’s size chart and compare foot measurements.', 'Check sole material, fastening and the retailer’s return terms.'], 'rail'),
    ('active-sports', 'Active & Sports', 't-shirts', 'Move comfortably. Feel like yourself.', ['Choose the fit and support for your intended activity.', 'Compare fabric composition, stretch and washing instructions.'], 'energetic'),
    ('bags', 'Bags', 'sports-bags', 'Carry what matters.', ['Compare dimensions with the items you carry every day.', 'Check strap length, closures, compartments and materials.'], 'luxe'),
]


# TEMPORARY: current affiliate wording, kept until the final Nykaa-approved disclosure is confirmed.
# Replace this one constant (used on /fashion/ and every product page) when the approved text arrives.
AFFILIATE_NOTE = 'SAT may earn a commission if you purchase through this link, at no extra cost to you.'
EDITORIAL_DIR = '/images/fashion/editorial/'
MODEL_DIR = '/images/fashion/models/'
# SAT editorial artwork per collection (owner-supplied model cutouts); None falls back to original SVG art. Never retailer imagery.
ART = {'womens-kurtas': 'purple-saree', 'westernwear': 'pink-dress', 'indianwear': 'purple-saree', 'footwear': 'white-tee-b', 'active-sports': 'white-tee-a', 'bags': None}
ART_ALT = {'purple-saree': 'Editorial image: a woman seated on a stool in a purple saree with an embroidered blouse.', 'pink-dress': 'Editorial image: a woman in a pink ribbed dress with a black cardigan, holding a quilted black bag.', 'white-tee-a': 'Editorial image: a woman sitting cross-legged in a white tee and blush joggers.',
           'white-tee-b': 'Editorial image: a woman sitting cross-legged in a white tee, blush joggers and white trainers.'}
EMPTY_NOTE = 'Products will appear here once approved Nykaa catalogue items are added.'
BRANDS_EMPTY_NOTE = 'Brands will appear here once approved Nykaa catalogue items are added.'


def art_picture(slug, sizes, alt=False, stem=None, priority=False):
    """SAT editorial image for a collection (responsive WebP cutout, or the original SVG fallback)."""
    stem = stem or ART.get(slug)
    if not stem:
        return f'<img class="fashion-art" src="{EDITORIAL_DIR}{slug}.svg" alt="" width="1200" height="1500" loading="lazy" decoding="async">'
    load = 'fetchpriority="high"' if priority else 'loading="lazy" decoding="async"'
    return (f'<img class="fashion-art" src="{MODEL_DIR}{stem}-640.webp" srcset="{MODEL_DIR}{stem}-640.webp 640w, {MODEL_DIR}{stem}-1122.webp 1122w" sizes="{sizes}" '
            f'alt="{esc(ART_ALT[stem]) if alt else ""}" width="1122" height="1402" {load}>')


def esc(value):
    return html.escape(str(value), quote=True)


def approved_url(value, hosts):
    if not isinstance(value, str) or not value or any(char.isspace() for char in value):
        return False
    try:
        url = urlsplit(value)
        return url.scheme == 'https' and not url.username and not url.password and url.port in (None, 443) and url.hostname in hosts
    except ValueError:
        return False


def read_data(src):
    base = Path(src) / 'fashion'
    data = json.loads((base / 'catalog.json').read_text())
    if not isinstance(data, dict) or not isinstance(data.get('products'), list):
        raise ValueError('catalog.json must contain an object with a products list')
    for path in sorted((base / 'products').glob('*.json')):
        data['products'].append(json.loads(path.read_text()))
    return data


def category_slug(value):
    if not isinstance(value, str):
        return ''
    normalized = re.sub(r'[^a-z0-9]', '', value.lower())
    return next((slug for slug, title, *_ in SECTIONS if normalized in (re.sub(r'[^a-z0-9]', '', slug), re.sub(r'[^a-z0-9]', '', title.lower()))), '')


def validate(data):
    if not isinstance(data, dict):
        return [], ['fashion data: root must be an object']
    problems, active, ids, slugs = [], [], set(), set()
    if not isinstance(data.get('products'), list):
        return [], ['fashion data: products must be a list']
    for config in ('approved_image_hosts', 'approved_affiliate_hosts'):
        hosts = data.get(config)
        if not isinstance(hosts, list) or any(not isinstance(host, str) or not re.fullmatch(r'[a-z0-9.-]+', host) for host in hosts):
            return [], [f'fashion data: {config} must be exact lowercase approved hostnames']
    for record in data['products']:
        before = len(problems)
        if not isinstance(record, dict):
            problems.append('fashion data: each product must be an object')
            continue
        product = copy.deepcopy(record)
        pid = product.get('id', '')
        for field, seen in [('id', ids), ('slug', slugs)]:
            value = product.get(field, '')
            if not isinstance(value, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value) or value in seen or len(value) > 120:
                problems.append(f'fashion product {pid!r}: {field} must be unique lowercase words/numbers')
            seen.add(str(value))
        if not isinstance(product.get('active'), bool) or not isinstance(product.get('featured'), bool):
            problems.append(f'fashion product {pid}: active and featured must be booleans')
        if product.get('active') is not True:
            continue
        for field in ('brand', 'title', 'description', 'subcategory'):
            value = product.get(field)
            if not isinstance(value, str) or len(value) > (6000 if field == 'description' else 250) or (field in ('brand', 'title') and not value.strip()):
                problems.append(f'fashion product {pid}: valid {field} is required')
        product['category'] = category_slug(product.get('category'))
        if not product['category']:
            problems.append(f'fashion product {pid}: unknown category')
        for field, config in [('image_url', 'approved_image_hosts'), ('affiliate_url', 'approved_affiliate_hosts')]:
            if not approved_url(product.get(field), data.get(config, [])):
                problems.append(f'fashion product {pid}: {field} requires HTTPS on an explicitly approved host')
        attributes = product.get('attributes')
        if not isinstance(attributes, dict) or len(attributes) > 30 or any(not isinstance(key, str) or not key.strip() or len(key) > 80 or not isinstance(value, str) or len(value) > 1000 for key, value in (attributes.items() if isinstance(attributes, dict) else [])):
            problems.append(f'fashion product {pid}: attributes must be factual text labels and values')
        elif any(re.search(r'\b(price|prices|mrp|discount|ratings?|reviews?|bestseller)\b', key, re.I) for key in attributes):
            problems.append(f'fashion product {pid}: commerce claims are not supported in product facts')
        gallery = product.get('gallery', [])
        if not isinstance(gallery, list) or len(gallery) > 8 or any(not approved_url(url, data['approved_image_hosts']) for url in gallery):
            problems.append(f'fashion product {pid}: gallery images require an approved image source')
        if len(problems) == before:
            active.append(product)
    return sorted(active, key=lambda item: (not item['featured'], item['id'])), problems


def catalog(src):
    try:
        return validate(read_data(src))
    except (OSError, ValueError) as exc:
        return [], [f'fashion data: cannot read product data ({exc})']


def product_url(product):
    return '/fashion/products/' + product['slug'] + '/'


# Data accessors. Each takes the validated active-product list returned by catalog().
def get_products(products):
    return list(products)


def get_product_by_slug(products, slug):
    return next((item for item in products if item['slug'] == slug), None)


def get_products_by_category(products, category):
    return [item for item in products if item['category'] == category]


def get_products_by_brand(products, brand):
    key = brand.strip().casefold()
    return [item for item in products if item['brand'].strip().casefold() == key]


def get_featured_products(products):
    return [item for item in products if item['featured']]


def get_related_products(products, product, limit=4):
    related = [item for item in products if item['id'] != product['id']]
    related.sort(key=lambda item: (item['category'] != product['category'], not item['featured'], item['id']))
    return related[:limit]


def get_brands(products):
    """Brand names and style counts derived from product data, largest first."""
    counts = {}
    for item in products:
        name = item['brand'].strip()
        key = name.casefold()
        shown, count = counts.get(key, (name, 0))
        counts[key] = (shown, count + 1)
    return sorted(counts.values(), key=lambda entry: (-entry[1], entry[0].casefold()))


def product_card(product):
    url = product_url(product)
    return (f'<article class="fashion-product"><a class="fashion-product-link" href="{esc(url)}"><img src="{esc(product["image_url"])}" alt="{esc(product["brand"] + " " + product["title"])}" loading="lazy" decoding="async" width="480" height="600">'
            f'<div><p class="fashion-product-brand">{esc(product["brand"])}</p><h3>{esc(product["title"])}</h3>'
            + (f'<p class="fashion-card-subcategory">{esc(product["subcategory"])}</p>' if product.get('subcategory') else '') +
            '<span class="fashion-card-more">View product details →</span></div></a></article>')


def retailer_cta(product, css=''):
    return f'<a class="sat-fashion-cta {esc(css)}" href="{esc(product["affiliate_url"])}" target="_blank" rel="sponsored nofollow noopener">View on Nykaa <span aria-hidden="true">→</span><span class="visually-hidden"> (opens in a new tab)</span></a>'


ARROW = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5M11 6l-6 6 6 6"/></svg>'
HEART = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></svg>'


def product_page(product, products, site_url):
    url = product_url(product)
    canonical = site_url.rstrip('/') + url
    category = next(section for section in SECTIONS if section[0] == product['category'])
    images = list(dict.fromkeys([product['image_url']] + product.get('gallery', [])))
    thumbnails = ''
    if len(images) > 1:
        thumbnails = '<div class="fashion-thumbnails" role="group" aria-label="Product images" data-gallery-thumbnails hidden>' + ''.join(
            f'<button type="button" data-gallery-image="{esc(image)}" aria-label="Show product image {index}" aria-pressed="{str(index == 1).lower()}"><img src="{esc(image)}" alt="" loading="lazy" width="72" height="90"></button>' for index, image in enumerate(images, 1)) + '</div>'
    facts = ''.join(f'<div><dt>{esc(key)}</dt><dd>{esc(value)}</dd></div>' for key, value in product['attributes'].items() if value.strip())
    facts_html = f'<section class="fashion-facts"><h2>Product details</h2><dl>{facts}</dl></section>' if facts else ''
    description = ''.join(f'<p>{esc(paragraph)}</p>' for paragraph in product['description'].splitlines() if paragraph.strip())
    related = get_related_products(products, product)
    related_html = '<section class="fashion-related"><div><h2>You may also like</h2><a href="/fashion/">Explore the edit →</a></div><div class="fashion-products fashion-rail-mobile">' + ''.join(product_card(item) for item in related) + '</div></section>' if related else ''
    whatsapp = 'https://wa.me/?text=' + quote(product['brand'] + ' ' + product['title'] + '\n' + canonical, safe='')
    body = (f'<div class="container fashion-detail" data-fashion-detail data-product-id="{esc(product["id"])}" data-canonical="{esc(canonical)}" data-share-title="{esc(product["brand"] + " " + product["title"])}">'
            f'<nav class="fashion-detail-tools" aria-label="Product actions"><a class="fashion-tool-back" href="/fashion/#{category[0]}" aria-label="Back to {esc(category[1])}">{ARROW}<span>Back to {esc(category[1])}</span></a><span class="fashion-detail-label" aria-hidden="true">Details</span><div><button type="button" data-save-product aria-pressed="false" aria-label="Save this product" hidden>{HEART}</button><a href="#fashion-share">Share ↗</a></div></nav>'
            '<div class="fashion-detail-layout"><div class="fashion-gallery">'
            f'<img class="fashion-main-image" src="{esc(product["image_url"])}" alt="{esc(product["brand"] + " " + product["title"])}" width="800" height="1000" fetchpriority="high" data-main-product-image>' + thumbnails + '</div>'
            f'<div class="fashion-detail-copy"><p class="fashion-detail-brand">{esc(product["brand"])}</p><h1>{esc(product["title"])}</h1>'
            f'<p class="fashion-detail-category"><a href="/fashion/#{category[0]}">{esc(category[1])}</a>' + (f' · {esc(product["subcategory"])}' if product.get('subcategory') else '') + '</p>'
            f'<div class="fashion-detail-description">{description}</div>{facts_html}<div class="fashion-primary">{retailer_cta(product)}</div>'
            f'<p class="fashion-affiliate-note" data-disclosure="temporary">Affiliate disclosure: {esc(AFFILIATE_NOTE)} <a href="/affiliate-disclosure/">Read the disclosure</a>.</p>'
            f'<section class="fashion-share" id="fashion-share"><h2>Share this find</h2><div><a href="{esc(whatsapp)}" target="_blank" rel="noopener">WhatsApp</a><button type="button" data-copy-product hidden>Copy link</button><button type="button" data-share-product hidden>More ↗</button></div><p role="status" data-product-status></p></section></div></div>'
            + related_html + f'<aside class="fashion-sticky" aria-label="Retailer link">{retailer_cta(product)}<small>Affiliate link · Purchase on Nykaa</small></aside></div>')
    return {'url': url, 'title': product['brand'] + ' ' + product['title'], 'description': (product['description'] or product['title'])[:155],
            'css': ['buttons', 'breadcrumb', 'fashion-gateway', 'fashion', 'fashion-product'], 'js': ['fashion-product'], 'theme': 'fashion-detail',
            'noindex': True, 'canonical_always': True, 'breadcrumbs': [['Fashion Edit', '/fashion/'], [category[1], '/fashion/#' + category[0]], [product['title'], url]],
            'updated': product.get('updated', '2026-10-18'), '_slug': 'fashion-product-' + product['slug'], '_body': body}


def pages(src, icon, site_url):
    products, errors = catalog(src)
    landing, _ = page(src, icon)
    landing['canonical_always'] = True
    return [landing] + [product_page(product, products, site_url) for product in products], errors


def render_products(layout, matching):
    """Compose one collection's products. Every layout copes with 1..n products."""
    cards = [product_card(item) for item in matching]
    if layout == 'feature':
        extra = f'<div class="fashion-products">{"".join(cards[5:])}</div>' if cards[5:] else ''
        return f'<div class="fashion-feature"><div class="fashion-feature-lead">{cards[0]}</div><div class="fashion-feature-rest">{"".join(cards[1:5])}</div></div>' + extra
    if layout == 'rail':
        return '<div class="fashion-rail" tabindex="0" role="region" aria-label="Footwear picks">' + ''.join(cards) + '</div>'
    return f'<div class="fashion-grid fashion-grid-{layout}">{"".join(cards)}</div>'


def render_empty(slug, tips, layout, icon=lambda *args: ''):
    """Fallback for a collection with no approved products: SAT editorial artwork, a clear note and buying tips, composed per layout."""
    frame = f'<figure class="fashion-frame fashion-tint-{slug}">{art_picture(slug, "(min-width: 900px) 40vw, 90vw")}</figure>'
    advice = ('<div class="fashion-empty-copy"><p class="fashion-empty-note">' + EMPTY_NOTE + '</p><ul>' + ''.join(f'<li>{esc(tip)}</li>' for tip in tips) + '</ul></div>')
    if layout == 'feature':
        slots = f'<span class="fashion-slot">{HANGER}</span>' * 4
        return f'<div class="fashion-empty fashion-empty-feature">{frame}<div class="fashion-empty-copy"><p class="fashion-empty-note">{EMPTY_NOTE}</p><div class="fashion-slots" aria-hidden="true">{slots}</div></div></div>'
    if layout == 'rail':
        # A gallery waiting for products: one editorial frame and empty slots.
        return f'<div class="fashion-empty fashion-empty-rail"><div class="fashion-rail-slots" aria-hidden="true">{frame}<i></i><i></i><i></i></div>{advice}</div>'
    return f'<div class="fashion-empty">{frame}{advice}</div>'


HANGER = '<svg class="fashion-slot-icon" viewBox="0 0 48 48" aria-hidden="true"><path d="M24 14a4 4 0 1 1 4 4c-2 0-4 1.3-4 3.5V24"/><path d="M24 24 5 36.5a2 2 0 0 0 1.1 3.5h35.8a2 2 0 0 0 1.1-3.5z"/></svg>'

TRUST_ICONS = (
    '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c.6-4 3.4-6 7-6s6.4 2 7 6"/></svg>',
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l7 3v5c0 4.6-3 8.3-7 10-4-1.7-7-5.4-7-10V6z"/><path d="M9 12l2.2 2.2L15.5 10"/></svg>',
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19c0-8 5-13 14-14 0 9-5 14-13 14"/><path d="M5 19c2-4 5-7 9-9"/></svg>',
)


def page(src, icon):
    products, problems = catalog(src)
    tiles, sections = [], []
    for index, (slug, title, art, description, tips, layout) in enumerate(SECTIONS, 1):
        matching = get_products_by_category(products, slug)
        if matching:
            visual = f'<img class="fashion-photo" src="{esc(matching[0]["image_url"])}" alt="" loading="lazy" decoding="async" width="800" height="1000">'
        else:
            visual = art_picture(slug, '(min-width: 900px) 34vw, 62vw', priority=(index == 1))
        tiles.append(f'<a class="fashion-category fashion-category-{slug} fashion-tint-{slug}" href="#{slug}">{visual}'
                     f'<span class="fashion-category-label"><strong>{esc(title)}</strong><em>{esc(description)}</em><span class="fashion-category-arrow" aria-hidden="true">→</span></span></a>')
        contents = render_products(layout, matching) if matching else render_empty(slug, tips, layout, icon)
        sections.append(f'<section class="fashion-section fashion-section-{layout}" id="{slug}" aria-labelledby="{slug}-title"><header><p class="fashion-section-number">0{index}</p><h2 id="{slug}-title">{esc(title)}</h2><p>{esc(description)}</p></header>{contents}<a class="fashion-back" href="#fashion-categories">Back to styles ↑</a></section>')
    brands = get_brands(products)
    if brands:
        brands_html = ('<section class="fashion-brands" aria-labelledby="fashion-brands-title"><header><p class="fashion-section-number">BRANDS</p><h2 id="fashion-brands-title">Featured Brands</h2></header><ul>'
                       + ''.join(f'<li><strong>{esc(name)}</strong><span>{count} {"style" if count == 1 else "styles"}</span></li>' for name, count in brands) + '</ul></section>')
    else:
        brands_html = (f'<section class="fashion-brands fashion-brands-empty" aria-labelledby="fashion-brands-title"><header><p class="fashion-section-number">BRANDS</p><h2 id="fashion-brands-title">Featured Brands</h2></header><p class="fashion-empty-note">{BRANDS_EMPTY_NOTE}</p></section>')
    banner = ('<section class="fashion-banner" aria-labelledby="fashion-banner-title"><div class="fashion-banner-copy"><h2 id="fashion-banner-title">Everyday fashion<br>for your everyday life.</h2><p>Style. Confidence. You.</p>'
              '<a class="fashion-banner-cta" href="#fashion-categories">Explore Looks <span aria-hidden="true">→</span></a></div>'
              f'<figure class="fashion-banner-art"><picture><source media="(max-width: 719px)" srcset="{MODEL_DIR}white-tee-b-640.webp"><img class="fashion-art" src="{MODEL_DIR}pink-dress-640.webp" srcset="{MODEL_DIR}pink-dress-640.webp 640w, {MODEL_DIR}pink-dress-1122.webp 1122w" sizes="(min-width: 900px) 40vw, 100vw" alt="{esc(ART_ALT["pink-dress"])}" width="1122" height="1402" loading="lazy" decoding="async"></picture></figure></section>')
    trust = ('<section class="fashion-trust" aria-label="Why SAT"><ul>'
             f'<li>{TRUST_ICONS[0]}<span>A little research.<br>A better choice.</span></li><li>{TRUST_ICONS[1]}<span>Curated from trusted retailers.</span></li><li>{TRUST_ICONS[2]}<span>Styles for every part of your life.</span></li></ul></section>')
    body = ('<div class="container fashion-page">'
            '<section class="fashion-discover" id="fashion-categories" aria-labelledby="fashion-discover-title"><h1 id="fashion-discover-title">Discover Your Style</h1>'
            '<nav class="fashion-categories" aria-label="Fashion collections">' + ''.join(tiles) + '</nav></section>'
            + ''.join(sections) + brands_html + banner + trust + '</div>')
    return {'url': '/fashion/', 'title': 'The SAT Fashion Edit', 'description': 'Explore women’s kurtas, westernwear, Indianwear, footwear, active and sportswear, and bags with the SAT Fashion Edit.',
            'css': ['buttons', 'breadcrumb', 'fashion-gateway', 'fashion'], 'js': [], 'noindex': True,
            'breadcrumbs': [['Fashion Edit', '/fashion/']], 'updated': '2026-10-18', '_slug': 'fashion', '_body': body}, problems
