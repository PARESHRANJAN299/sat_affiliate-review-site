"""Add official Nykaa affiliate widgets to src/fashion/widgets.json.

Paste one or many iframe snippets (or bare widget URLs) from the Nykaa affiliate dashboard:

    python3 frontend/add_widget.py            # then paste, and finish with Ctrl-D
    pbpaste | python3 frontend/add_widget.py  # macOS: straight from the clipboard
    python3 frontend/add_widget.py --category womens-kurtas --dry-run < snippets.txt

Only the iframe's src URL is kept, unchanged. Everything is checked with the same rules as the site build
(host, path, affiliate id, product id); nothing is written unless every record is valid. Products already listed are skipped.
"""
import argparse
import html
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import fashion

DEFAULT_FILE = Path(__file__).resolve().parent / 'src' / 'fashion' / 'widgets.json'
URL = re.compile(r'https://affiliate\.nykaa\.com/[^\s"\'<>]+')


def extract(text):
    """Widget URLs in the order given, with HTML entities decoded and duplicates removed."""
    seen, out = set(), []
    for match in URL.findall(html.unescape(text)):
        if match not in seen:
            seen.add(match)
            out.append(match)
    return out


def size_of(text, url, key, default):
    """Width/height from the style of the iframe that carries this URL, else the default."""
    for tag in re.findall(r'<iframe[^>]*>', text):
        tag = html.unescape(tag)
        if url in tag:
            found = re.search(r'(?<![\w-])' + key + r'\s*:\s*(\d+)\s*px', tag)
            return int(found.group(1)) if found else default
    return default


def build_records(text, category, existing_ids):
    records, skipped, problems = [], [], []
    for url in extract(text):
        ids = parse_qs(urlsplit(url).query).get('product_id', [])
        if len(ids) != 1 or not re.fullmatch(r'[0-9]{1,12}', ids[0]):
            problems.append(f'no usable product_id in: {url[:90]}')
            continue
        product_id = ids[0]
        if product_id in existing_ids:
            skipped.append(product_id)
            continue
        existing_ids.add(product_id)
        records.append({'id': f'nykaa-{product_id}', 'product_id': product_id, 'category': category, 'source': 'nykaa-fashion', 'widget_url': url,
                        'width': size_of(text, url, 'width', 280), 'height': size_of(text, url, 'height', 360), 'active': True, 'featured': False})
    return records, skipped, problems


def add(text, category='womens-kurtas', path=DEFAULT_FILE, dry_run=False):
    """Returns (added, skipped, problems). Writes only when there are no problems and not dry_run."""
    path = Path(path)
    data = json.loads(path.read_text())
    existing = {w.get('product_id') for w in data['widgets']}
    records, skipped, problems = build_records(text, category, existing)
    if not records and not problems:
        return [], skipped, ['no new widget URLs found'] if not skipped else []
    candidate = {**data, 'widgets': data['widgets'] + records}
    problems += fashion.validate_widgets(candidate)[1]
    if problems:
        return [], skipped, problems
    if not dry_run:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, suffix='.tmp', delete=False, encoding='utf-8') as handle:
            handle.write(json.dumps(candidate, indent=2, ensure_ascii=False) + '\n')
        os.replace(handle.name, path)
    return [r['product_id'] for r in records], skipped, []


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--category', default='womens-kurtas', help='collection to add to (default: womens-kurtas)')
    parser.add_argument('--file', default=str(DEFAULT_FILE), help='widgets.json to update')
    parser.add_argument('--dry-run', action='store_true', help='check and report without writing')
    args = parser.parse_args(argv)
    text = sys.stdin.read()
    added, skipped, problems = add(text, fashion.category_slug(args.category) or args.category, args.file, args.dry_run)
    if problems:
        print('Nothing was written:', *problems, sep='\n  - ')
        return 1
    total = len(json.loads(Path(args.file).read_text())['widgets'])
    print(('Would add' if args.dry_run else 'Added') + f' {len(added)} widget(s): ' + (', '.join(added) or 'none'))
    if skipped:
        print(f'Skipped {len(skipped)} already listed: ' + ', '.join(skipped))
    print(f'widgets.json now lists {total} widget(s).' if not args.dry_run else f'widgets.json would list {total + len(added)} widget(s).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
