"""核验正在运行的本地 HTTP 服务，笔记测试会恢复测试前文件。"""
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    base = 'http://127.0.0.1:%d' % args.port
    checks = []

    def request(path, body=None, expected=200, origin=None, host=None):
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        if host:
            headers['Host'] = host
        data = None if body is None else json.dumps(body, ensure_ascii=False).encode('utf-8')
        try:
            response = urlopen(Request(base + path, data=data, headers=headers), timeout=120)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            assert response.status == expected, (path, response.status, raw[:200])
            checks.append({'path': path, 'status': response.status})
            return raw, dict(response.headers)

    def api(path, body=None, expected=200, origin=None, host=None):
        raw, _ = request(path, body, expected, origin, host)
        return json.loads(raw.decode('utf-8'))

    status = api('/api/status')
    assert status['gallery_count'] == 48 and status['index_ready']
    assert not status['busy'], '请先等待已有任务结束'
    gallery = api('/api/gallery')['items']
    assert len(gallery) == 48 and '花瓶' in gallery[0]['title']
    for asset in ('/', '/app.js', '/styles.css', '/' + gallery[0]['file']):
        raw, _ = request(asset)
        assert raw
    request('/models/clip_cn_rn50.pt', expected=404)
    request('/data/images/%2e%2e/gallery.json', expected=404)
    api('/api/search', {'query': ''}, expected=400)
    api('/api/search', {'query': '猫', 'top_k': True}, expected=400)
    api('/api/prepare', {}, expected=403, origin='https://example.invalid')
    api('/api/notes', expected=403, host='other-site.example:%d' % args.port)
    api('/api/prepare', {}, expected=403, host='other-site.example:%d' % args.port)
    searches = []
    for method in ('caption', 'clip', 'negative'):
        result = api('/api/search', {'query': '椅子，不要坐垫', 'method': method, 'top_k': 5, 'negative_weight': .4})
        assert len(result['results']) == 5 and result['method'] == method
        assert len({item['id'] for item in result['results']}) == 5
        if method == 'negative':
            assert result['parsed'] == {'positive': '椅子', 'negative': '坐垫'}
        searches.append({'method': method, 'elapsed_ms': result['elapsed_ms'], 'top_id': result['results'][0]['id']})
    assert api('/api/status')['model_ready']
    for suffix in ('红色', '蓝色'):
        result = api('/api/search', {'query': '杯子' * 30 + suffix, 'method': 'clip'}, expected=400)
        assert '50' in result['error'] and '没有执行截断' in result['error']

    # 临时探针不是用户笔记；完成后恢复原文件的所有字节。
    notes_path = ROOT / 'cache/notes.json'
    original = notes_path.read_bytes() if notes_path.exists() else None
    try:
        sample = '# 接口测试探针\n这段文本只用于验证中文笔记往返。'
        assert api('/api/notes', {'content': sample})['content'] == sample
        assert api('/api/notes')['content'] == sample
    finally:
        if original is None:
            notes_path.unlink(missing_ok=True)
        else:
            notes_path.write_bytes(original)

    api('/api/evaluate', {'split': 'test', 'negative_weight': .4}, expected=202)
    deadline = time.monotonic() + 60
    while True:
        current = api('/api/status')
        if not current['busy']:
            assert not current['error'], current['error']
            break
        assert time.monotonic() < deadline, '实验等待超时'
        time.sleep(.25)
    report = api('/api/report')
    assert report['gallery_count'] == 48 and report['query_count'] == 16
    assert len(report['methods']) == 3
    assert all(len(method['rows']) == 16 for method in report['methods'])
    raw, headers = request('/api/export')
    assert json.loads(raw.decode('utf-8')) == report
    assert 'attachment' in headers['Content-Disposition']
    output = {'checks': checks, 'searches': searches, 'report_created_at': report['created_at'],
              'metrics': {method['method']: method['metrics'] for method in report['methods']},
              'notes_restored': True}
    location = ROOT / 'cache/http-smoke.json'
    location.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('集成验证失败：%s' % exc, file=sys.stderr)
        raise
