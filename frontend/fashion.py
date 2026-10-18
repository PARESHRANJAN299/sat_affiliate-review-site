"""Fashion destination. Published products require explicitly approved image/link hosts."""
import html
import json
import copy
from pathlib import Path
import re
from urllib.parse import urlsplit, quote

SECTIONS = [
    ('womens-kurtas', 'Women’s Kurtas', 'kurtas-kurti-sets', 'Everyday elegance, your way.', ['Compare fabric composition and care instructions.', 'Check the length, lining and size chart for the exact garment.']),
    ('westernwear', 'Westernwear', 'casual-dresses', 'Modern pieces for everyday style.', ['Think about how each piece fits your existing wardrobe.', 'Compare fit, fabric, closures and care requirements.']),
    ('indianwear', 'Indianwear', 'kurtas', 'Tradition with a personal touch.', ['Check what is included in the set before buying.', 'Compare fabric, lining and embellishment care.']),
    ('footwear', 'Footwear', 'sports-shoes', 'Comfort for every step.', ['Use the brand’s size chart and compare foot measurements.', 'Check sole material, fastening and the retailer’s return terms.']),
    ('active-sports', 'Active & Sports', 't-shirts', 'Move comfortably. Feel like yourself.', ['Choose the fit and support for your intended activity.', 'Compare fabric composition, stretch and washing instructions.']),
    ('bags', 'Bags', 'sports-bags', 'Carry what matters.', ['Compare dimensions with the items you carry every day.', 'Check strap length, closures, compartments and materials.']),
]


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


def product_card(product):
    url = product_url(product)
    return (f'<article class="fashion-product"><a class="fashion-product-link" href="{esc(url)}"><img src="{esc(product["image_url"])}" alt="{esc(product["brand"] + " " + product["title"])}" loading="lazy" decoding="async" width="480" height="600">'
            f'<div><p class="fashion-product-brand">{esc(product["brand"])}</p><h3>{esc(product["title"])}</h3>'
            + (f'<p class="fashion-card-subcategory">{esc(product["subcategory"])}</p>' if product.get('subcategory') else '') +
            '<span class="fashion-card-more">View product details →</span></div></a></article>')


def retailer_cta(product, css=''):
    return f'<a class="sat-fashion-cta {esc(css)}" href="{esc(product["affiliate_url"])}" target="_blank" rel="sponsored nofollow noopener">View on Nykaa <span aria-hidden="true">→</span><span class="visually-hidden"> (opens in a new tab)</span></a>'


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
    related = [item for item in products if item['id'] != product['id']]
    related.sort(key=lambda item: (item['category'] != product['category'], not item['featured'], item['id']))
    related_html = '<section class="fashion-related"><div><h2>You may also like</h2><a href="/fashion/">Explore the edit →</a></div><div class="fashion-products">' + ''.join(product_card(item) for item in related[:4]) + '</div></section>' if related else ''
    whatsapp = 'https://wa.me/?text=' + quote(product['brand'] + ' ' + product['title'] + '\n' + canonical, safe='')
    heart = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/></svg>'
    body = (f'<div class="container fashion-detail" data-fashion-detail data-product-id="{esc(product["id"])}" data-canonical="{esc(canonical)}" data-share-title="{esc(product["brand"] + " " + product["title"])}">'
            f'<nav class="fashion-detail-tools" aria-label="Product actions"><a href="/fashion/#{category[0]}">← <span>Back to {esc(category[1])}</span></a><div><button type="button" data-save-product aria-pressed="false" aria-label="Save this product" hidden>{heart}</button><a href="#fashion-share">Share ↗</a></div></nav>'
            '<div class="fashion-detail-layout"><div class="fashion-gallery">'
            f'<img class="fashion-main-image" src="{esc(product["image_url"])}" alt="{esc(product["brand"] + " " + product["title"])}" width="800" height="1000" data-main-product-image>' + thumbnails + '</div>'
            f'<div class="fashion-detail-copy"><p class="fashion-detail-brand">{esc(product["brand"])}</p><h1>{esc(product["title"])}</h1>'
            f'<p class="fashion-detail-category"><a href="/fashion/#{category[0]}">{esc(category[1])}</a>' + (f' · {esc(product["subcategory"])}' if product.get('subcategory') else '') + '</p>'
            f'<div class="fashion-detail-description">{description}</div>{facts_html}<div class="fashion-primary">{retailer_cta(product)}</div>'
            '<p class="fashion-affiliate-note">Affiliate disclosure: SAT may earn a commission if you purchase through this link, at no extra cost to you. <a href="/affiliate-disclosure/">Read the disclosure</a>.</p>'
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


def page(src, icon):
    products, problems = catalog(src)
    cards, sections = [], []
    for index, (slug, title, art, description, tips) in enumerate(SECTIONS, 1):
        cards.append(f'<a class="fashion-category" href="#{slug}"><span class="fashion-category-art">{icon({"art": art}, "fashion-category-icon")}</span><span class="fashion-category-number">0{index}</span><strong>{esc(title)}</strong><span>{esc(description)}</span><span class="fashion-category-explore">Explore →</span></a>')
        matching = [product for product in products if product['category'] == slug]
        contents = '<div class="fashion-products">' + ''.join(product_card(product) for product in matching) + '</div>' if matching else '<div class="fashion-style-advice"><p>What to look for</p><ul>' + ''.join(f'<li>{esc(tip)}</li>' for tip in tips) + '</ul></div>'
        sections.append(f'<section class="fashion-section" id="{slug}" aria-labelledby="{slug}-title"><header><p class="fashion-section-number">0{index}</p><h2 id="{slug}-title">{esc(title)}</h2><p>{esc(description)}</p></header>{contents}<a class="fashion-back" href="#fashion-categories">Back to styles ↑</a></section>')
    notice = '<p class="fashion-data-note">Product recommendations are being prepared. Retailer links and product images will appear only after approved Nykaa affiliate data is available.</p>' if not products else ''
    body = ('<div class="container fashion-page">{{breadcrumb}}<header class="fashion-introduction"><div><p class="sat-fashion-eyebrow">THE SAT FASHION EDIT</p><h1>Discover your style.</h1><p>Thoughtful fashion discovery across six everyday collections.</p><a class="sat-fashion-cta" href="#fashion-categories">Find your next favourite <span aria-hidden="true">→</span></a></div>'
            '<figure><img src="/images/fashion/sat-editorial-ivory.jpg" alt="Illustrative fashion editorial in a sandstone courtyard." width="1536" height="1024"><figcaption>Editorial visual · not a Nykaa product photograph</figcaption></figure></header>' + notice +
            '<nav class="fashion-categories" id="fashion-categories" aria-label="Fashion collections">' + ''.join(cards) + '</nav>' + ''.join(sections) + '</div>')
    return {'url': '/fashion/', 'title': 'The SAT Fashion Edit', 'description': 'Explore women’s kurtas, westernwear, Indianwear, footwear, active and sportswear, and bags with the SAT Fashion Edit.',
            'css': ['buttons', 'breadcrumb', 'fashion-gateway', 'fashion'], 'js': [], 'noindex': True,
            'breadcrumbs': [['Fashion Edit', '/fashion/']], 'updated': '2026-10-18', '_slug': 'fashion', '_body': body}, problems
