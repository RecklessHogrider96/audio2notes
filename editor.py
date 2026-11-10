"""Local note editor: serves the piano-roll player with editing turned on, and saves cleaned notes.

Usage: python3 editor.py out/PREFIX "Title" [START_SECONDS]
  Reads  out/PREFIX.json         (the raw transcription; never modified)
  Loads  out/PREFIX_edited.json  (your saved edits, if they belong to that same transcription)
  Saves  out/PREFIX_edited.json and out/PREFIX_edited.mid when you press Save

Env: EDITOR_PORT (default: any free port), NO_OPEN=1 (don't open the browser).
"""
import hashlib, json, os, subprocess, sys
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from transcribe import write_midi  # noqa: E402

prefix, title = sys.argv[1], sys.argv[2]
start = sys.argv[3] if len(sys.argv) > 3 else '0'
RAW, ED_JSON, ED_MID = prefix + '.json', prefix + '_edited.json', prefix + '_edited.mid'
KEY = os.path.basename(prefix)


def safe_json(o):
    return json.dumps(o).replace('</', '<\\/')


def load_state():
    raw = open(RAW, 'rb').read()
    fingerprint = hashlib.sha1(raw).hexdigest()
    original = json.loads(raw)
    notes, loaded, stale = original, False, False
    if os.path.exists(ED_JSON):
        try:
            ed = json.load(open(ED_JSON))
            if ed.get('transcription') == fingerprint:
                notes, loaded = ed['notes'], True
            else:
                stale = True
        except (ValueError, KeyError):
            stale = True
    return fingerprint, original, notes, loaded, stale


def clean_notes(items):
    out = []
    for n in items:
        p, s, d, v = int(n['pitch']), float(n['start']), float(n['dur']), int(n['vel'])
        if not (0 <= p <= 127 and s >= 0 and d > 0):
            raise ValueError('bad note')
        out.append({'pitch': p, 'start': round(s, 3), 'dur': round(d, 3), 'vel': max(1, min(127, v))})
    out.sort(key=lambda n: (n['start'], n['pitch']))
    return out


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _host_ok(self):
        return self.headers.get('Host', '') in (f'127.0.0.1:{PORT}', f'localhost:{PORT}')

    def _send(self, code, body, ctype):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return self._send(403, 'forbidden', 'text/plain')
        if self.path not in ('/', '/index.html'):
            return self._send(404, 'not found', 'text/plain')
        _, original, notes, loaded, stale = load_state()
        editor = {'title': title, 'start': start, 'original': original if loaded else None,
                  'loadedEdits': loaded, 'staleEdits': stale}
        html = open(os.path.join(HERE, 'player_template.html')).read()
        html = html.replace('__DATA__', safe_json({KEY: {'title': title, 'notes': notes}}))
        html = html.replace('__EDITOR__', safe_json(editor))
        self._send(200, html, 'text/html; charset=utf-8')

    def do_POST(self):
        # JSON content type forces a CORS preflight, which this server never approves,
        # so other websites can't write here; the Host check blocks DNS rebinding.
        if self.path != '/save' or not self._host_ok() or \
                not self.headers.get('Content-Type', '').startswith('application/json'):
            return self._send(403, json.dumps({'ok': False, 'error': 'forbidden'}), 'application/json')
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 20_000_000:
                raise ValueError('too large')
            notes = clean_notes(json.loads(self.rfile.read(length))['notes'])
            fingerprint = load_state()[0]
            tmp = ED_JSON + '.tmp'
            with open(tmp, 'w') as f:
                json.dump({'transcription': fingerprint, 'title': title, 'start': start, 'notes': notes}, f)
            os.replace(tmp, ED_JSON)
            write_midi(notes, ED_MID + '.tmp')
            os.replace(ED_MID + '.tmp', ED_MID)
            print(f'Saved {len(notes)} notes -> {ED_MID}', flush=True)
            self._send(200, json.dumps({'ok': True, 'count': len(notes), 'midi': os.path.relpath(ED_MID, HERE)}),
                       'application/json')
        except Exception as e:  # report to the page instead of crashing the server
            self._send(400, json.dumps({'ok': False, 'error': str(e)}), 'application/json')


server = ThreadingHTTPServer(('127.0.0.1', int(os.environ.get('EDITOR_PORT', 0))), Handler)
PORT = server.server_address[1]
url = f'http://127.0.0.1:{PORT}/'
print(f'Note editor: {url}')
print(f'Saving writes {ED_MID}')
print('Keep this window open while you edit. Press Ctrl+C here when you are done.', flush=True)
if not os.environ.get('NO_OPEN'):
    subprocess.run(['open', url])
try:
    server.serve_forever()
except KeyboardInterrupt:
    print('\nEditor closed.')
