"""Fashion destination. Published products require explicitly approved image/link hosts."""
import html
import json
import copy
from pathlib import Path
import re
from urllib.parse import urlsplit, quote, parse_qs

# (anchor, title, icon art, tagline, tips, layout). Layout picks the section composition in render_products().
SECTIONS = [
    ('womens-kurtas', 'Women’s Kurtas', 'kurtas-kurti-sets', 'Elegant Indian styles selected for everyday and occasion wear.', ['Compare fabric composition and care instructions.', 'Check the length, lining and size chart for the exact garment.'], 'feature'),
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
# SAT editorial artwork per collection (owner-supplied images); no stems means the original SVG fallback. Never retailer imagery.
ART = {'womens-kurtas': ('ivory-kurta',), 'westernwear': ('pink-dress', 'orange-dress-pillar'), 'indianwear': ('purple-saree-support',),
       'footwear': ('footwear-detail',), 'active-sports': ('white-tee-a',), 'bags': ()}
# Cutouts are 1122x1402 WebP; the ivory kurta photograph is a portrait JPEG crop. (extension, small width, large width, large height)
ART_FILES = {'ivory-kurta': ('jpg', 640, 836, 1024), 'ivory-banner': ('jpg', 828, 1536, 832), 'footwear-detail': ('webp', 480, 700, 442)}
# Wide banner photograph used above a collection's widget rail.
BANNER_STEMS = {'womens-kurtas': 'ivory-banner', 'footwear': 'white-tee-b'}
SITE_URL = 'https://sat.net.in'
ART_ALT = {'footwear-detail': 'Editorial image: close-up of white velcro trainers worn with blush joggers.',
           'ivory-kurta': 'Editorial image: a woman in an ivory floral kurta set with a dupatta, seated on sandstone steps.',
           'purple-saree-support': 'Editorial image: a woman seated on a stool in a purple saree with an embroidered blouse, her elbow resting on a stone pedestal.',
           'pink-dress': 'Editorial image: a woman in a pink ribbed dress with a black cardigan, holding a quilted black bag.',
           'orange-dress-pillar': 'Editorial image: a woman in an orange pinafore dress over a white top, with white trainers.',
           'white-tee-a': 'Editorial image: a woman sitting cross-legged in a white tee and blush joggers.',
           'white-tee-b': 'Editorial image: a woman sitting cross-legged in a white tee, blush joggers and white trainers.'}
# Easy-to-replace wording shown beside the first Nykaa widgets.
WIDGET_AFFILIATE_NOTE = 'This section contains affiliate links. SAT may earn a commission from qualifying purchases at no extra cost to you.'
EDIT_LABELS = {'womens-kurtas': 'THE KURTA EDIT', 'westernwear': 'THE WESTERN EDIT', 'footwear': 'THE FOOTWEAR EDIT', 'indianwear': 'THE INDIAN EDIT', 'active-sports': 'THE ACTIVE EDIT', 'bags': 'THE BAG EDIT'}
WIDGET_KEYS = {'id', 'product_id', 'category', 'source', 'widget_url', 'width', 'height', 'active', 'featured', 'collection', 'affiliate_url', 'audience', 'brand'}
# A category page can split its widgets by audience (a Women / Men toggle). Widgets without an audience count as women's.
AUDIENCES = (('women', 'Women'), ('men', 'Men'))
DEFAULT_AUDIENCE = 'women'
COLLECTION_KEYS = {'id', 'category', 'title', 'suggestions'}
CATEGORY_PAGE_KEYS = {'category', 'audience_toggle', 'groups'}
GROUP_KEYS = {'id', 'label', 'note', 'audience_toggle'}
WIDGET_URL_CHARS = re.compile(r'[A-Za-z0-9._~:/?&=%+-]+')
EMPTY_NOTE = 'Products will appear here once approved Nykaa catalogue items are added.'
BRANDS_EMPTY_NOTE = 'Brands will appear here once approved Nykaa catalogue items are added.'


def art_file(stem, large=False):
    ext, small, big, _ = ART_FILES.get(stem, ('webp', 640, 1122, 1402))
    return f'{MODEL_DIR}{stem}-{big if large else small}.{ext}'


def art_picture(slug, sizes, alt=False, stem=None, priority=False):
    """SAT editorial image(s) for a collection: responsive owner-supplied images, or the original SVG fallback."""
    stems = (stem,) if stem else ART.get(slug, ())
    if not stems:
        return f'<img class="fashion-art" src="{EDITORIAL_DIR}{slug}.svg" alt="" width="1200" height="1500" loading="lazy" decoding="async">'
    load = 'fetchpriority="high"' if priority else 'loading="lazy" decoding="async"'
    images = []
    for name in stems:
        ext, small, big, height = ART_FILES.get(name, ('webp', 640, 1122, 1402))
        width = ART_FILES[name][2] if name in ART_FILES else 1122
        images.append(f'<img class="fashion-art" src="{art_file(name)}" srcset="{art_file(name)} {small}w, {art_file(name, True)} {big}w" sizes="{sizes}" '
                      f'alt="{esc(ART_ALT[name]) if alt else ""}" width="{width}" height="{height}" {load}>')
    return ''.join(images)


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


def read_widgets(src):
    path = Path(src) / 'fashion' / 'widgets.json'
    return json.loads(path.read_text()) if path.is_file() else {'widgets': []}


def validate_collections(data):
    """Named scroll rails inside a category (for example a search-results group), each with an optional list of search suggestions."""
    items = data.get('collections', [])
    if not isinstance(items, list):
        return [], ['fashion widgets: collections must be a list']
    out, problems, ids = [], [], set()
    for entry in items:
        before = len(problems)
        if not isinstance(entry, dict) or set(entry) - COLLECTION_KEYS:
            problems.append('fashion widgets: each collection must be an object with only id, category, title and suggestions')
            continue
        cid = entry.get('id', '')
        if not isinstance(cid, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', cid) or cid in ids:
            problems.append(f'fashion collection {cid!r}: id must be unique lowercase words/numbers')
        ids.add(str(cid))
        category = category_slug(entry.get('category'))
        if not category:
            problems.append(f'fashion collection {cid}: unknown category')
        title, suggestions = entry.get('title'), entry.get('suggestions', [])
        if not isinstance(title, str) or not title.strip() or len(title) > 120:
            problems.append(f'fashion collection {cid}: a title of up to 120 characters is required')
        if not isinstance(suggestions, list) or len(suggestions) > 12 or any(not isinstance(v, str) or not v.strip() or len(v) > 120 for v in suggestions):
            problems.append(f'fashion collection {cid}: suggestions must be up to 12 short texts')
        if len(problems) == before:
            out.append({'id': cid, 'category': category, 'title': title.strip(), 'suggestions': [v.strip() for v in suggestions]})
    return out, problems


def validate_category_pages(data):
    """Per-category display settings. Today only audience_toggle (a Women / Men toggle inside that category's panel)."""
    entries = data.get('category_pages', [])
    if not isinstance(entries, list):
        return {}, ['fashion widgets: category_pages must be a list']
    out, problems = {}, []
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) - CATEGORY_PAGE_KEYS:
            problems.append('fashion widgets: each category setting must be an object with only ' + ', '.join(sorted(CATEGORY_PAGE_KEYS)))
            continue
        slug = category_slug(entry.get('category'))
        if not slug or slug in out:
            problems.append(f'fashion category setting {entry.get("category")!r}: unknown or duplicate category')
            continue
        if 'audience_toggle' in entry and not isinstance(entry['audience_toggle'], bool):
            problems.append(f'fashion category setting {slug}: audience_toggle must be true or false')
            continue
        setting = {'audience_toggle': True} if entry.get('audience_toggle') else {}
        if 'groups' in entry:
            groups, ids = entry['groups'], set()
            valid = isinstance(groups, list) and 2 <= len(groups) <= 8
            for group in (groups if valid else []):
                gid = group.get('id') if isinstance(group, dict) else None
                note = group.get('note', '') if isinstance(group, dict) else None
                if (not isinstance(group, dict) or set(group) - GROUP_KEYS or not isinstance(gid, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', gid) or gid in ids
                        or not isinstance(group.get('label'), str) or not group['label'].strip() or len(group['label']) > 60 or not isinstance(note, str) or len(note) > 90
                        or not isinstance(group.get('audience_toggle', False), bool)):
                    valid = False
                    break
                ids.add(gid)
            if not valid:
                problems.append(f'fashion category setting {slug}: groups must be 2 to 8 entries with a unique lowercase id, a label (up to 60 characters) and an optional note')
                continue
            setting['groups'] = [{'id': g['id'], 'label': g['label'].strip(), 'note': g.get('note', '').strip(), 'audience_toggle': bool(g.get('audience_toggle'))} for g in groups]
        out[slug] = setting
    return out, problems


def validate_widgets(data):
    """Validate official Nykaa affiliate widget records. Only an exact, allowlisted widget URL is accepted, never HTML."""
    if not isinstance(data, dict) or not isinstance(data.get('widgets'), list):
        return [], ['fashion widgets: root must be an object with a widgets list']
    host, path, affiliate = data.get('allowed_widget_host'), data.get('allowed_widget_path'), data.get('allowed_affiliate_id')
    if data['widgets'] and not all(isinstance(v, str) and v for v in (host, path, affiliate)):
        return [], ['fashion widgets: allowed_widget_host, allowed_widget_path and allowed_affiliate_id are required']
    collections, problems = validate_collections(data)
    settings, setting_problems = validate_category_pages(data)
    problems = problems + setting_problems
    link_hosts = data.get('allowed_product_link_hosts', [])
    if not isinstance(link_hosts, list) or any(not isinstance(h, str) or not re.fullmatch(r'[a-z0-9.-]+', h) for h in link_hosts):
        return [], ['fashion widgets: allowed_product_link_hosts must be exact lowercase hostnames']
    known = {c['id']: c['category'] for c in collections}
    active, ids = [], set()
    for record in data['widgets']:
        before = len(problems)
        if not isinstance(record, dict):
            problems.append('fashion widgets: each widget must be an object')
            continue
        wid = record.get('id', '')
        extra = sorted(set(record) - WIDGET_KEYS)
        if extra:
            problems.append(f'fashion widget {wid!r}: unsupported fields {extra} (store the widget URL, never HTML)')
        if not isinstance(wid, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', wid) or wid in ids:
            problems.append(f'fashion widget {wid!r}: id must be unique lowercase words/numbers')
        ids.add(str(wid))
        if not isinstance(record.get('active'), bool) or not isinstance(record.get('featured'), bool):
            problems.append(f'fashion widget {wid}: active and featured must be booleans')
        if record.get('active') is not True:
            continue
        widget = copy.deepcopy(record)
        if not isinstance(widget.get('product_id'), str) or not re.fullmatch(r'[0-9]{1,12}', widget['product_id']):
            problems.append(f'fashion widget {wid}: product_id must be digits')
        widget['category'] = category_slug(widget.get('category'))
        if not widget['category']:
            problems.append(f'fashion widget {wid}: unknown category')
        link = widget.get('affiliate_url')
        if link is not None and not approved_url(link, link_hosts):
            problems.append(f'fashion widget {wid}: affiliate_url requires https on an approved Nykaa product-link host (allowed_product_link_hosts)')
        group_ids = [g['id'] for g in settings.get(widget['category'], {}).get('groups', [])]
        brand = widget.get('brand')
        if group_ids and brand not in group_ids:
            problems.append(f'fashion widget {wid}: this category is split into groups, so brand must be one of {group_ids}')
        elif not group_ids and brand is not None:
            problems.append(f'fashion widget {wid}: brand is only allowed in a category that defines groups')
        audience = widget.get('audience')
        if audience is not None and audience not in dict(AUDIENCES):
            problems.append(f'fashion widget {wid}: audience must be one of {sorted(dict(AUDIENCES))}')
        group = widget.get('collection')
        if group is not None and (not isinstance(group, str) or known.get(group) != widget['category']):
            problems.append(f'fashion widget {wid}: collection must be a defined collection of the same category')
        url = widget.get('widget_url')
        if not isinstance(url, str) or not WIDGET_URL_CHARS.fullmatch(url):
            problems.append(f'fashion widget {wid}: widget_url has unsupported characters')
        else:
            parts = urlsplit(url)
            query = parse_qs(parts.query, keep_blank_values=True)
            if not (parts.scheme == 'https' and parts.hostname == host and parts.port in (None, 443) and not parts.username and not parts.fragment and parts.path == path):
                problems.append(f'fashion widget {wid}: widget_url must be https://{host}{path}')
            elif query.get('affiliate_id') != [affiliate] or query.get('product_id') != [widget.get('product_id')] or query.get('store') != ['nykaa_fashion']:
                problems.append(f'fashion widget {wid}: widget_url must carry the approved affiliate_id, this product_id and store=nykaa_fashion')
        for key, default in (('width', 280), ('height', 360)):
            widget.setdefault(key, default)
            if not isinstance(widget[key], int) or isinstance(widget[key], bool) or not 100 <= widget[key] <= 600:
                problems.append(f'fashion widget {wid}: {key} must be a whole number from 100 to 600')
        if len(problems) == before:
            active.append(widget)
    return sorted(active, key=lambda item: not item['featured']), problems  # stable: featured first, otherwise the order in widgets.json


def widgets(src):
    try:
        return validate_widgets(read_widgets(src))
    except (OSError, ValueError) as exc:
        return [], [f'fashion widgets: cannot read widget data ({exc})']


def category_page_config(src):
    try:
        return validate_category_pages(read_widgets(src))[0]
    except (OSError, ValueError):
        return {}


def widget_collections(src):
    try:
        return validate_collections(read_widgets(src))[0]
    except (OSError, ValueError):
        return []


def get_widgets_by_category(items, category):
    return [item for item in items if item['category'] == category]


def widget_id(widget):
    return 'pick-' + widget['product_id']


def widget_shell(widget, title='', site_url=SITE_URL, page_path='/fashion/'):
    """SAT wrapper around the official Nykaa iframe. The iframe URL is exactly the stored, validated widget_url; its content stays Nykaa's.
    The optional 'Get it on Nykaa' button uses the owner-supplied affiliate product link unchanged. Share buttons use a SAT page and card
    (an anchor), never the Nykaa affiliate link."""
    link = site_url.rstrip('/') + page_path + '#' + widget_id(widget)
    get = ''
    if widget.get('affiliate_url'):
        get = (f'<a class="nykaa-get" href="{esc(widget["affiliate_url"])}" target="_blank" rel="sponsored nofollow noopener">Get it on Nykaa '
               '<span aria-hidden="true">→</span><span class="visually-hidden"> (opens in a new tab)</span></a>')
    return (f'<article class="nykaa-product-shell" id="{widget_id(widget)}" data-product-id="{esc(widget["product_id"])}">'
            f'<iframe src="{esc(widget["widget_url"])}" title="Nykaa Fashion product" width="{widget["width"]}" height="{widget["height"]}" loading="lazy" '
            f'style="height:{widget["height"]}px;width:{widget["width"]}px;overflow:hidden;"></iframe>{get}'
            f'<div class="nykaa-share" role="group" aria-label="Share this pick">'
            f'<button type="button" data-copy-pick data-url="{esc(link)}" hidden>Copy link</button>'
            f'<button type="button" data-share-pick data-url="{esc(link)}" data-title="{esc(title)}" hidden>Share</button></div></article>')


def widget_group(head, items, label, title, site_url, page_path='/fashion/'):
    """Every widget in the list as a grid (lazy-loaded). The official Nykaa cards stay Nykaa's; SAT only wraps them."""
    return (f'<div class="nykaa-group" data-rail-group>{head}<div data-widget-grid class="nykaa-grid" aria-label="{esc(label)}">'
            + ''.join(widget_shell(item, title, site_url, page_path) for item in items) + '</div><p class="visually-hidden" role="status" data-widget-status></p></div>')


def titled_lists(head, members, label, title, site_url, collections, page_path='/fashion/'):
    """Products of one panel. Products that belong to a named collection (for example "Search results for Nike Shoes") are listed under that
    collection's title, in the order the collections are defined; products without one follow in a plain list. With no collections in use this is
    exactly the plain grid."""
    used = [(c, [m for m in members if m.get('collection') == c['id']]) for c in collections]
    used = [(c, items) for c, items in used if items]
    if not used:
        return widget_group(head, members, label, title, site_url, page_path)
    tag = 'h4' if head else 'h3'
    parts = [head] if head else []
    for c, items in used:
        parts.append(widget_group(f'<{tag} class="nykaa-results-title nykaa-collection-title">{esc(c["title"])}</{tag}>', items, f'{c["title"]} from Nykaa Fashion', title, site_url, page_path))
    rest = [m for m in members if not m.get('collection')]
    if rest:
        parts.append(widget_group('', rest, label, title, site_url, page_path))
    return ''.join(parts)


def audience_split(slug, title, items, site_url, page_path='/fashion/', prefix=None, collections=()):
    """A Women / Men toggle inside a category panel, one list per audience (widgets without an audience count as women's)."""
    counts = {key: sum(1 for item in items if item.get('audience', DEFAULT_AUDIENCE) == key) for key, _ in AUDIENCES}
    first = max(AUDIENCES, key=lambda audience: counts[audience[0]])[0]  # open on the list with the most products (the first one on a tie)
    tabs, panels = [], []
    for key, name in AUDIENCES:
        members = [item for item in items if item.get('audience', DEFAULT_AUDIENCE) == key]
        current = ' aria-current="true"' if key == first else ''
        panel_id = f'{prefix or slug}-{key}'
        tabs.append(f'<a href="#{panel_id}" data-audience-tab="{key}"{current}>{esc(name)} <span>{len(members)}</span></a>')
        heading = f'{name}’s {title}'
        head = f'<h3 class="nykaa-results-title">{esc(heading)}</h3>'
        inside = (titled_lists(head, members, f'{heading} from Nykaa Fashion', title, site_url, collections, page_path) if members else
                  f'{head}<p class="fashion-empty-note nykaa-audience-empty">{esc(name)}’s picks will appear here once approved Nykaa catalogue items are added.</p>')
        panels.append(f'<section class="nykaa-panel" id="{panel_id}" data-audience-panel="{key}" aria-label="{esc(heading)}">{inside}</section>')
    return f'<div data-audience-group><nav class="nykaa-audience" aria-label="Show {esc(title)} for">' + ''.join(tabs) + '</nav>' + ''.join(panels) + '</div>'


def brand_split(slug, title, items, groups, site_url, audience_toggle=False, collections=()):
    """audience_toggle is the category default; an option can switch its own Women / Men toggle on (its 'audience_toggle')."""
    """Brand options inside a category panel (for example U.S. Polo Assn., Nike, Puma, Affordable Indian brands). Each option shows only its own
    products, with the Women / Men toggle inside it where the category has one. Opens on the first option that has products."""
    counts = {g['id']: sum(1 for item in items if item.get('brand') == g['id']) for g in groups}
    first = next((g['id'] for g in groups if counts[g['id']]), groups[0]['id'])
    tabs, panels = [], []
    for g in groups:
        members = [item for item in items if item.get('brand') == g['id']]
        current = ' aria-current="true"' if g['id'] == first else ''
        tabs.append(f'<a href="#{slug}-{g["id"]}" data-brand-tab="{g["id"]}"{current}>{esc(g["label"])} <span>{len(members)}</span></a>')
        line = f'<p class="nykaa-brand-line"><strong>{esc(g["label"])}</strong>' + (f' <span>{esc(g["note"])}</span>' if g['note'] else '') + '</p>'
        if not members:
            inside = f'{line}<p class="fashion-empty-note nykaa-audience-empty">{esc(g["label"])} picks will appear here once approved Nykaa catalogue items are added.</p>'
        elif audience_toggle or g.get('audience_toggle'):
            inside = line + audience_split(slug, title, members, site_url, prefix=f'{slug}-{g["id"]}', collections=collections)
        else:
            inside = line + titled_lists('', members, f'{g["label"]} from Nykaa Fashion', title, site_url, collections)
        panels.append(f'<section class="nykaa-brandpanel" id="{slug}-{g["id"]}" data-brand-panel="{g["id"]}" aria-label="{esc(g["label"])}">{inside}</section>')
    return f'<div data-brand-set><nav class="nykaa-brands-nav" aria-label="Choose a {esc(title)} brand">' + ''.join(tabs) + '</nav>' + ''.join(panels) + '</div>'


def render_widgets(slug, items, title='', site_url=SITE_URL, config=None, collections=()):
    """A collection's panel on /fashion/: a wide SAT editorial banner, the replaceable affiliate note and EVERY official Nykaa widget of the
    collection, split by brand option and/or Women / Men where the category is set up that way. There is no separate page per category."""
    config = config or {}
    banner = f'<figure class="fashion-widget-banner fashion-tint-{slug}">{art_picture(slug, "(min-width: 900px) 1232px, 100vw", stem=BANNER_STEMS.get(slug))}</figure>'
    note = f'<p class="fashion-widget-note" data-disclosure="temporary">{esc(WIDGET_AFFILIATE_NOTE)}</p>'
    if config.get('groups'):
        listing = brand_split(slug, title, items, config['groups'], site_url, bool(config.get('audience_toggle')), collections)
    elif config.get('audience_toggle'):
        listing = audience_split(slug, title, items, site_url, collections=collections)
    else:
        listing = titled_lists('', items, f'{title} picks from Nykaa Fashion', title, site_url, collections)
    return banner + note + listing


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
            'css': ['buttons', 'breadcrumb', 'fashion-gateway', 'fashion-art', 'fashion', 'fashion-product'], 'js': ['fashion-product'], 'theme': 'fashion-detail',
            'noindex': True, 'canonical_always': True, 'breadcrumbs': [['Fashion Edit', '/fashion/'], [category[1], '/fashion/#' + category[0]], [product['title'], url]],
            'updated': product.get('updated', '2026-10-18'), '_slug': 'fashion-product-' + product['slug'], '_body': body}


def pages(src, icon, site_url):
    products, errors = catalog(src)
    errors = errors + widgets(src)[1]
    landing, _ = page(src, icon, site_url)
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


def discover_tiles(products, prefix='/fashion/'):
    """The Discover Your Style tiles: SAT editorial artwork (or an approved product photo) per collection, each opening that collection."""
    tiles = []
    for slug, title, art, description, tips, layout in SECTIONS:
        matching = get_products_by_category(products, slug)
        if matching:
            visual = f'<img class="fashion-photo" src="{esc(matching[0]["image_url"])}" alt="" loading="lazy" decoding="async" width="800" height="1000">'
        else:
            visual = art_picture(slug, '(min-width: 900px) 34vw, 62vw')
        tiles.append(f'<a class="fashion-category fashion-category-{slug} fashion-tint-{slug}" href="{prefix}#{slug}">{visual}'
                     f'<span class="fashion-category-label"><strong>{esc(title)}</strong><em>{esc(description)}</em><span class="fashion-category-arrow" aria-hidden="true">→</span></span></a>')
    return ''.join(tiles)


def discover_html(src, prefix='/fashion/'):
    """The Discover Your Style mosaic for the home page; every tile opens that collection on /fashion/."""
    products, _ = catalog(src)
    return ('<section class="fashion-discover" aria-labelledby="fashion-discover-title"><h2 id="fashion-discover-title">Discover Your Style</h2>'
            '<nav class="fashion-categories" aria-label="Fashion collections">' + discover_tiles(products, prefix) + '</nav></section>')


def page(src, icon, site_url=SITE_URL):
    products, problems = catalog(src)
    live_widgets, widget_problems = widgets(src)
    live_collections = widget_collections(src)
    page_configs = category_page_config(src)
    problems = problems + widget_problems
    first_live = next((slug for slug, *_ in SECTIONS if get_widgets_by_category(live_widgets, slug)), SECTIONS[0][0])  # open on the first collection that has products
    tabs, sections = [], []
    for index, (slug, title, art, description, tips, layout) in enumerate(SECTIONS, 1):
        matching = get_products_by_category(products, slug)
        current = ' aria-current="true"' if slug == first_live else ''
        tabs.append(f'<a href="#{slug}" data-category-tab="{slug}"{current}>{esc(title)}</a>')
        here = get_widgets_by_category(live_widgets, slug)
        if here:
            contents = render_widgets(slug, here, title, site_url, page_configs.get(slug, {}), [c for c in live_collections if c['category'] == slug])
        else:
            contents = render_products(layout, matching) if matching else render_empty(slug, tips, layout, icon)
            if page_configs.get(slug, {}).get('groups'):  # the brand options are visible even before the first product is added
                contents += brand_split(slug, title, [], page_configs[slug]['groups'], site_url, bool(page_configs[slug].get('audience_toggle')))
        label = EDIT_LABELS.get(slug)
        marker = f'<p class="sat-fashion-eyebrow">{esc(label)} <span aria-hidden="true"></span></p>' if here and label else ''
        sections.append(f'<section class="fashion-section fashion-section-{layout}{" fashion-section-widgets" if here else ""}" id="{slug}" data-category-panel="{slug}" aria-labelledby="{slug}-title">'
                        f'<header>{marker}<h2 id="{slug}-title">{esc(title)}</h2><p>{esc(description)}</p></header>{contents}</section>')
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
    body = ('<div class="container fashion-page"><header class="fashion-switch-head"><h1>Discover Your Style</h1></header>'
            '<nav class="fashion-switch" id="fashion-categories" aria-label="Choose a fashion category">' + ''.join(tabs) + '</nav>'
            + ''.join(sections) + brands_html + banner + trust + '</div>')
    return {'url': '/fashion/', 'title': 'The SAT Fashion Edit', 'description': 'Explore women’s kurtas, westernwear, Indianwear, footwear, active and sportswear, and bags with the SAT Fashion Edit.',
            'css': ['buttons', 'breadcrumb', 'fashion-gateway', 'fashion-art', 'fashion'], 'js': ['fashion-widgets'], 'noindex': True,
            'breadcrumbs': [['Fashion Edit', '/fashion/']], 'updated': '2026-10-18', '_slug': 'fashion', '_body': body}, problems
