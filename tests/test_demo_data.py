import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DemoDataTests(unittest.TestCase):
    def test_chinese_labels_survive_data_generation(self):
        gallery = json.loads((ROOT / 'data/gallery.json').read_text(encoding='utf-8'))['items']
        queries = json.loads((ROOT / 'data/queries.json').read_text(encoding='utf-8'))['queries']
        for item in gallery:
            self.assertRegex(item['title'], r'[\u4e00-\u9fff]', item['id'] + ' 标题丢失中文')
            self.assertRegex(item['caption'], r'[\u4e00-\u9fff]', item['id'] + ' 描述丢失中文')
        for query in queries:
            self.assertRegex(query['text'], r'[\u4e00-\u9fff]', query['id'] + ' 查询丢失中文')


if __name__ == '__main__':
    unittest.main()
