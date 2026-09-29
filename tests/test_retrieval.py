import unittest
import numpy as np

try:
    from lab.retrieval import normalize, rank_scores, parse_negative, combine_scores
except ImportError:
    normalize = rank_scores = parse_negative = combine_scores = None


class RetrievalTests(unittest.TestCase):
    def test_normalization_preserves_direction_and_rejects_zero(self):
        self.assertIsNotNone(normalize, '归一化函数尚未实现')
        np.testing.assert_allclose(normalize([[3., 4.], [6., 8.]]), [[.6, .8], [.6, .8]])
        with self.assertRaises(ValueError):
            normalize([[0., 0.]])
        with self.assertRaises(ValueError):
            normalize([[float('nan'), 1.]])

    def test_rank_is_stable_and_never_invents_candidates(self):
        self.assertIsNotNone(rank_scores, '排序函数尚未实现')
        ranked = rank_scores(['a', 'b', 'c'], [.2, .8, .8], 2)
        self.assertEqual([item['id'] for item in ranked], ['b', 'c'])
        with self.assertRaises(ValueError):
            rank_scores(['a'], [.1], 0)

    def test_negative_condition_is_visible_and_explicit(self):
        self.assertIsNotNone(parse_negative, '否定解析尚未实现')
        self.assertEqual(parse_negative('杯子，不要红色'), {'positive': '杯子', 'negative': '红色'})
        self.assertEqual(parse_negative('花瓶，但不含蓝色'), {'positive': '花瓶', 'negative': '蓝色'})
        self.assertEqual(parse_negative('红色的花'), {'positive': '红色的花', 'negative': ''})
        with self.assertRaises(ValueError):
            parse_negative('不要红色')
        with self.assertRaises(ValueError):
            parse_negative('   ')

    def test_negative_penalty_changes_order_without_claiming_probability(self):
        self.assertIsNotNone(combine_scores, '分数组合尚未实现')
        np.testing.assert_allclose(combine_scores([.7, .6], [.9, .1], .5), [.25, .55])
        with self.assertRaises(ValueError):
            combine_scores([.7], [.9], -1)


if __name__ == '__main__':
    unittest.main()
