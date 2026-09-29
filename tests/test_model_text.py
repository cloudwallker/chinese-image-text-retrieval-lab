import unittest
from collections import OrderedDict
from types import SimpleNamespace
from lab.engine import ChineseClipEncoder


class ModelTextTests(unittest.TestCase):
    def test_overlong_model_query_is_rejected_before_inference(self):
        encoder = ChineseClipEncoder.__new__(ChineseClipEncoder)
        encoder.text_cache = OrderedDict()
        encoder.clip = SimpleNamespace(_tokenizer=SimpleNamespace(tokenize=list))
        for suffix in ('红色', '蓝色'):
            with self.assertRaisesRegex(ValueError, '50'):
                encoder.encode_text('杯子' * 30 + suffix)


if __name__ == '__main__':
    unittest.main()
