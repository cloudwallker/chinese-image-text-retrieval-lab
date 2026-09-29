import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lab.engine import RetrievalEngine
from lab.evaluation import evaluate


def main():
    parser = argparse.ArgumentParser(description='在固定完整图库上运行实际 CPU 检索对照实验')
    parser.add_argument('--split', choices=['validation', 'test'], default='test')
    parser.add_argument('--negative-weight', type=float, default=.4)
    parser.add_argument('--caption-only', action='store_true', help='只运行标注清楚的人工描述基线')
    args = parser.parse_args()
    engine = RetrievalEngine(ROOT)
    if not args.caption_only:
        engine.prepare(lambda fraction, message: print(message, flush=True))
    queries = json.loads((ROOT / 'data/queries.json').read_text(encoding='utf-8'))['queries']
    report = evaluate(engine, queries, args.split, args.negative_weight,
                      lambda fraction, message: print(message, flush=True),
                      methods=['caption'] if args.caption_only else None)
    cache = ROOT / 'cache'
    cache.mkdir(exist_ok=True)
    destination = cache / 'report.json'
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n实际报告：' + str(destination))
    for method in report['methods']:
        print(method['label'] + ': ' + json.dumps(method['metrics'], ensure_ascii=False))


if __name__ == '__main__':
    main()
