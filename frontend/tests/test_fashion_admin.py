"""Private local product saves: source approvals, stable links and rollback."""
import copy
import http.client
import threading
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fashion
from fashion_admin import EditorError, Store, handler


class AdminStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.src = Path(self.temp.name)
        (self.src/'fashion').mkdir()
        self.config = {'products':[], 'approved_image_hosts':[], 'approved_affiliate_hosts':[]}
        self.write_config()
        self.builds = 0
        def build(): self.builds += 1
        self.store = Store(self.src, build)
        self.product = {'id':'nykaa-one', 'slug':'cotton-kurta', 'title':'Cotton Kurta', 'brand':'Provided brand', 'category':'womens-kurtas', 'subcategory':'Kurtas', 'description':'Provided description', 'attributes':{'Material':'Cotton'}, 'image_url':'https://approved-images.example/one.jpg', 'affiliate_url':'https://approved-affiliate.example/product?a=1&b=2', 'active':False, 'featured':False}

    def write_config(self): (self.src/'fashion/catalog.json').write_text(json.dumps(self.config))
    def save(self, product=None, revision=None):
        return self.store.save({'revision':revision or self.store.state()['revision'], 'product':product or self.product})

    def test_draft_save_creates_one_record_and_no_public_page(self):
        result=self.save()
        self.assertIsNone(result['url'])
        self.assertEqual(self.builds,1)
        self.assertTrue((self.src/'fashion/products/nykaa-one.json').is_file())
        self.assertEqual(fashion.catalog(self.src),( [], [] ))

    def test_activation_requires_approved_sources_then_generates_its_url(self):
        self.product['active']=True
        with self.assertRaises(EditorError): self.save()
        self.assertEqual(self.builds,0)
        self.config.update({'approved_image_hosts':['approved-images.example'],'approved_affiliate_hosts':['approved-affiliate.example']})
        self.write_config()
        result=self.save()
        self.assertEqual(result['url'],'/fashion/products/cotton-kurta/')
        self.assertEqual(fashion.catalog(self.src)[0][0]['affiliate_url'],self.product['affiliate_url'])

    def test_stale_edits_and_slug_changes_are_rejected(self):
        revision=self.store.state()['revision'];self.save()
        with self.assertRaises(EditorError) as error:self.save(revision=revision)
        self.assertEqual(error.exception.status,409)
        changed=copy.deepcopy(self.product);changed['slug']='different-url'
        with self.assertRaises(EditorError):self.save(changed)

    def test_duplicate_slug_and_unsafe_id_are_rejected(self):
        self.save()
        duplicate=copy.deepcopy(self.product);duplicate['id']='nykaa-two'
        with self.assertRaises(EditorError):self.save(duplicate)
        duplicate['id']='../outside'
        with self.assertRaises(EditorError):self.save(duplicate)

    def test_failed_build_rolls_back_new_product(self):
        def fail():raise RuntimeError('deliberate isolated test failure')
        self.store.rebuild=fail
        with self.assertRaises(EditorError):self.save()
        self.assertFalse((self.src/'fashion/products/nykaa-one.json').exists())

    def test_failed_edit_restores_previous_product(self):
        self.save();old=(self.src/'fashion/products/nykaa-one.json').read_bytes()
        def fail():raise RuntimeError('deliberate isolated test failure')
        self.store.rebuild=fail
        changed=copy.deepcopy(self.product);changed['title']='Changed'
        with self.assertRaises(EditorError):self.save(changed)
        self.assertEqual((self.src/'fashion/products/nykaa-one.json').read_bytes(),old)


class AdminHTTPTests(unittest.TestCase):
    setUp = AdminStoreTests.setUp
    write_config = AdminStoreTests.write_config
    def test_http_origin_host_and_csrf_checks_before_writes(self):
        root=self.src/'app';(root/'admin').mkdir(parents=True)
        (root/'dist').mkdir();(root/'admin/fashion.html').write_text('<html>{{csrf}}</html>')
        server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None)
        host='127.0.0.1:'+str(server.server_port)
        server.RequestHandlerClass=handler(self.store,'private-test-token',host,root)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def request(headers):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            body=json.dumps({'revision':self.store.state()['revision'],'product':self.product})
            connection.request('POST','/admin/api/products',body,{**{'Content-Type':'application/json'},**headers})
            response=connection.getresponse();result=(response.status,json.loads(response.read()));connection.close();return result
        good={'Host':host,'Origin':'http://'+host,'X-CSRF-Token':'private-test-token'}
        for bad in [{'Origin':'https://untrusted.example'},{'Host':'untrusted.example'},{'X-CSRF-Token':'wrong'}]:
            code,_=request({**good,**bad});self.assertEqual(code,403)
        self.assertEqual(self.builds,0)
        code,result=request(good);self.assertEqual(code,200);self.assertIsNone(result['url']);self.assertEqual(self.builds,1)


if __name__=='__main__':unittest.main()
