STAGE EFFECTS — LOCAL BROADCAST
=================================

What this is
-------------
A small, offline stand-in for the internet broadcast Stage Manager normally
uses. Run it on the same computer as Stage Manager and crew phones on the
SAME WI-FI can see the live countdown, Crew Chat, and use Crew Talk voice —
even with no internet connection at all. It runs ALONGSIDE your normal
internet broadcast, not instead of it, so you can keep both going: the
internet link still reaches anyone anywhere, while this local link keeps
working for everyone in the building even if the venue's internet is
struggling under a crowd.

Getting the app (one time, or whenever you want the newest version)
----------------------------------------------------------------------
This is built automatically on GitHub, so there's nothing to install to get
it — just download the ready-to-run file:

  1. Open this repository on GitHub, in the "Releases" section (or go
     straight to the "Local Broadcast — latest build" release).
  2. Download the file for your computer:
       - Mac:      "Stage Effects Local Broadcast (Mac).zip" — unzip it,
                    you'll get "Stage Effects Local Broadcast.app".
       - Windows:  "Stage Effects Local Broadcast.exe"
  3. Put it somewhere handy (Desktop, or this folder) — that's it, no
     installer, no Python, nothing else to set up.

Every show
-----------
1. Double-click the app.
     - Mac, first time only: it'll say it's from an "unidentified
       developer" — right-click (or Control-click) it and choose "Open"
       instead of double-clicking, then confirm. Only needed once.
     - Windows, first time only: it may show "Windows protected your PC" —
       click "More info", then "Run anyway". Only needed once.
2. A window opens showing this computer's address and two QR codes (Crew /
   Viewer). Leave it open for the duration of the show — closing it stops
   the local broadcast for anyone using it.
3. In Stage Manager's Setup page, open "Local Network Broadcast". If Stage
   Manager is running on this same computer, it should find the app on its
   own and offer to turn it on with one click. Otherwise, type in the
   address shown in the app's window and tick "Also broadcast to the local
   network".
4. Click "Start Broadcasting" as usual (or turn it on if it's already on)
   — it now sends to both the internet and this local broadcast at once.
5. Hand crew the QR code from the app's window for the page they need
   (Crew or Viewer), or use its Copy Link buttons.

Notes
------
- This only reaches devices on the SAME Wi-Fi/network as this computer.
  Crew off-site or on mobile data need the regular internet link instead.
- The app rechecks its address every few seconds, so if this computer
  changes networks mid-show its window will update — re-share the QR if
  that happens.
- Make sure this computer's firewall allows incoming connections on the
  port it's using (8765 by default) — most home/venue Wi-Fi setups don't
  block this, but a strict venue network occasionally does.
- Crew Talk (voice) should still work fine between phones on the same
  Wi-Fi even with no internet, but hasn't been tested on every possible
  venue network configuration.
- To use a different port, run it from a terminal with the port as an
  argument, e.g. on Mac: ./"Stage Effects Local Broadcast.app/Contents/MacOS/Stage Effects Local Broadcast" 9000

For anyone technical who'd rather run it from source
------------------------------------------------------
local_broadcast_app.py in this folder is the app's actual source — run it
directly with `python3 local_broadcast_app.py` if you have Python 3
installed (needs the `qrcode` package: `pip install qrcode`). This is also
what the "Build Local Broadcast app" GitHub Action builds automatically
into the ready-to-run downloads above — see
.github/workflows/build-local-broadcast-app.yml.

local_broadcast_server.py is the older, terminal-only version (no window,
prints the address to a console) — kept here in case it's ever useful, but
the app above is the one to use day to day.
