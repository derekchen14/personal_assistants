"""Seed-scenario review server — stdlib http.server on port 8023.

The train split (utils/evaluation_suite/datasets/train.jsonl — one conversation per line) is the DB;
this serves a small UI to read each conversation and save a per-conversation verdict + comment under
review_app/feedback/.

  GET  /                    -> index.html
  GET  /app.js              -> app.js
  GET  /api/scenarios       -> [{id, persona, use_case, topic, title, verdict, flagged, kind}] (flagged only)
  GET  /api/search?q=<term> -> same item shape, ALL conversations matched by id/title/topic/utterance
  GET  /api/scenario/<id>   -> the case object for that convo_id
  GET  /api/feedback/<id>   -> feedback/<id>.json (stub if none)
  PUT  /api/feedback/<id>   -> save feedback/<id>.json

Run from the Hugo directory:
    python utils/evaluation_suite/review_app/server.py
    # then open http://localhost:8023
"""

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 8023
ROOT = Path(__file__).resolve().parent                 # utils/evaluation_suite/review_app
TRAIN = ROOT.parent / 'datasets' / 'train.jsonl'       # the corpus (one conversation per line)
FEEDBACK = ROOT / 'feedback'                            # review verdicts live with the review app


def _train() -> dict:
    """{convo_id: case} from the train split, read fresh each call (96 lines, cheap)."""
    cases = {}
    for line in TRAIN.read_text().splitlines():
        line = line.strip()
        if line:
            case = json.loads(line)
            cases[case['convo_id']] = case
    return cases


def _scan_kind(case):
    # Conversation-level chip: 'Plan' if any user turn is a plan (multi-flow stack / intent Plan), else None.
    for turn in case.get('turns', []):
        if (turn.get('labels') or {}).get('intent') == 'Plan':
            return 'Plan'
    return None


class Handler(BaseHTTPRequestHandler):

    def _send_json(self, payload, status=200):
        body = json.dumps(payload, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        if not path.exists():
            self.send_error(404, f'Not found: {path.name}')
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _item(self, case):
        cid = case['convo_id']
        fb = FEEDBACK / f'{cid}.json'
        verdict = json.loads(fb.read_text()).get('verdict') if fb.exists() else None
        return {'id': cid, 'persona': case.get('persona', '—'),
                'use_case': case.get('use_case', '—'), 'topic': case.get('topic', '—'),
                'title': case.get('title', cid), 'verdict': verdict,
                'flagged': case.get('flagged', False), 'kind': _scan_kind(case)}

    def _scenario_list(self):
        # Main review log: only cases flagged for review (one per batch is seeded on the scenario).
        return [self._item(case) for case in _train().values() if case.get('flagged', False)]

    def _search(self, query):
        # Separate search across ALL conversations (unfiltered), matched by id/title/topic/utterance.
        query = query.lower()
        hits = []
        for case in _train().values():
            haystack = [case['convo_id'], case.get('title', ''), case.get('topic', ''),
                        case.get('persona', '')]
            haystack += [t.get('utterance', '') for t in case.get('turns', [])]
            if not query or any(query in field.lower() for field in haystack):
                hits.append(self._item(case))
        return hits

    def do_GET(self):
        p = self.path
        if p in ('/', '/index.html'):
            self._send_file(ROOT / 'index.html', 'text/html; charset=utf-8')
            return
        if p == '/app.js':
            self._send_file(ROOT / 'app.js', 'application/javascript; charset=utf-8')
            return
        if p == '/api/scenarios':
            self._send_json(self._scenario_list())
            return
        if p.split('?', 1)[0] == '/api/search':
            query = parse_qs(urlparse(p).query).get('q', [''])[0]
            self._send_json(self._search(query))
            return
        if p.startswith('/api/scenario/'):
            cid = p.rsplit('/', 1)[-1]
            case = _train().get(cid)
            if case is None:
                self._send_json({'error': f'no scenario {cid}'}, status=404)
                return
            self._send_json(case)
            return
        if p.startswith('/api/feedback/'):
            cid = p.rsplit('/', 1)[-1]
            fp = FEEDBACK / f'{cid}.json'
            if not fp.exists():
                self._send_json({'id': cid, 'verdict': None, 'comment': ''})
                return
            self._send_json(json.loads(fp.read_text()))
            return
        self.send_error(404, f'Not found: {p}')

    def do_PUT(self):
        p = self.path
        if p.startswith('/api/feedback/'):
            cid = p.rsplit('/', 1)[-1]
            length = int(self.headers.get('Content-Length', 0))
            try:
                payload = json.loads(self.rfile.read(length))
            except json.JSONDecodeError as ecp:
                self._send_json({'error': f'invalid json: {ecp}'}, status=400)
                return
            FEEDBACK.mkdir(parents=True, exist_ok=True)
            (FEEDBACK / f'{cid}.json').write_text(json.dumps(payload, indent=2) + '\n')
            self._send_json({'saved': True})
            return
        self.send_error(404, f'Not found: {p}')

    def log_message(self, fmt, *args):
        sys.stderr.write(f'[seed-review] {fmt % args}\n')


def main():
    server = HTTPServer(('localhost', PORT), Handler)
    print(f'Seed review running at http://localhost:{PORT}')
    print(f'  corpus: {TRAIN}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nshutting down')
        server.server_close()


if __name__ == '__main__':
    main()
