import tempfile
import unittest
from pathlib import Path

try:
    from lab.server import safe_static_path, validate_search
except ImportError:
    safe_static_path = validate_search = None


class ServerTests(unittest.TestCase):
    def test_private_api_rejects_nonlocal_host(self):
        from lab import server
        validator = getattr(server, 'validate_host', None)
        self.assertIsNotNone(validator, '本地 Host 校验尚未实现')
        validator('127.0.0.1:8765', 8765)
        validator('localhost:8765', 8765)
        for host in (None, '', 'other-site.example:8765', '127.0.0.1:8766', '127.0.0.1:8765@evil.example'):
            with self.assertRaises(ValueError):
                validator(host, 8765)

    def test_only_public_assets_can_be_served(self):
        self.assertIsNotNone(safe_static_path, '静态资源保护尚未实现')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'web').mkdir()
            (root / 'web/index.html').write_text('demo')
            self.assertEqual(safe_static_path(root, '/'), root / 'web/index.html')
            for url in ['/../models/secret.pt', '/%2e%2e/README.md', '/models/weights.pt', '/data/gallery.json', '/web/../README.md']:
                with self.assertRaises(ValueError):
                    safe_static_path(root, url)

    def test_bad_search_inputs_are_errors_not_coercions(self):
        self.assertIsNotNone(validate_search, '请求校验尚未实现')
        good = {'query': '鸟', 'method': 'caption', 'top_k': 5, 'negative_weight': .4}
        self.assertEqual(validate_search(good)['query'], '鸟')
        for patch in [{'query': ''}, {'query': 'a' * 301}, {'top_k': True}, {'top_k': 0}, {'top_k': 500}, {'negative_weight': float('nan')}, {'method': 'fake'}]:
            with self.assertRaises(ValueError):
                validate_search(dict(good, **patch))


if __name__ == '__main__':
    unittest.main()
