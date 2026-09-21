#!/usr/bin/env python3
"""
Stage Effects / Spaan — Local Broadcast (one-click app)
=========================================================

This is the same offline local-network broadcast as before, but packaged as
a single double-clickable app instead of a script you run from a terminal.
There is nothing to install and nothing to type: double-click it, a window
opens showing two QR codes, crew scan the one they need, done.

Stage Effects and Spaan are two completely separate acts and always build
and run as two separate apps (see the BRANDS dict below) — each app only
ever knows about its own brand's Stage Manager/Crew/Viewer pages, and its
window only ever shows that one brand. There is no shared, both-brands-at-
once launcher. This file holds the shared implementation; the actual
double-clickable apps are tiny wrapper entry points (this file itself for
Stage Effects, local_broadcast_app_spaan.py for Spaan) that just pick which
brand to run as — see main() at the bottom.

Runs entirely on this computer, on your local Wi-Fi/network — no internet
required. It does three things at once:

  1. Stands in for a Firebase Realtime Database, using the same tiny REST
     shape (GET returns JSON at a path, PUT replaces it, PATCH merges into
     it) that Stage Manager's "Local Network Broadcast" already speaks —
     so the show state, Crew Chat, and Crew Talk voice signaling all just
     work, the same as they would against a real Firebase project.

  2. Serves the Crew and Viewer pages (and this brand's Stage Manager
     control panel) that live in this same folder, so crew phones don't
     need to reach GitHub Pages (or anywhere else on the internet) either —
     everything comes from this one machine.

  3. Serves all of the above over HTTPS, using a self-signed certificate
     this app generates and keeps on this computer (see the CERT section
     below) — so Crew Talk's microphone access works too, with zero
     internet, which plain http can never do (browsers only expose the
     microphone on a "secure context": https, or loopback).

HOW TO USE
----------
1. Double-click this app. A window opens with this computer's address, two
   QR codes (Crew / Viewer), and an "Open Stage Manager" button.
2. The FIRST time, your browser will warn that the connection isn't
   private — that's expected, this is a self-signed certificate this app
   made just for this computer, not a real security problem. Click through
   it (e.g. "Advanced" -> "Proceed"/"visit this website") once per device;
   it won't ask again on that device for this computer's address.
3. Click "Open Stage Manager" (or visit this computer's address shown in
   the window) rather than the usual github.io link — this is what makes
   local broadcast work in every browser, Windows or Mac, Safari included.
   Stage Manager then finds this app on its own automatically, nothing to
   type in Setup.
4. Hand crew the QR code for the page they need, or use the Copy Link
   buttons. It only works for devices on this same network, but it never
   needs to leave the building.

CERTIFICATE (why the one-time "not private" warning, and how it's avoided
after that)
------------------------------------------------------------------------
A normal (CA-signed) https certificate has to be issued by someone the
browser already trusts, which means proving you own a public domain name —
meaningless for a laptop on a venue's private Wi-Fi with no internet. So
this app makes its own ("self-signed") certificate instead, covering every
IP address this computer has ever used with it (kept in
~/.stage_effects_local_broadcast/, alongside the certificate itself, so a
venue's network this computer has visited before never re-prompts). The
browser can't verify a self-signed certificate against anyone, so it warns
once — that's the "scary warning" — but the connection itself is exactly as
encrypted as any other https connection, it just isn't vouched for by a
public certificate authority. Clicking through it is a one-time thing per
device, not per show.

MIXED CONTENT (why "Open Stage Manager" from here, not the usual link)
------------------------------------------------------------------------
The usual Stage Manager link is served over https (GitHub Pages). Browsers
block an https page's own requests to a plain http:// address unless it's
loopback (127.0.0.1) — and even that exemption isn't consistent across
browsers (Chrome/Edge/Firefox honor it, Safari has historically been
stricter). Serving this app itself over https too (see CERTIFICATE above)
sidesteps this entirely — an https page talking to another https address is
never "mixed content", in any browser.

Leave this window open for the duration of the show — closing it stops the
local broadcast for anyone using it. Nothing here is saved to disk (besides
the certificate above); closing it clears the current room's state, same as
restarting a Firebase project would.
"""

