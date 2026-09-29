"""CPU 模型、图片缓存与人工描述基线。"""
import ctypes
import hashlib
import json
import re
import threading
from zipfile import BadZipFile
from collections import Counter, OrderedDict
from pathlib import Path
from time import perf_counter
import numpy as np
from PIL import Image
from .retrieval import normalize, rank_scores, parse_negative, combine_scores

MODEL_REVISION = '717ba215769231e53b9b7c6b9d329b9cc5944418'
MODEL_NAME = 'Chinese-CLIP RN50'


def available_memory_mb():
    try:
        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ('total', 'available', 'page_total', 'page_available', 'virtual_total', 'virtual_available', 'extended')]
        mem = MemoryStatus()
        mem.length = ctypes.sizeof(mem)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
            return round(mem.available / 2**20)
    except (AttributeError, OSError):
        pass
    return None


def load_gallery(root):
    root = Path(root).resolve()
    location = root / 'data/gallery.json'
    if not location.exists():
        return []
    items = json.loads(location.read_text(encoding='utf-8')).get('items', [])
    if not isinstance(items, list):
        raise ValueError('图库 items 必须为列表')
    ids = set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in ids:
            raise ValueError('图库 id 必须为唯一字符串')
        path = (root / item.get('file', '')).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('图库图片不存在或超出项目目录')
        if path.suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
            raise ValueError('图库只允许常见图片文件')
        ids.add(item['id'])
    return items


def gallery_fingerprint(items, root, model_version):
    digest = hashlib.sha256(model_version.encode())
    for item in items:
        digest.update(item['id'].encode('utf-8'))
        digest.update(item['file'].encode('utf-8'))
        with (Path(root) / item['file']).open('rb') as stream:
            for block in iter(lambda: stream.read(65536), b''):
                digest.update(block)
    return digest.hexdigest()


def _tokens(text):
    tokens = re.findall(r'[a-zA-Z0-9]+', text.lower())
    for phrase in re.findall(r'[\u4e00-\u9fff]+', text):
        tokens.extend(char for char in phrase if char not in '的一张在有是和与这')
        tokens.extend(phrase[i:i+2] for i in range(len(phrase)-1))
    return Counter(tokens)


class ChineseClipEncoder:
    def __init__(self, root):
        model_path = Path(root) / 'models/clip_cn_rn50.pt'
        if not model_path.exists() or model_path.stat().st_size < 100_000_000:
            raise RuntimeError('模型权重未准备好。请运行 scripts/download_model.py 或 setup.ps1。')
        try:
            import torch
            import cn_clip.clip as clip
        except ImportError as exc:
            raise RuntimeError('CPU 模型依赖未安装。请运行 powershell -File scripts/setup.ps1。') from exc
        memory = available_memory_mb()
        if memory is not None and memory < 128:
            raise RuntimeError('当前可用内存不足 128MB，请释放一些内存后重试；项目不会关闭你的程序。')
        torch.set_num_threads(2)
        self.torch = torch
        self.clip = clip
        self.model, self.preprocess = clip.load_from_name('RN50', device='cpu', download_root=str(model_path.parent))
        self.model.eval()
        self.text_cache = OrderedDict()

    def encode_image(self, path):
        with Image.open(path) as source:
            tensor = self.preprocess(source.convert('RGB')).unsqueeze(0)
        with self.torch.inference_mode():
            return normalize(self.model.encode_image(tensor).float().cpu().numpy())[0]

    def encode_text(self, text):
        if text not in self.text_cache:
            content_tokens = self.clip._tokenizer.tokenize(text)
            if len(content_tokens) > 50:
                raise ValueError('图文模型最多接受 50 个分词 token（当前 %d 个），请缩短描述；没有执行截断检索。' % len(content_tokens))
            tokens = self.clip.tokenize([text])
            with self.torch.inference_mode():
                values = normalize(self.model.encode_text(tokens).float().cpu().numpy())[0]
            self.text_cache[text] = values
            if len(self.text_cache) > 128:
                self.text_cache.popitem(last=False)
        return self.text_cache[text]


