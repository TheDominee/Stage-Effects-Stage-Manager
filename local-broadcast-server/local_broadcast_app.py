#!/usr/bin/env python3
"""
Stage Effects — Local Broadcast (one-click app)
=================================================

This is the same offline local-network broadcast as before, but packaged as
a single double-clickable app instead of a script you run from a terminal.
There is nothing to install and nothing to type: double-click it, a window
opens showing two QR codes, crew scan the one they need, done.

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
1. Double-click this app. A window opens with this computer's address and
   two QR codes (Crew / Viewer).
2. In Stage Manager's Setup page, open "Local Network Broadcast" and paste
   in the address shown (or, if Stage Manager is running on this same
   computer, it will usually find it on its own — a banner appears there
   offering to turn it on with one click, nothing to type).
3. Hand crew the QR code for the page they need, or use the Copy Link
   buttons. It only works for devices on this same network, but it never
   needs to leave the building.

Leave this window open for the duration of the show — closing it stops the
local broadcast for anyone using it. Nothing here is saved to disk; closing
it clears the current room's state, same as restarting a Firebase project
would.
"""

import json
import mimetypes
import os
import socket
import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP_NAME = 'Stage Effects — Local Broadcast'
APP_ID = 'stage-effects-local-broadcast'
APP_VERSION = 2
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765

# PyInstaller unpacks bundled data files (the Crew/Viewer HTML) next to a
# temp folder given in sys._MEIPASS at runtime; a plain `python3
# local_broadcast_app.py` run (e.g. while developing) has no such folder, so
# fall back to this script's own directory in that case.
SCRIPT_DIR = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

# In-memory tree mimicking Firebase Realtime Database REST semantics: GET
# returns the JSON at a path (including nested children), PUT replaces the
# node at a path entirely, PATCH shallow-merges the given object's keys into
# the node at that path, leaving other children untouched. This is the exact
# behavior broadcastState(), Crew Chat, and Crew Talk's voice signaling in
# Stage Manager already rely on against a real Firebase project.
STORE = {}
STORE_LOCK = threading.Lock()


def split_path(path):
    return [p for p in path.strip('/').split('/') if p]


def get_at(path):
    with STORE_LOCK:
        parts = split_path(path)
        cur = STORE
        for p in parts:
            if not isinstance(cur, dict) or p not in cur:
                return None
            cur = cur[p]
        return cur


def set_at(path, value):
    with STORE_LOCK:
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
    with STORE_LOCK:
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

    # ---- identification endpoint: lets Stage Manager's Setup page confirm
    # a server on some address is genuinely this app (not just anything
    # else happening to listen on the same port) before offering to enable
    # local broadcast automatically. Also hands back this machine's actual
    # LAN IP, since Stage Manager itself only ever reaches this endpoint via
    # 127.0.0.1/localhost (loopback) -- an address that's meaningless to any
    # other device on the network. Crew phones need the real address, so
    # that's what gets used to fill in the Local server address field, not
    # the loopback address this request happened to arrive on. ----
    def _send_meta(self):
        ips = local_ip_addresses()
        self._send_json({
            'app': APP_ID,
            'version': APP_VERSION,
            'port': PORT,
            'lan_ip': ips[0] if ips else None,
        })

    # ---- the Firebase-shaped broadcast API: any path ending in .json ----

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/__stage_effects_meta':
            self._send_meta()
            return
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
            '<span style="color:#2ecc71;">&#9679;</span> Local Broadcast '
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
        pass  # quiet — the window is what matters, not a console


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

# Kept dependency-free on purpose (qrcode's matrix output, drawn by hand on a
# Tkinter Canvas) so the only extra piece PyInstaller has to bundle is the
# `qrcode` package itself — no Pillow, no image codecs, smaller and more
# reliable standalone builds on both Mac and Windows.
def draw_qr(canvas, data, box_size=6, border=2):
    import qrcode
    qr = qrcode.QRCode(border=border)
    qr.add_data(data)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    n = len(matrix)
    px = n * box_size
    canvas.config(width=px, height=px)
    canvas.delete('all')
    canvas.create_rectangle(0, 0, px, px, fill='#ffffff', outline='')
    for r, row in enumerate(matrix):
        for c, dark in enumerate(row):
            if dark:
                x0, y0 = c * box_size, r * box_size
                canvas.create_rectangle(x0, y0, x0 + box_size, y0 + box_size,
                                         fill='#111111', outline='')
    return px


