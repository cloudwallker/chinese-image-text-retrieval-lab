"""下载固定版本官方 RN50 权重，校验官方 LFS SHA-256 后原子替换。"""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = '717ba215769231e53b9b7c6b9d329b9cc5944418'
REPOSITORY = 'OFA-Sys/chinese-clip-rn50'
FILENAME = 'clip_cn_rn50.pt'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def download():
    folder = ROOT / 'models'
    folder.mkdir(exist_ok=True)
    metadata_url = 'https://huggingface.co/api/models/%s/tree/%s' % (REPOSITORY, REVISION)
    with urllib.request.urlopen(metadata_url, timeout=60) as response:
        tree = json.load(response)
    metadata = next(row for row in tree if row.get('path') == FILENAME)
    expected = metadata['lfs']['oid']
    destination = folder / FILENAME
    url = 'https://huggingface.co/%s/resolve/%s/%s' % (REPOSITORY, REVISION, FILENAME)
    if destination.exists() and sha256(destination) == expected:
        print('官方 CPU 模型已存在，SHA-256 校验通过。', flush=True)
    else:
        temporary = folder / (FILENAME + '.part')
        print('下载官方 RN50 权重，约 308MB；仅需首次准备。', flush=True)
        request = urllib.request.Request(url, headers={'User-Agent': 'LocalRetrievalLearningLab/1.0'})
        with urllib.request.urlopen(request, timeout=180) as source, temporary.open('wb') as target:
            total, previous = 0, 0
            while True:
                block = source.read(1024 * 1024)
                if not block:
                    break
                target.write(block)
                total += len(block)
                if total - previous >= 32 * 1024 * 1024:
                    print('已下载 %dMB' % (total // 1024**2), flush=True)
                    previous = total
        if sha256(temporary) != expected:
            temporary.unlink(missing_ok=True)
            raise RuntimeError('模型校验失败，未替换正式权重；请重新下载。')
        temporary.replace(destination)
        print('官方权重下载完成，SHA-256 校验通过。', flush=True)
    info = {'repository': REPOSITORY, 'revision': REVISION, 'filename': FILENAME,
            'sha256': expected, 'source_url': url, 'bytes': destination.stat().st_size}
    (folder / 'model_info.json').write_text(json.dumps(info, indent=2), encoding='utf-8')


if __name__ == '__main__':
    try:
        download()
    except Exception as exc:
        print('模型准备失败：%s' % getattr(exc, 'reason', str(exc)), file=sys.stderr)
        sys.exit(1)