class RetrievalEngine:
    model_name = MODEL_NAME

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.items = load_gallery(self.root)
        self.encoder = None
        self.vectors = None
        self.index_ready = False
        self.lock = threading.RLock()
        self._read_index()

    def _read_index(self):
        location = self.root / 'cache/image_index.npz'
        if not self.items or not location.exists():
            return False
        fingerprint = gallery_fingerprint(self.items, self.root, MODEL_REVISION)
        try:
            with location.open('rb') as stream, np.load(stream, allow_pickle=False) as cache:
                if str(cache['fingerprint'].item()) != fingerprint:
                    return False
                values = cache['vectors']
                if values.ndim != 2 or values.shape[0] != len(self.items):
                    return False
                self.vectors = normalize(values)
                self.index_ready = True
                return True
        except (OSError, ValueError, KeyError, BadZipFile, EOFError):
            return False

    def _get_encoder(self):
        if self.encoder is None:
            self.encoder = ChineseClipEncoder(self.root)
        return self.encoder

    def prepare(self, progress=None):
        with self.lock:
            self.items = load_gallery(self.root)
            if not self.items:
                raise RuntimeError('没有演示图片，请先运行 scripts/prepare_gallery.py。')
            if progress:
                progress(.01, '加载中文模型（CPU），首次需要一点时间')
            encoder = self._get_encoder()
            if self._read_index():
                if progress:
                    progress(1., '已读取有效图片向量缓存，无需重复编码')
                return
            self.index_ready = False
            rows = []
            for count, item in enumerate(self.items, 1):
                rows.append(encoder.encode_image(self.root / item['file']))
                if progress:
                    progress(count / len(self.items), '编码图片 %d/%d：%s' % (count, len(self.items), item.get('title', item['id'])))
            values = np.asarray(rows, dtype=np.float32)
            directory = self.root / 'cache'
            directory.mkdir(exist_ok=True)
            temporary = directory / 'image_index.tmp.npz'
            np.savez_compressed(temporary, vectors=values,
                                fingerprint=gallery_fingerprint(self.items, self.root, MODEL_REVISION))
            temporary.replace(directory / 'image_index.npz')
            self.vectors = values
            self.index_ready = True

    def _caption_scores(self, query):
        corpus = [_tokens(' '.join([item.get('title', ''), item.get('caption', ''), ' '.join(item.get('tags', []))])) for item in self.items]
        wanted = _tokens(query)
        vocab = sorted(set(wanted) | set().union(*(set(row) for row in corpus)))
        if not vocab:
            return np.zeros(len(self.items), dtype=np.float32)
        idf = {t: np.log((len(corpus) + 1) / (1 + sum(t in row for row in corpus))) + 1 for t in vocab}
        target = np.array([wanted[t] * idf[t] for t in vocab])
        norms = np.linalg.norm(target)
        if not norms:
            return np.zeros(len(self.items), dtype=np.float32)
        scores = []
        for row in corpus:
            value = np.array([row[t] * idf[t] for t in vocab])
            denominator = norms * np.linalg.norm(value)
            scores.append(float(value @ target / denominator) if denominator else 0.)
        return np.asarray(scores, dtype=np.float32)

    def search(self, query, method='caption', top_k=5, negative_weight=.4):
        parsed = parse_negative(query)
        if method not in ('caption', 'clip', 'negative'):
            raise ValueError('未知检索方法')
        if not self.items:
            raise RuntimeError('图库为空，请准备演示数据')
        start = perf_counter()
        with self.lock:
            if method == 'caption':
                scores = self._caption_scores(query)
                message = '基于人工中文描述的 TF-IDF 词项匹配；没有运行图像编码器。'
            else:
                if not self.index_ready:
                    raise RuntimeError('图片向量索引未就绪，请先点击“准备模型与索引”。')
                # 每次真实模型检索验证图片指纹，避免图库变化后复用旧结果。
                if not self._read_index():
                    self.index_ready = False
                    raise RuntimeError('图库图片已变化，请重新准备索引。')
                encoder = self._get_encoder()
                if method == 'clip':
                    scores = self.vectors @ encoder.encode_text(query)
                    message = '真实 CPU 图像/文本编码的余弦相似度；分数不是置信概率。'
                else:
                    scores = self.vectors @ encoder.encode_text(parsed['positive'])
                    if parsed['negative']:
                        rejected = self.vectors @ encoder.encode_text(parsed['negative'])
                        scores = combine_scores(scores, rejected, negative_weight)
                    message = '教学启发式：正向相似度 − 排除权重 × 排除条件相似度；没有训练模型。'
            ranked = rank_scores([item['id'] for item in self.items], scores, top_k)
            lookup = {item['id']: item for item in self.items}
            results = [dict(lookup[result['id']], score=result['score']) for result in ranked]
        return {'results': results, 'elapsed_ms': (perf_counter() - start) * 1000,
                'parsed': parsed, 'method': method, 'message': message}
