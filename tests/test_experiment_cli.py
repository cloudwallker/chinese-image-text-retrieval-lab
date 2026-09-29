import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


class ExperimentCliTests(unittest.TestCase):
    def test_caption_only_never_calls_model_even_when_index_is_cached(self):
        source = Path(__file__).resolve().parents[1] / 'scripts/run_experiment.py'
        spec = importlib.util.spec_from_file_location('experiment_cli', source)
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)

        class CachedEngine:
            index_ready = True
            model_name = 'model-must-not-run'
            items = [{'id': 'a'}]

            def __init__(self, root):
                pass

            def prepare(self, progress):
                raise AssertionError('caption-only 不得准备模型')

            def search(self, text, method, top_k, weight):
                if method != 'caption':
                    raise AssertionError('caption-only 不得调用图文模型')
                return {'results': [{'id': 'a', 'score': 1.0}]}

        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir()
            query = {'id': 'q', 'text': '猫', 'relevant_ids': ['a'], 'split': 'test'}
            (root / 'data/queries.json').write_text(json.dumps({'queries': [query]}), encoding='utf-8')
            with patch.object(cli, 'ROOT', root), patch.object(cli, 'RetrievalEngine', CachedEngine), \
                    patch('sys.argv', ['run_experiment.py', '--caption-only']), redirect_stdout(StringIO()):
                cli.main()
            report = json.loads((root / 'cache/report.json').read_text(encoding='utf-8'))
            self.assertEqual([method['method'] for method in report['methods']], ['caption'])


if __name__ == '__main__':
    unittest.main()
