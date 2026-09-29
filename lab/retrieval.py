"""独立于模型的检索算法；相似度不等于概率。"""
import re
import numpy as np


def normalize(vectors):
    values = np.asarray(vectors, dtype=np.float32)
    if values.ndim not in (1, 2) or not np.isfinite(values).all():
        raise ValueError('向量必须是一维或二维有限数值数组')
    norms = np.linalg.norm(values, axis=-1, keepdims=True)
    if np.any(norms < 1e-12):
        raise ValueError('零向量无法计算余弦相似度')
    return values / norms


def rank_scores(ids, scores, top_k):
    values = np.asarray(scores, dtype=float)
    if values.shape != (len(ids),) or not np.isfinite(values).all():
        raise ValueError('分数必须与候选图片一一对应且为有限数值')
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100:
        raise ValueError('top_k 必须为 1–100 的整数')
    order = np.argsort(-values, kind='stable')[:top_k]
    return [{'id': ids[int(i)], 'score': float(values[i])} for i in order]


def parse_negative(query):
    if not isinstance(query, str) or not query.strip() or len(query) > 300:
        raise ValueError('请输入 1–300 个字符的查询')
    parts = re.split(r'[，,；;]?\s*(?:但)?(?:不要|不包含|不含|排除)\s*', query.strip(), maxsplit=1)
    positive = parts[0].strip(' ，,；;。')
    negative = parts[1].strip(' ，,；;。') if len(parts) > 1 else ''
    if not positive or (len(parts) > 1 and not negative):
        raise ValueError('请使用“要找的内容，不要排除的内容”，例如“杯子，不要红色”')
    return {'positive': positive, 'negative': negative}


def combine_scores(positive, negative, weight):
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not np.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError('排除权重必须在 0–1 之间')
    p, n = np.asarray(positive, dtype=np.float32), np.asarray(negative, dtype=np.float32)
    if p.shape != n.shape or not np.isfinite(p).all() or not np.isfinite(n).all():
        raise ValueError('正向与排除分数必须形状一致且为有限数值')
    return p - weight * n