class App:
    def __init__(self, root, server, port):
        self.root = root
        self.server = server
        self.port = port
        self.last_addr = None

        root.title(APP_NAME)
        root.configure(bg='#131F1B')
        root.geometry('720x560')
        root.minsize(640, 520)
        root.protocol('WM_DELETE_WINDOW', self.on_quit)

        mono = tkfont.Font(family='Courier New', size=15, weight='bold')
        big = tkfont.Font(family='Helvetica', size=17, weight='bold')
        small = tkfont.Font(family='Helvetica', size=11)

        header = tk.Frame(root, bg='#131F1B')
        header.pack(fill='x', pady=(22, 8))
        tk.Label(header, text='●  Local Broadcast is running', fg='#3FD07F',
                  bg='#131F1B', font=big).pack()
        tk.Label(header, text='Leave this window open for the duration of the show.',
                  fg='#7E9088', bg='#131F1B', font=small).pack(pady=(2, 0))

        addr_frame = tk.Frame(root, bg='#182620')
        addr_frame.pack(fill='x', padx=28, pady=14)
        self.addr_label = tk.Label(addr_frame, text='detecting address…', fg='#FFB443',
                                    bg='#182620', font=mono, pady=12)
        self.addr_label.pack(side='left', padx=16, fill='x', expand=True)
        copy_btn = tk.Button(addr_frame, text='Copy Address', command=self.copy_address,
                              bg='#FF9500', fg='#131F1B', activebackground='#FFB443',
                              relief='flat', font=small, padx=10, pady=6)
        copy_btn.pack(side='right', padx=12)

        qr_frame = tk.Frame(root, bg='#131F1B')
        qr_frame.pack(fill='both', expand=True, pady=6)

        self.crew_col = self._make_qr_column(qr_frame, 'Crew')
        self.viewer_col = self._make_qr_column(qr_frame, 'Viewer')

        footer = tk.Frame(root, bg='#131F1B')
        footer.pack(fill='x', pady=(6, 18))
        tk.Button(footer, text='Quit', command=self.on_quit, bg='#182620', fg='#EFF3F0',
                  activebackground='#1D2E27', relief='flat', font=small,
                  padx=16, pady=8).pack()

        self.refresh_address()

    def _make_qr_column(self, parent, label):
        col = tk.Frame(parent, bg='#131F1B')
        col.pack(side='left', expand=True, fill='both', padx=18)
        tk.Label(col, text=label, fg='#EFF3F0', bg='#131F1B',
                  font=('Helvetica', 14, 'bold')).pack(pady=(4, 8))
        canvas = tk.Canvas(col, bg='#ffffff', highlightthickness=0)
        canvas.pack()
        copy_btn = tk.Button(col, text='Copy %s Link' % label, bg='#182620', fg='#EFF3F0',
                              activebackground='#1D2E27', relief='flat',
                              font=('Helvetica', 10), padx=8, pady=5)
        copy_btn.pack(pady=(10, 0))
        return {'canvas': canvas, 'copy_btn': copy_btn, 'link': ''}

    def copy_address(self):
        self._copy(self.addr_label.cget('text'))

    def _copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def refresh_address(self):
        ips = local_ip_addresses()
        addr = ips[0] if ips else '127.0.0.1'
        base = 'http://%s:%d' % (addr, self.port)
        if base != self.last_addr:
            self.last_addr = base
            self.addr_label.config(text=base)

            crew_link = base + '/Stage_Effects_Crew.html'
            viewer_link = base + '/Stage_Effects_Viewer.html'
            self.crew_col['link'] = crew_link
            self.viewer_col['link'] = viewer_link
            self.crew_col['copy_btn'].config(command=lambda: self._copy(crew_link))
            self.viewer_col['copy_btn'].config(command=lambda: self._copy(viewer_link))
            draw_qr(self.crew_col['canvas'], crew_link)
            draw_qr(self.viewer_col['canvas'], viewer_link)

        # Wi-Fi can drop and reconnect mid-show with a new address — keep
        # checking so the window (and its QR codes) never go stale.
        self.root.after(4000, self.refresh_address)

    def on_quit(self):
        try:
            self.server.shutdown()
        except Exception:
            pass
        self.root.destroy()


def main():
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    root = tk.Tk()
    App(root, server, PORT)
    root.mainloop()


if __name__ == '__main__':
    main()
