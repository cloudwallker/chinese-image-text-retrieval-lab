import unittest

try:
    from lab.evaluation import metrics, validate_queries
except ImportError:
    metrics = validate_queries = None


class EvaluationTests(unittest.TestCase):
    def test_multiple_positives_have_distinct_hit_recall_and_ap(self):
        self.assertIsNotNone(metrics, '指标函数尚未实现')
        result = metrics(['b', 'x', 'a'], ['a', 'b'], 3)
        self.assertEqual(result['hit'], 1.)
        self.assertEqual(result['recall'], 1.)
        self.assertAlmostEqual(result['ap'], (1. + 2. / 3.) / 2.)
        self.assertEqual(metrics(['b', 'x', 'a'], ['a', 'b'], 1)['recall'], .5)

    def test_no_match_is_zero_and_duplicates_are_invalid(self):
        self.assertIsNotNone(metrics, '指标函数尚未实现')
        self.assertEqual(metrics(['x', 'y'], ['a'], 2), {'hit': 0., 'recall': 0., 'ap': 0.})
        with self.assertRaises(ValueError):
            metrics(['a', 'a'], ['a'], 2)
        with self.assertRaises(ValueError):
            metrics(['a'], [], 1)

    def test_unknown_positive_is_not_silently_dropped(self):
        self.assertIsNotNone(validate_queries, '查询校验尚未实现')
        with self.assertRaises(ValueError):
            validate_queries([{'id': 'q', 'text': '鸟', 'relevant_ids': ['absent'], 'split': 'test', 'category': 'object'}], ['a'])
        validate_queries([{'id': 'q', 'text': '鸟', 'relevant_ids': ['a'], 'split': 'test', 'category': 'object'}], ['a'])


if __name__ == '__main__':
    unittest.main()
