import json
import tempfile
import unittest
from pathlib import Path

try:
    from lab.engine import gallery_fingerprint, load_gallery
except ImportError:
    gallery_fingerprint = load_gallery = None


class CacheTests(unittest.TestCase):
    def test_corrupt_archive_does_not_prevent_baseline_or_rebuilding(self):
        from lab.engine import RetrievalEngine
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            (root / 'cache').mkdir()
            (root / 'one.jpg').write_bytes(b'image-content-for-fingerprint')
            item = {'id': 'one', 'file': 'one.jpg', 'title': '猫', 'caption': '猫', 'tags': ['猫']}
            (root / 'data/gallery.json').write_text(json.dumps({'items': [item]}), encoding='utf-8')
            (root / 'cache/image_index.npz').write_bytes(b'PK\x03\x04invalid zip archive')
            engine = RetrievalEngine(root)
            self.assertFalse(engine.index_ready)
            self.assertEqual(engine.search('猫', method='caption')['results'][0]['id'], 'one')

    def test_image_changes_invalidate_same_name_cache(self):
        self.assertIsNotNone(gallery_fingerprint, '缓存指纹尚未实现')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'one.bin').write_bytes(b'first')
            items = [{'id': 'one', 'file': 'one.bin'}]
            first = gallery_fingerprint(items, root, 'RN50-v1')
            (root / 'one.bin').write_bytes(b'other')
            self.assertNotEqual(first, gallery_fingerprint(items, root, 'RN50-v1'))
            self.assertNotEqual(first, gallery_fingerprint(items, root, 'RN50-v2'))

    def test_gallery_cannot_escape_project_or_repeat_ids(self):
        self.assertIsNotNone(load_gallery, '图库读取尚未实现')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            location = root / 'data/gallery.json'
            location.write_text(json.dumps({'items': [{'id': 'one', 'file': '../outside.jpg'}]}))
            with self.assertRaises(ValueError):
                load_gallery(root)


if __name__ == '__main__':
    unittest.main()
