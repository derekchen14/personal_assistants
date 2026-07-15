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
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 8023
ROOT = Path(__file__).resolve().parent                 # utils/evaluation_suite/review_app
TRAIN = ROOT.parent / 'datasets' / 'train.jsonl'       # the corpus (one conversation per line)
FEEDBACK = ROOT / 'feedback'                            # review verdicts live with the review app
REPORT = ROOT.parent / 'report'
CURATION_ROUND = REPORT / 'curation_round_current.json'
CURATION_LEDGER = REPORT / 'curation_ledger.json'


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


def _curation_round():
    return json.loads(CURATION_ROUND.read_text()) if CURATION_ROUND.exists() else None


def _curation_item(convo_id):
    manifest = _curation_round()
    if not manifest:
        return None
    return next((item for item in manifest.get('cases', []) if item['convo_id'] == convo_id), None)


def _write_json(path, payload):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + '\n')
    temporary.replace(path)


def save_curation_decision(manifest_path, ledger_path, convo_id, payload):
    """Persist one decision and its first-review budget event atomically per file."""
    manifest = json.loads(manifest_path.read_text())
    item = next((entry for entry in manifest.get('cases', [])
                 if entry['convo_id'] == convo_id), None)
    if manifest.get('status') != 'open' or item is None:
        raise KeyError(f'no open curation item {convo_id}')
    decision = payload.get('decision')
    if decision not in ('keep', 'fix', 'delete', None):
        raise ValueError(f'invalid decision {decision!r}')
    ledger = json.loads(ledger_path.read_text())
    first_review = item.get('decision') is None and decision is not None
    already_recorded = any(event['round'] == manifest['round'] and event['convo_id'] == convo_id
                           for event in ledger['events'])
    if first_review and not already_recorded and len(ledger['events']) >= ledger['budget']:
        raise RuntimeError('human review budget is exhausted')
    item['decision'] = decision
    item['correction'] = payload.get('correction', '')
    item['edited_case'] = payload.get('edited_case') if decision == 'fix' else None
    if first_review and not already_recorded:
        ledger['events'].append({'round': manifest['round'], 'convo_id': convo_id,
                                 'reviewed_at': datetime.now().isoformat()})
        for round_entry in ledger['rounds']:
            if round_entry['round'] == manifest['round']:
                round_entry['completed'] = round_entry.get('completed', 0) + 1
    _write_json(manifest_path, manifest)
    _write_json(ledger_path, ledger)
    return item


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
        curation = _curation_item(cid)
        verdict = curation.get('decision') if curation else (
            json.loads(fb.read_text()).get('verdict') if fb.exists() else None)
        return {'id': cid, 'persona': case.get('persona', '—'),
                'use_case': case.get('use_case', '—'), 'topic': case.get('topic', '—'),
                'title': case.get('title', cid), 'verdict': verdict,
                'flagged': case.get('flagged', False), 'kind': _scan_kind(case),
                'curation': curation is not None}

    def _scenario_list(self):
        manifest = _curation_round()
        if manifest and manifest.get('status') == 'open':
            cases = _train()
            return [self._item(cases[item['convo_id']]) for item in manifest['cases']]
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
        if p == '/api/curation':
            manifest = _curation_round()
            ledger = json.loads(CURATION_LEDGER.read_text()) if CURATION_LEDGER.exists() else None
            self._send_json({'active': bool(manifest and manifest.get('status') == 'open'),
                             'round': manifest, 'ledger': ledger})
            return
        if p.startswith('/api/curation/'):
            cid = p.rsplit('/', 1)[-1]
            item = _curation_item(cid)
            self._send_json(item or {'error': f'no curation item {cid}'}, status=200 if item else 404)
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
        if p == '/api/curation':
            manifest = _curation_round()
            if not manifest or manifest.get('status') != 'open':
                self._send_json({'error': 'no open curation round'}, status=409)
                return
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length))
            manifest['generalized_feedback'] = payload.get('generalized_feedback', '')
            CURATION_ROUND.write_text(json.dumps(manifest, indent=2) + '\n')
            self._send_json({'saved': True})
            return
        if p.startswith('/api/curation/'):
            cid = p.rsplit('/', 1)[-1]
            length = int(self.headers.get('Content-Length', 0))
            payload = json.loads(self.rfile.read(length))
            try:
                save_curation_decision(CURATION_ROUND, CURATION_LEDGER, cid, payload)
            except KeyError as error:
                self._send_json({'error': str(error)}, status=404)
                return
            except ValueError as error:
                self._send_json({'error': str(error)}, status=400)
                return
            except RuntimeError as error:
                self._send_json({'error': str(error)}, status=409)
                return
            self._send_json({'saved': True})
            return
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
