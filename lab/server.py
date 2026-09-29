"""只监听本机的轻量 HTTP API；不暴露模型与任意文件。"""
import json
import math
import mimetypes
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from .engine import RetrievalEngine, available_memory_mb
from .evaluation import evaluate


def validate_host(host, port):
    allowed = {'127.0.0.1:%d' % port, 'localhost:%d' % port}
    if port == 80:
        allowed.update(('127.0.0.1', 'localhost'))
    if not isinstance(host, str) or host.strip().lower() not in allowed:
        raise ValueError('仅允许使用本机地址访问')


def safe_static_path(root, url):
    root = Path(root).resolve()
    path = unquote(urlsplit(url).path)
    if '\\' in path or any(part in ('.', '..') for part in path.split('/')):
        raise ValueError('不允许的资源路径')
    if path == '/':
        relative = 'web/index.html'
    elif path in ('/styles.css', '/app.js'):
        relative = 'web' + path
    elif path.startswith('/data/images/'):
        relative = path.lstrip('/')
        if Path(relative).suffix.lower() not in ('.jpg', '.jpeg', '.png', '.webp'):
            raise ValueError('只允许图片资源')
    else:
        raise ValueError('资源不存在')
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError('资源不存在')
    return resolved


def validate_search(body):
    if not isinstance(body, dict):
        raise ValueError('请求必须为 JSON 对象')
    query, method = body.get('query'), body.get('method', 'caption')
    k, weight = body.get('top_k', 5), body.get('negative_weight', .4)
    if not isinstance(query, str) or not query.strip() or len(query) > 300:
        raise ValueError('请输入 1–300 个字符的查询')
    if method not in ('caption', 'clip', 'negative'):
        raise ValueError('请选择有效检索方法')
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 100:
        raise ValueError('top_k 必须为 1–100 的整数')
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not math.isfinite(weight) or not 0 <= weight <= 1:
        raise ValueError('排除权重必须在 0–1 之间')
    return {'query': query.strip(), 'method': method, 'top_k': k, 'negative_weight': weight}


class LabApplication:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.engine = RetrievalEngine(self.root)
        self.guard = threading.Lock()
        self.busy, self.progress, self.task, self.message, self.error = False, 0., '', '准备开始你的检索实验', None
        self.cache = self.root / 'cache'
        self.cache.mkdir(exist_ok=True)

    def status(self):
        with self.guard:
            return {'model_ready': self.engine.encoder is not None, 'index_ready': self.engine.index_ready,
                    'busy': self.busy, 'progress': self.progress, 'task': self.task,
                    'message': self.message, 'error': self.error, 'gallery_count': len(self.engine.items),
                    'memory_available_mb': available_memory_mb(), 'report_ready': (self.cache / 'report.json').exists(),
                    'model_name': self.engine.model_name, 'model_file_present': (self.root / 'models/clip_cn_rn50.pt').exists()}

    def update(self, progress, message):
        with self.guard:
            self.progress, self.message = float(progress), message

    def launch(self, task, parameters=None):
        with self.guard:
            if self.busy:
                raise BlockingIOError('已有任务运行中，请等待完成')
            self.busy, self.progress, self.task, self.error = True, 0., task, None
            self.message = '正在启动任务'
        def worker():
            try:
                if task == 'prepare':
                    self.engine.prepare(self.update)
                    self.update(1., 'CPU 模型与图片索引就绪')
                else:
                    queries = json.loads((self.root / 'data/queries.json').read_text(encoding='utf-8'))['queries']
                    report = evaluate(self.engine, queries, progress=self.update, **(parameters or {}))
                    temporary = self.cache / 'report.tmp.json'
                    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
                    temporary.replace(self.cache / 'report.json')
                    self.update(1., '实际实验报告已生成')
            except Exception as exc:
                with self.guard:
                    self.error = str(exc)
                    self.message = '任务未完成：' + str(exc)
            finally:
                with self.guard:
                    self.busy = False
        threading.Thread(target=worker, daemon=True, name='retrieval-' + task).start()

    def notes(self):
        location = self.cache / 'notes.json'
        if location.exists():
            return json.loads(location.read_text(encoding='utf-8'))
        return {'content': '# 我的跨模态检索学习记录\n\n## 我想验证的问题\n\n## 我的假设与理由\n\n## 实际观察（附查询和图片 ID）\n\n## 失败案例与可能原因\n\n## 下一步实验\n', 'updated_at': None}


