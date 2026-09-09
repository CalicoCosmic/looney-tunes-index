#!/usr/bin/env python3
"""
Looney Tunes Catalog Local Backend & API Server
-----------------------------------------------
Serves the search engine interface and provides REST endpoints for
live manual editing of cartoon entries.

Runs with ZERO external dependencies (standard Python library only).
"""

import http.server
import json
import os
import sys
import urllib.parse
from http import HTTPStatus

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_JSON_PATH = os.path.join(BASE_DIR, 'database.json')
DB_JS_PATH = os.path.join(BASE_DIR, 'database.js')
OVERRIDES_PATH = os.path.join(BASE_DIR, 'custom_overrides.json')

def load_database():
    if os.path.exists(DB_JSON_PATH):
        try:
            with open(DB_JSON_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'[-] Error loading {DB_JSON_PATH}: {e}')
    return []

def load_overrides():
    if os.path.exists(OVERRIDES_PATH):
        try:
            with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'[-] Error loading {OVERRIDES_PATH}: {e}')
    return {}

def save_all(database, overrides):
    # 1. Save overrides
    with open(OVERRIDES_PATH, 'w', encoding='utf-8') as f:
        json.dump(overrides, f, indent=2, ensure_ascii=False)
        f.write('\n')
    
    # 2. Save database.json
    database.sort(key=lambda x: (x.get('year') or 9999, x.get('title', '')))
    with open(DB_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(database, f, indent=2, ensure_ascii=False)
        f.write('\n')

    # 3. Save database.js
    with open(DB_JS_PATH, 'w', encoding='utf-8') as f:
        f.write('window.LOONEY_TUNES_DATABASE = ' + json.dumps(database, indent=2, ensure_ascii=False) + ';\n')

class CatalogRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def send_json(self, data, status=HTTPStatus.OK):
        payload = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path == '/api/status':
            db = load_database()
            ov = load_overrides()
            return self.send_json({
                'status': 'ok',
                'cartoons_count': len(db),
                'overrides_count': len(ov)
            })

        if path == '/api/cartoons':
            db = load_database()
            return self.send_json(db)

        if path.startswith('/api/cartoons/'):
            cartoon_id = urllib.parse.unquote(path[len('/api/cartoons/'):])
            db = load_database()
            for c in db:
                if c.get('id') == cartoon_id or c.get('title', '').lower() == cartoon_id.lower():
                    return self.send_json(c)
            return self.send_json({'error': 'Cartoon not found'}, status=HTTPStatus.NOT_FOUND)

        # Fallback to standard static file serving (index.html, database.js, etc.)
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path.startswith('/api/cartoons/'):
            cartoon_id = urllib.parse.unquote(path[len('/api/cartoons/'):])
            content_len = int(self.headers.get('Content-Length', 0))
            body_raw = self.rfile.read(content_len)
            try:
                updates = json.loads(body_raw.decode('utf-8'))
            except Exception as e:
                return self.send_json({'error': f'Invalid JSON: {e}'}, status=HTTPStatus.BAD_REQUEST)

            db = load_database()
            overrides = load_overrides()
            found_idx = None

            for idx, c in enumerate(db):
                if c.get('id') == cartoon_id or c.get('title', '').lower() == cartoon_id.lower():
                    found_idx = idx
                    break

            if found_idx is None:
                return self.send_json({'error': 'Cartoon not found'}, status=HTTPStatus.NOT_FOUND)

            target = db[found_idx]
            
            # Key updates to persist
            editable_fields = [
                'title', 'year', 'release_date', 'series', 'director', 'director_credit', 
                'directors', 'director_aliases', 'story', 'layout', 
                'backgrounds', 'animation', 'voice_actors', 
                'featured_characters', 'synopsis', 'media_locations'
            ]

            saved_override = overrides.setdefault(target['id'], {})

            for k in editable_fields:
                if k in updates:
                    target[k] = updates[k]
                    saved_override[k] = updates[k]

            save_all(db, overrides)
            print(f'[✓] Updated cartoon: {target["title"]} ({target.get("year")})')
            return self.send_json({
                'success': True,
                'message': f'Updated {target["title"]} successfully.',
                'cartoon': target
            })

        self.send_json({'error': 'Endpoint not found'}, status=HTTPStatus.NOT_FOUND)

def main():
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])

    server = http.server.ThreadingHTTPServer(('127.0.0.1', port), CatalogRequestHandler)
    print('=' * 70)
    print(f'🎬 Looney Tunes Catalog & Editor Server Running!')
    print(f'🌐 Web Interface: http://127.0.0.1:{port}')
    print(f'📁 Serving from:  {BASE_DIR}')
    print('=' * 70)
    print('Press Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n[!] Server stopped.')

if __name__ == '__main__':
    main()