import datetime
import ipaddress
import json
import mimetypes
import os
import socket
import ssl
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import messagebox
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# Brands — Stage Effects and Spaan always run as two separate apps. Whichever
# one this process is (set by main(), called from this file's own __main__
# below for Stage Effects, or from local_broadcast_app_spaan.py for Spaan),
# BRAND is the only brand this running app ever knows about.
# ---------------------------------------------------------------------------
BRANDS = {
    'stage_effects': {
        'app_name': 'Stage Effects — Local Broadcast',
        'brand_label': 'Stage Effects',
        'sm_file': 'Stage_Effects_Stage_Manager.html',
        'crew_file': 'Stage_Effects_Crew.html',
        'viewer_file': 'Stage_Effects_Viewer.html',
        'default_port': 8765,
    },
    'spaan': {
        'app_name': 'Spaan — Local Broadcast',
        'brand_label': 'Spaan',
        'sm_file': 'Spaan_Stage_Manager_Countdown.html',
        'crew_file': 'Spaan_Crew.html',
        'viewer_file': 'Spaan_Viewer.html',
        'default_port': 8766,
    },
}

APP_ID = 'stage-effects-local-broadcast'
APP_VERSION = 3  # bumped: brand-split + https
BRAND_ID = 'stage_effects'   # overwritten by main() before anything starts
BRAND = BRANDS[BRAND_ID]
APP_NAME = BRAND['app_name']
PORT = 8765                  # overwritten by main()

# PyInstaller unpacks bundled data files (the brand's HTML pages) next to a
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


# ---------------------------------------------------------------------------
# Self-signed HTTPS certificate
# ---------------------------------------------------------------------------
# Kept in the user's home directory (not next to the app, which may be
# read-only or re-downloaded/replaced) so it survives across app restarts
# and across Stage Effects/Spaan both running on the same computer — one
# certificate, shared by both brands, covering every IP this computer has
# ever broadcast from, is what lets a device that already clicked through
# the warning once for a known venue never see it again there, no matter
# which brand's app it's talking to.
CERT_DIR = os.path.join(os.path.expanduser('~'), '.stage_effects_local_broadcast')
CERT_PATH = os.path.join(CERT_DIR, 'cert.pem')
KEY_PATH = os.path.join(CERT_DIR, 'key.pem')
KNOWN_IPS_PATH = os.path.join(CERT_DIR, 'known_ips.json')


def _load_known_ips():
    try:
        with open(KNOWN_IPS_PATH) as f:
            return set(json.load(f))
    except Exception:
        return set()


def _save_known_ips(ips):
    os.makedirs(CERT_DIR, exist_ok=True)
    with open(KNOWN_IPS_PATH, 'w') as f:
        json.dump(sorted(ips), f)


def _san_entries(ips):
    from cryptography import x509
    names = [x509.DNSName('localhost')]
    seen = set()
    for ip in sorted({'127.0.0.1'} | set(ips)):
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if addr in seen:
            continue
        seen.add(addr)
        names.append(x509.IPAddress(addr))
    return names


