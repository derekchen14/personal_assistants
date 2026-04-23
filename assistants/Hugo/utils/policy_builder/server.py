"""Policy Builder server \u2014 stdlib http.server on port 8022.

Round 2 shape:
  GET  /                       \u2192 index.html
  GET  /app.js                 \u2192 app.js
  GET  /api/flows              \u2192 { round, flows }
  GET  /api/draft/<flow>       \u2192 data/drafts/<flow>.json
  GET  /api/feedback/<flow>    \u2192 data/feedback/<flow>.json (empty stub if not started)
  PUT  /api/feedback/<flow>    \u2192 save data/feedback/<flow>.json

Run from the Hugo directory:
    python utils/policy_builder/server.py
    # then open http://localhost:8022
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8022
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / 'data'

ALL_FLOWS = ['outline', 'rework', 'add', 'polish', 'audit', 'inspect', 'find', 'release']
ROUND = 2


class Handler(BaseHTTPRequestHandler):

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path:Path, content_type:str):
        if not path.exists():
            self.send_error(404, f'Not found: {path.name}')
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path
        if p == '/' or p == '/index.html':
            self._send_file(ROOT / 'index.html', 'text/html; charset=utf-8')
            return
        if p == '/app.js':
            self._send_file(ROOT / 'app.js', 'application/javascript; charset=utf-8')
            return
        if p == '/api/flows':
            self._send_json({'round': ROUND, 'flows': ALL_FLOWS})
            return
        if p.startswith('/api/draft/'):
            flow = p.rsplit('/', 1)[-1]
            fp = DATA_DIR / 'drafts' / f'{flow}.json'
            if not fp.exists():
                self._send_json({'error': f'no draft for {flow}'}, status=404)
                return
            self._send_json(json.loads(fp.read_text()))
            return
        if p.startswith('/api/feedback/'):
            flow = p.rsplit('/', 1)[-1]
            fp = DATA_DIR / 'feedback' / f'{flow}.json'
            if not fp.exists():
                self._send_json({'flow': flow, 'sections': {}}, status=200)
                return
            self._send_json(json.loads(fp.read_text()))
            return
        self.send_error(404, f'Not found: {p}')

    def do_PUT(self):
        p = self.path
        if p.startswith('/api/feedback/'):
            flow = p.rsplit('/', 1)[-1]
            length = int(self.headers.get('Content-Length', 0))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError as ecp:
                self._send_json({'error': f'invalid json: {ecp}'}, status=400)
                return
            (DATA_DIR / 'feedback').mkdir(parents=True, exist_ok=True)
            fp = DATA_DIR / 'feedback' / f'{flow}.json'
            fp.write_text(json.dumps(payload, indent=2) + '\n')
            self._send_json({'saved': True, 'path': str(fp.relative_to(ROOT))})
            return
        self.send_error(404, f'Not found: {p}')

    def log_message(self, fmt, *args):
        sys.stderr.write(f'[policy_builder] {fmt % args}\n')


def main():
    server = HTTPServer(('localhost', PORT), Handler)
    print(f'Policy Builder running at http://localhost:{PORT}')
    print(f'  data dir: {DATA_DIR}')
    print(f'  round {ROUND} \u2014 flows: {ALL_FLOWS}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nshutting down')
        server.server_close()


if __name__ == '__main__':
    main()