def make_handler(application):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _reply(self, value, code=200, download=False):
            raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if download:
                self.send_header('Content-Disposition', 'attachment; filename="retrieval-report.json"')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            try:
                validate_host(self.headers.get('Host'), self.server.server_port)
            except ValueError as exc:
                return self._reply({'error': str(exc)}, 403)
            path = urlsplit(self.path).path
            try:
                if path == '/api/status':
                    return self._reply(application.status())
                if path == '/api/gallery':
                    return self._reply({'items': application.engine.items})
                if path == '/api/notes':
                    return self._reply(application.notes())
                if path in ('/api/report', '/api/export'):
                    location = application.cache / 'report.json'
                    if not location.exists():
                        return self._reply({'error': '还没有实验报告，请先运行实验'}, 404)
                    return self._reply(json.loads(location.read_text(encoding='utf-8')), download=path == '/api/export')
                asset = safe_static_path(application.root, self.path)
                raw = asset.read_bytes()
                self.send_response(200)
                kind = mimetypes.guess_type(str(asset))[0] or 'application/octet-stream'
                self.send_header('Content-Type', kind + ('; charset=utf-8' if kind.startswith('text/') or kind == 'application/javascript' else ''))
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers()
                self.wfile.write(raw)
            except ValueError as exc:
                self._reply({'error': str(exc)}, 404)
            except (OSError, KeyError, json.JSONDecodeError):
                self._reply({'error': '本地文件读取失败'}, 500)

        def do_POST(self):
            try:
                validate_host(self.headers.get('Host'), self.server.server_port)
            except ValueError as exc:
                return self._reply({'error': str(exc)}, 403)
            # 本地网页之外的站点不能写笔记或启动耗资源任务。
            origin = self.headers.get('Origin')
            if origin and origin not in ('http://127.0.0.1:%d' % self.server.server_port, 'http://localhost:%d' % self.server.server_port):
                return self._reply({'error': '仅允许本地页面操作'}, 403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length < 0 or length > 100_000:
                    raise ValueError('请求内容过长')
                body = json.loads(self.rfile.read(length).decode('utf-8')) if length else {}
                path = urlsplit(self.path).path
                if path == '/api/search':
                    if application.busy:
                        raise BlockingIOError('后台任务运行中，请等待后再检索')
                    return self._reply(application.engine.search(**validate_search(body)))
                if path in ('/api/prepare', '/api/evaluate'):
                    parameters = None
                    if path.endswith('evaluate'):
                        if not isinstance(body, dict) or body.get('split', 'test') not in ('test', 'validation'):
                            raise ValueError('请选择 test 或 validation 划分')
                        weight = validate_search({'query': '评估', 'negative_weight': body.get('negative_weight', .4)})['negative_weight']
                        parameters = {'split': body.get('split', 'test'), 'negative_weight': weight}
                    application.launch('prepare' if path.endswith('prepare') else 'evaluate', parameters)
                    return self._reply({'started': True}, 202)
                if path == '/api/notes':
                    if not isinstance(body, dict) or not isinstance(body.get('content'), str) or len(body['content']) > 30000:
                        raise ValueError('笔记应为不超过 30000 字的文本')
                    note = {'content': body['content'], 'updated_at': datetime.now(timezone.utc).isoformat()}
                    temporary = application.cache / 'notes.tmp.json'
                    temporary.write_text(json.dumps(note, ensure_ascii=False), encoding='utf-8')
                    temporary.replace(application.cache / 'notes.json')
                    return self._reply(note)
                return self._reply({'error': '接口不存在'}, 404)
            except BlockingIOError as exc:
                self._reply({'error': str(exc)}, 409)
            except (ValueError, TypeError, UnicodeDecodeError) as exc:
                self._reply({'error': str(exc)}, 400)
            except RuntimeError as exc:
                self._reply({'error': str(exc)}, 503)
            except Exception:
                self._reply({'error': '操作失败，请查看模型和数据是否准备好'}, 500)
    return Handler


def serve(root, port=8765):
    app = LabApplication(root)
    server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(app))
    print('本地学习实验室：http://127.0.0.1:%d （Ctrl+C 停止）' % port, flush=True)
    server.serve_forever()