def _generate_cert(ips):
    """Writes a fresh self-signed cert/key covering every IP in `ips` (plus
    localhost/127.0.0.1) to CERT_PATH/KEY_PATH, valid for ~10 years so it's
    effectively a one-time thing per computer, not per show."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u'Local Broadcast (self-signed)')])
    now = datetime.datetime.utcnow()
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(_san_entries(ips)), critical=False)
        .sign(key, hashes.SHA256())
    )
    os.makedirs(CERT_DIR, exist_ok=True)
    with open(KEY_PATH, 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(CERT_PATH, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    _save_known_ips(ips)


def ensure_cert(ssl_context=None):
    """Makes sure a certificate covering every IP this computer currently
    has exists, generating/regenerating one if needed, and (if an already-
    running ssl_context is given) hot-swaps it in so already-accepted
    connections are undisturbed and only new ones pick up the change —
    called once at startup, and again from the address-refresh loop
    whenever a genuinely new IP shows up (e.g. arriving at a new venue),
    so a previously-seen network never re-prompts but a brand new one is
    covered within a few seconds without needing a restart."""
    known = _load_known_ips()
    current = set(local_ip_addresses())
    need_new = (
        not os.path.isfile(CERT_PATH)
        or not os.path.isfile(KEY_PATH)
        or not current.issubset(known)
    )
    if need_new:
        known |= current
        try:
            _generate_cert(known)
        except Exception:
            # Cert generation failing shouldn't take the whole app down —
            # surfaced to the user via the window's status area instead by
            # the caller checking os.path.isfile(CERT_PATH) after this.
            return False
    if ssl_context is not None and os.path.isfile(CERT_PATH) and os.path.isfile(KEY_PATH):
        ssl_context.load_cert_chain(CERT_PATH, KEY_PATH)
    return True


def build_ssl_context():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ensure_cert(ctx)
    return ctx


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
            'brand': BRAND_ID,
            'brandLabel': BRAND['brand_label'],
            'version': APP_VERSION,
            'port': PORT,
            'scheme': 'https',
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

    # ---- static file serving: this brand's Crew/Viewer/Stage Manager pages,
    # from this same folder ----

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
        base = 'https://%s:%d' % (addr, PORT)
        has_sm = os.path.isfile(os.path.join(SCRIPT_DIR, BRAND['sm_file']))
        has_crew = os.path.isfile(os.path.join(SCRIPT_DIR, BRAND['crew_file']))
        has_viewer = os.path.isfile(os.path.join(SCRIPT_DIR, BRAND['viewer_file']))
        links = ''
        # Absolute (not relative) links throughout: this index page might get
        # reached via a loopback address (someone typed 127.0.0.1) even though
        # the useful address for anything handed to another device is the LAN
        # one -- absolute links mean every button always lands on the right
        # address regardless of how this page itself was reached.
        if has_sm:
            links += '<a class="btn btn-primary" href="%s/%s">Open Stage Manager</a>' % (base, BRAND['sm_file'])
        if has_crew:
            links += '<a class="btn" href="%s/%s">Open Crew Page</a>' % (base, BRAND['crew_file'])
        if has_viewer:
            links += '<a class="btn" href="%s/%s">Open Viewer Page</a>' % (base, BRAND['viewer_file'])
        intro = (
            '<p style="color:#666;margin-bottom:10px;">Open Stage Manager from the button below '
            '&mdash; it works in every browser this way, Safari included. This computer\'s address:</p>'
            if has_sm else
            '<p style="color:#666;margin-bottom:10px;">Enter this address in Stage Manager, '
            'under Setup &rarr; Local Network Broadcast:</p>'
        )
        body = (
            '<!doctype html><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            '<title>%s — Local Broadcast</title>'
            '<body style="font:17px system-ui;max-width:420px;margin:64px auto;'
            'padding:0 20px;text-align:center;color:#222;">'
            '<h1 style="font-size:20px;margin-bottom:36px;">'
            '<span style="color:#2ecc71;">&#9679;</span> %s Local Broadcast '
            'is running</h1>'
            '%s'
            '<p style="font-size:22px;font-weight:600;background:#f0f0f0;border-radius:10px;'
            'padding:14px;margin-bottom:36px;word-break:break-all;">%s</p>'
            '<div style="display:flex;flex-direction:column;gap:12px;">%s</div>'
            '<style>.btn{display:block;padding:14px;border-radius:10px;background:#111;'
            'color:#fff;text-decoration:none;font-weight:600;}'
            '.btn-primary{background:#FF9500;color:#131F1B;}</style>'
            '</body>'
        ) % (BRAND['brand_label'], BRAND['brand_label'], intro, base, links)
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
    def __init__(self, root, server, port, ssl_context):
        self.root = root
        self.server = server
        self.port = port
        self.ssl_context = ssl_context
        self.last_addr = None
        self.known_ips = _load_known_ips()

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
        tk.Label(header, text='●  %s — Local Broadcast is running' % BRAND['brand_label'], fg='#3FD07F',
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

        # One brand, one Stage Manager build -- one button, no brand suffix
        # needed since this whole window is already that one brand (see the
        # module docstring: Stage Effects and Spaan never share a window).
        self.has_sm = os.path.isfile(os.path.join(SCRIPT_DIR, BRAND['sm_file']))
        if self.has_sm:
            sm_frame = tk.Frame(root, bg='#131F1B')
            sm_frame.pack(fill='x', padx=28, pady=(0, 4))
            tk.Button(sm_frame, text='Open Stage Manager', command=self.open_stage_manager,
                      bg='#FF9500', fg='#131F1B', activebackground='#FFB443',
                      relief='flat', font=small, padx=10, pady=8).pack(fill='x', pady=4)

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

    def open_stage_manager(self):
        # Deliberately 127.0.0.1, NOT self.last_addr (the LAN address used
        # for crew's QR codes/links). This button always runs on the same
        # computer as this app, so localhost reaches it just fine, and
        # avoids one extra click-through of the certificate warning (this
        # computer already trusts its own loopback cert the same as any
        # other address it's generated for, but 127.0.0.1 is always in the
        # certificate from the very first run, before this computer's real
        # LAN IP is even known).
        if not self.last_addr or 'detecting' in (self.last_addr or ''):
            return  # address not known yet, e.g. clicked in the first instant after launch
        webbrowser.open('https://127.0.0.1:%d/%s' % (self.port, BRAND['sm_file']))

    def _copy(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()

    def refresh_address(self):
        ips = local_ip_addresses()
        addr = ips[0] if ips else '127.0.0.1'
        base = 'https://%s:%d' % (addr, self.port)

        # A genuinely new IP (new venue/network) needs a fresh certificate
        # covering it -- hot-swapped into the already-running TLS listener
        # so this doesn't need a restart. Already-known IPs (a venue this
        # computer has broadcast from before) never regenerate, which is
        # what keeps the "not private" warning to a true one-time thing per
        # device per venue instead of every show.
        current_ips = set(ips)
        if not current_ips.issubset(self.known_ips):
            self.known_ips |= current_ips
            ensure_cert(self.ssl_context)

        if base != self.last_addr:
            self.last_addr = base
            self.addr_label.config(text=base)

            crew_link = base + '/' + BRAND['crew_file']
            viewer_link = base + '/' + BRAND['viewer_file']
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


def _fatal_error(title, message):
    """Best-effort GUI error box for a startup failure that would otherwise
    just be a silent crash or a console traceback nobody double-clicking an
    app ever sees."""
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message)
        root.destroy()
    except Exception:
        print('%s: %s' % (title, message), file=sys.stderr)


def main(brand_id='stage_effects', port=None):
    global BRAND_ID, BRAND, APP_NAME, PORT

    if brand_id not in BRANDS:
        brand_id = 'stage_effects'
    BRAND_ID = brand_id
    BRAND = BRANDS[BRAND_ID]
    APP_NAME = BRAND['app_name']

    if port is None:
        # `python3 local_broadcast_app.py 9000` still works for anyone
        # running from source who wants a specific port.
        port = int(sys.argv[1]) if len(sys.argv) > 1 else BRAND['default_port']
    PORT = port

    try:
        import cryptography  # noqa: F401
    except ImportError:
        _fatal_error(
            APP_NAME,
            "This app needs the 'cryptography' package to serve itself over "
            "HTTPS (needed for Crew Talk's microphone to work). If you're "
            "running this from source, install it with:\n\n"
            "    pip install cryptography\n\n"
            "The downloadable app from GitHub already includes it."
        )
        sys.exit(1)

    ssl_context = build_ssl_context()
    if not os.path.isfile(CERT_PATH):
        _fatal_error(APP_NAME, "Couldn't create the certificate needed for HTTPS. "
                                "Check that %s is writable, then try again." % CERT_DIR)
        sys.exit(1)

    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    server.socket = ssl_context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    root = tk.Tk()
    App(root, server, PORT, ssl_context)
    root.mainloop()


if __name__ == '__main__':
    main('stage_effects')
