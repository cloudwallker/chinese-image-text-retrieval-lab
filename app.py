import argparse
from pathlib import Path
import threading
import webbrowser
from lab.server import serve

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='本地 CPU 中文图文检索学习实验室')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--open', action='store_true', help='启动时打开本地网页')
    args = parser.parse_args()
    if args.open:
        threading.Timer(1.5, lambda: webbrowser.open('http://127.0.0.1:%d' % args.port)).start()
    serve(Path(__file__).resolve().parent, args.port)
