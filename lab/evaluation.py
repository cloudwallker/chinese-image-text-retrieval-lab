"""自建教学集的实际评估，多正例定义明确。"""
from collections import defaultdict
from datetime import datetime, timezone
from time import perf_counter
import numpy as np


def metrics(ranked_ids, relevant_ids, k):
    if not isinstance(k, int) or k < 1:
        raise ValueError('k 必须为正整数')
    if len(set(ranked_ids)) != len(ranked_ids):
        raise ValueError('排序候选不得重复')
    relevant = set(relevant_ids)
    if not relevant:
        raise ValueError('每个查询至少需要一个正确答案')
    matches = 0
    precision_sum = 0.
    for rank, image_id in enumerate(ranked_ids[:k], 1):
        if image_id in relevant:
            matches += 1
            precision_sum += matches / rank
    return {'hit': float(matches > 0), 'recall': matches / len(relevant),
            'ap': precision_sum / min(k, len(relevant))}


def validate_queries(queries, gallery_ids):
    gallery = set(gallery_ids)
    seen = set()
    for query in queries:
        if not isinstance(query, dict) or not query.get('id') or query['id'] in seen:
            raise ValueError('查询 id 缺失或重复')
        if not isinstance(query.get('text'), str) or not query['text'].strip():
            raise ValueError('查询文本不能为空')
        relevant = query.get('relevant_ids')
        if not isinstance(relevant, list) or not relevant or not set(relevant) <= gallery:
            raise ValueError('正确答案为空或含不在图库中的图片')
        if query.get('split') not in ('validation', 'test'):
            raise ValueError('查询划分应为 validation 或 test')
        seen.add(query['id'])


def _average(rows):
    keys = ('hit_at_1', 'hit_at_5', 'recall_at_5', 'map_at_5')
    return {key: float(np.mean([r[key] for r in rows])) if rows else 0. for key in keys}


def evaluate(engine, queries, split='test', negative_weight=.4, progress=None, methods=None):
    validate_queries(queries, [item['id'] for item in engine.items])
    selected = [q for q in queries if q['split'] == split]
    if not selected:
        raise ValueError('所选划分没有查询')
    labels = {'caption': '人工描述基线', 'clip': '原始图文相似度', 'negative': '排除条件教学实验'}
    if methods is None:
        methods = ['caption', 'clip', 'negative'] if engine.index_ready else ['caption']
    else:
        methods = list(methods)
        if not methods or len(set(methods)) != len(methods) or any(method not in labels for method in methods):
            raise ValueError('评估方法必须为不重复的有效方法')
        if any(method != 'caption' for method in methods) and not engine.index_ready:
            raise RuntimeError('图片索引未就绪，不能运行图文模型评估')
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'gallery_count': len(engine.items),
              'query_count': len(selected), 'split': split,
              'model': engine.model_name if any(method != 'caption' for method in methods) else '未运行图文模型',
              'negative_weight': negative_weight, 'warnings': [], 'methods': []}
    if methods == ['caption']:
        report['warnings'].append('本报告只运行人工描述基线，没有调用图文模型。')
    report['warnings'].append('自建教学集结果只代表当前图库与标注，不是标准论文基准或原创方法证明。')
    total = len(methods) * len(selected)
    completed = 0
    for method in methods:
        rows, groups = [], defaultdict(list)
        start = perf_counter()
        for query in selected:
            found = engine.search(query['text'], method, len(engine.items), negative_weight)
            ranked = [r['id'] for r in found['results']]
            one, five = metrics(ranked, query['relevant_ids'], 1), metrics(ranked, query['relevant_ids'], 5)
            row = {'id': query['id'], 'text': query['text'], 'category': query.get('category', 'other'),
                   'relevant_ids': query['relevant_ids'], 'ranked_ids': ranked,
                   'top_results': found['results'][:5], 'hit_at_1': one['hit'], 'hit_at_5': five['hit'],
                   'recall_at_5': five['recall'], 'map_at_5': five['ap']}
            rows.append(row)
            groups[row['category']].append(row)
            completed += 1
            if progress:
                progress(completed / total, '正在评价 %s：%d/%d' % (labels[method], completed, total))
        report['methods'].append({'method': method, 'label': labels[method], 'metrics': _average(rows),
                                  'elapsed_ms': (perf_counter() - start) * 1000,
                                  'categories': [{'category': cat, 'count': len(rs), 'metrics': _average(rs)} for cat, rs in groups.items()],
                                  'rows': rows})
    return report
