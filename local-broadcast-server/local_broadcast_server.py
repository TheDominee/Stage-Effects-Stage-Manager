#!/usr/bin/env python3
"""
Stage Effects — Local Broadcast Server
=======================================

Runs entirely on this computer, on your local Wi-Fi/network — no internet
required. It does two things at once:

  1. Stands in for a Firebase Realtime Database, using the same tiny REST
     shape (GET returns JSON at a path, PUT replaces it, PATCH merges into
     it) that Stage Manager's "Local Network Broadcast" already speaks —
     so the show state, Crew Chat, and Crew Talk voice signaling all just
     work, the same as they would against a real Firebase project.

  2. Serves the Crew and Viewer pages that live in this same folder, so
     crew phones don't need to reach GitHub Pages (or anywhere else on the
     internet) either — everything comes from this one machine.

HOW TO USE
----------
1. Double-click "Start Local Broadcast (Mac).command" or
   "Start Local Broadcast (Windows).bat" in this folder — or run this
   script directly with `python3 local_broadcast_server.py`.
2. It prints one or more addresses like "http://192.168.1.50:8765" —
   that's this computer's address on the local network right now.
3. In Stage Manager's Setup page, open "Local Network Broadcast", paste
   that address into "Local server address", and tick "Also broadcast to
   the local network". It runs alongside your normal internet broadcast
   (if any) — turning "Start Broadcasting" on sends to both.
4. Use the "Copy Local Crew Link" / "QR" buttons in that same section to
   hand out the local link — it only works for devices on this same
   network, but it never needs to leave the building.

Leave this window open for the duration of the show — closing it (or the
terminal/command window it's running in) stops the local broadcast.
Nothing here is saved to disk; closing it clears the current room's state,
same as restarting a Firebase project would.

No third-party packages needed — just Python 3's standard library.
"""

import json
import mimetypes
import os
import socket
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# In-memory tree mimicking Firebase Realtime Database REST semantics: GET
# returns the JSON at a path (including nested children), PUT replaces the
# node at a path entirely, PATCH shallow-merges the given object's keys into
# the node at that path, leaving other children untouched. This is the exact
# behavior broadcastState(), Crew Chat, and Crew Talk's voice signaling in
# Stage Manager already rely on against a real Firebase project.
STORE = {}


def split_path(path):
    return [p for p in path.strip('/').split('/') if p]


def get_at(path):
    parts = split_path(path)
    cur = STORE
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def set_at(path, value):
    parts = split_path(path)
    if not parts:
        global STORE
        STORE = value
        return
    cur = STORE
    for p in parts[:-1]:
        if not isinstance(cur.get(p), dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def patch_at(path, patch_obj):
    parts = split_path(path)
    cur = STORE
    for p in parts:
        if not isinstance(cur.get(p), dict):
            cur[p] = {}
        cur = cur[p]
    if isinstance(patch_obj, dict):
        for k, v in patch_obj.items():
            cur[k] = v


def local_ip_addresses():
    """Best-effort list of this machine's LAN IP address(es). Uses a UDP
    "connect" to a public address purely to ask the OS which local interface
    would be used to reach the outside world — no packet is actually sent,
    so this works fine even with no internet connection at all."""
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('8.8.8.8', 80))
            ips.add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith('127.'):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,PUT,PATCH,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_not_found(self):
        self.send_response(404)
        self._cors()
        self.end_headers()

    # ---- the Firebase-shaped broadcast API: any path ending in .json ----

    def do_GET(self):
        path = self.path.split('?')[0]
        if path.endswith('.json'):
            self._send_json(get_at(path[:-5]))
            return
        self._serve_static(path)

    def do_PUT(self):
        path = self.path.split('?')[0]
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        data = json.loads(raw) if raw else None
        if path.endswith('.json'):
            set_at(path[:-5], data)
            self._send_json(data)
        else:
            self._send_not_found()

    def do_PATCH(self):
        path = self.path.split('?')[0]
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        data = json.loads(raw) if raw else {}
        if path.endswith('.json'):
            patch_at(path[:-5], data)
            self._send_json(data)
        else:
            self._send_not_found()

    # ---- static file serving: the Crew/Viewer pages, from this same folder ----

    def _serve_static(self, path):
        if path == '/':
            self._send_index()
            return
        # No subdirectories, no path traversal — this only ever serves a
        # single file sitting directly alongside this script.
        name = path.lstrip('/')
        if '/' in name or '..' in name:
            self._send_not_found()
            return
        full = os.path.join(SCRIPT_DIR, name)
        if not os.path.isfile(full):
            self._send_not_found()
            return
        ctype = mimetypes.guess_type(full)[0] or 'application/octet-stream'
        with open(full, 'rb') as f:
            body = f.read()
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_index(self):
        ips = local_ip_addresses()
        addr = ips[0] if ips else '127.0.0.1'
        base = 'http://%s:%d' % (addr, PORT)
        has_crew = os.path.isfile(os.path.join(SCRIPT_DIR, 'Stage_Effects_Crew.html'))
        has_viewer = os.path.isfile(os.path.join(SCRIPT_DIR, 'Stage_Effects_Viewer.html'))
        links = ''
        if has_crew:
            links += '<a class="btn" href="/Stage_Effects_Crew.html">Open Crew Page</a>'
        if has_viewer:
            links += '<a class="btn" href="/Stage_Effects_Viewer.html">Open Viewer Page</a>'
        body = (
            '<!doctype html><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>Local Broadcast Server</title>'
            '<body style="font:17px system-ui;max-width:420px;margin:64px auto;'
            'padding:0 20px;text-align:center;color:#222;">'
            '<h1 style="font-size:20px;margin-bottom:36px;">'
            '<span style="color:#2ecc71;">&#9679;</span> Local Broadcast Server '
            'is running</h1>'
            '<p style="color:#666;margin-bottom:10px;">Enter this address in Stage Manager, '
            'under Setup &rarr; Local Network Broadcast:</p>'
            '<p style="font-size:22px;font-weight:600;background:#f0f0f0;border-radius:10px;'
            'padding:14px;margin-bottom:36px;word-break:break-all;">%s</p>'
            '<div style="display:flex;flex-direction:column;gap:12px;">%s</div>'
            '<style>.btn{display:block;padding:14px;border-radius:10px;background:#111;'
            'color:#fff;text-decoration:none;font-weight:600;}</style>'
            '</body>'
        ) % (base, links)
        body_bytes = body.encode()
        self.send_response(200)
        self._cors()
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)

    def log_message(self, fmt, *args):
        pass  # quiet by default — the banner below is what matters


def main():
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    ips = local_ip_addresses()
    print('=' * 64)
    print(' Stage Effects — Local Broadcast Server')
    print('=' * 64)
    print()
    if ips:
        print(' Give Stage Manager this address (Setup > Local Network Broadcast):')
        for ip in ips:
            print('   http://%s:%d' % (ip, PORT))
    else:
        print(' Could not detect a network address automatically.')
        print(' Try: http://127.0.0.1:%d  (only works on this same computer)' % PORT)
    print()
    print(' Crew/Viewer pages in this folder are served from that same address, e.g.')
    if ips:
        print('   http://%s:%d/Stage_Effects_Crew.html' % (ips[0], PORT))
    print()
    print(' Leave this window open for the duration of the show.')
    print(' Press Ctrl+C to stop.')
    print('=' * 64)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')


if __name__ == '__main__':
    main()
