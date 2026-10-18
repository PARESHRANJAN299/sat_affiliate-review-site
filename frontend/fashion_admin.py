"""Private local Fashion editor. Run: python3 frontend/fashion_admin.py"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import argparse
import datetime
import hashlib
import html
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import uuid

import fashion

ROOT = Path(__file__).resolve().parent


class EditorError(Exception):
    def __init__(self, message, status=422):
        self.status = status
        super().__init__(message)


class Store:
    def __init__(self, src, rebuild):
        self.src = Path(src)
        self.rebuild = rebuild
        self.lock = threading.RLock()

    def state(self):
        with self.lock:
            data = fashion.read_data(self.src)
            digest = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            return {'revision': digest, 'products': data['products'], 'categories': [{'id': item[0], 'name': item[1]} for item in fashion.SECTIONS],
                    'approved_image_hosts': data['approved_image_hosts'], 'approved_affiliate_hosts': data['approved_affiliate_hosts']}

    def save(self, payload):
        with self.lock:
            state = self.state()
            if payload.get('revision') != state['revision']:
                raise EditorError('The catalogue changed in another session. Reload the catalogue before saving.', 409)
            raw = payload.get('product')
            if not isinstance(raw, dict):
                raise EditorError('A product object is required.')
            allowed = {'id', 'slug', 'brand', 'title', 'category', 'subcategory', 'image_url', 'affiliate_url', 'description', 'attributes', 'gallery', 'featured', 'active'}
            product = {key: value for key, value in raw.items() if key in allowed}
            product['id'] = product.get('id') or 'nykaa-' + uuid.uuid4().hex[:12]
            product['updated'] = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
            pid = product['id']
            if not isinstance(pid, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', pid) or len(pid) > 120:
                raise EditorError('Use a valid product ID.')
            if not product.get('slug'):
                raise EditorError('A stable URL slug is required.')
            data = fashion.read_data(self.src)
            previous = next((item for item in data['products'] if item.get('id') == pid), None)
            if previous and previous.get('slug') != product['slug']:
                raise EditorError('This product already has a URL. Its slug cannot be changed here.')
            products_dir = self.src / 'fashion/products'
            products_dir.mkdir(exist_ok=True)
            path = products_dir / (pid + '.json')
            if previous and not path.is_file():
                raise EditorError('This record is stored inline in catalog.json. Move it to a product file before editing.')
            data['products'] = [item for item in data['products'] if item.get('id') != pid] + [product]
            _, errors = fashion.validate(data)
            if errors:
                raise EditorError('\n'.join(errors))
            old = path.read_bytes() if path.exists() else None
            try:
                with tempfile.NamedTemporaryFile(dir=products_dir, suffix='.tmp', delete=False) as file:
                    temporary = Path(file.name)
                    file.write((json.dumps(product, ensure_ascii=False, indent=2) + '\n').encode())
                os.replace(temporary, path)
                self.rebuild()
            except Exception as exc:
                if 'temporary' in locals():
                    temporary.unlink(missing_ok=True)
                if old is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(old)
                try:
                    self.rebuild()
                except Exception:
                    pass
                raise EditorError('The local build failed; the product change was rolled back. ' + str(exc), 500) from exc
            return {'product': product, 'url': fashion.product_url(product) if product['active'] else None,
                    'revision': self.state()['revision'], 'message': 'Saved and rebuilt locally. Nothing has been pushed or published.'}


def handler(store, token, host_header, root=ROOT):
    class Editor(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root / 'dist'), **kwargs)

        def valid_host(self):
            return self.headers.get('Host') == host_header

        def json_response(self, code, body):
            data = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def list_directory(self, path):
            self.send_error(404)
            return None

        def do_GET(self):
            if not self.valid_host():
                self.json_response(403, {'error': 'Use the local editor address.'})
                return
            route = urlsplit(self.path).path
            if route == '/admin/api/state':
                self.json_response(200, store.state())
            elif route in ('/admin', '/admin/'):
                page = (root / 'admin/fashion.html').read_text().replace('{{csrf}}', html.escape(token, quote=True)).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(page)))
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
                self.send_header('X-Frame-Options', 'DENY')
                self.end_headers()
                self.wfile.write(page)
            elif route.startswith('/admin/'):
                self.send_error(404)
            else:
                super().do_GET()

        def do_POST(self):
            if not self.valid_host() or self.headers.get('Origin') != 'http://' + host_header or not secrets.compare_digest(self.headers.get('X-CSRF-Token', ''), token):
                self.json_response(403, {'error': 'Open the local editor and try again.'})
                return
            if urlsplit(self.path).path != '/admin/api/products':
                self.send_error(404)
                return
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                self.json_response(415, {'error': 'JSON is required.'})
                return
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 131072:
                    raise ValueError('Invalid request size.')
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError('A JSON object is required.')
                self.json_response(200, store.save(payload))
            except EditorError as exc:
                self.json_response(exc.status, {'error': str(exc)})
            except (ValueError, UnicodeDecodeError) as exc:
                self.json_response(400, {'error': str(exc)})

    return Editor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8790)
    args = parser.parse_args()
    def rebuild():
        result = subprocess.run([sys.executable, str(ROOT / 'build.py')], cwd=ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'}, capture_output=True, text=True, timeout=120)
        if result.returncode:
            errors = [line for line in (result.stdout + result.stderr).splitlines() if 'ERROR' in line]
            raise RuntimeError('\n'.join(errors[:8]) or 'See the local build output.')
    if not (ROOT / 'dist/index.html').is_file():
        rebuild()
    host = '127.0.0.1:' + str(args.port)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(Store(ROOT / 'src', rebuild), secrets.token_urlsafe(32), host))
    print('Private local Fashion editor: http://' + host + '/admin/', flush=True)
    print('Saves rebuild local previews only. Publishing is a separate step.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == '__main__':
    main()
