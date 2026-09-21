LOCAL BROADCAST — Stage Effects & Spaan
=========================================

What this is
-------------
A small, offline stand-in for the internet broadcast Stage Manager normally
uses. Run it on the same computer as Stage Manager and crew phones on the
SAME WI-FI can see the live countdown, Crew Chat, and use Crew Talk voice —
even with no internet connection at all. It runs ALONGSIDE your normal
internet broadcast, not instead of it, so you can keep both going: the
internet link still reaches anyone anywhere, while this local link keeps
working for everyone in the building even if the venue's internet drops or
is struggling under a crowd.

Since a recent update, the Crew and Viewer links you hand out only need to
be ONE link each (not a separate "internet" and "local" link) — when Local
Network Broadcast is turned on in Stage Manager, that one link automatically
uses the local network while you're on the venue Wi-Fi, and quietly falls
back to the internet the moment a phone leaves range (or switches back the
moment it returns) — no manual switching, nothing to re-send.

Stage Effects and Spaan are two separate apps
------------------------------------------------
Stage Effects and Spaan always run as two separate downloads. Each one only
ever shows its own brand — its own window title, its own QR codes, its own
"Open Stage Manager" button. There's no shared screen showing both. If
you run shows for both, download and run both apps; they use different
ports by default (Stage Effects 8765, Spaan 8766) so they can run side by
side on the same computer without clashing if you ever need to.

Getting the app (one time, or whenever you want the newest version)
----------------------------------------------------------------------
This is built automatically on GitHub, so there's nothing to install to get
it — just download the ready-to-run file:

  1. Open this repository on GitHub, in the "Releases" section (or go
     straight to the "Local Broadcast — latest build" release).
  2. Download the file(s) for your computer and brand:
       - Mac:      "Stage Effects Local Broadcast (Mac).zip" and/or
                    "Spaan Local Broadcast (Mac).zip" — unzip to get the
                    matching ".app".
       - Windows:  "Stage Effects Local Broadcast.exe" and/or
                    "Spaan Local Broadcast.exe"
  3. Put it somewhere handy (Desktop, or this folder) — that's it, no
     installer, no Python, nothing else to set up.

Every show
-----------
1. Double-click the app for the brand you're running.
     - Mac, first time only: it'll say Apple can't verify it and only
       offer "Move to Trash" / "Done" — click Done, then open System
       Settings -> Privacy & Security, scroll down to the Security
       section, and click "Open Anyway" next to the app's name (you'll
       need your password or Touch ID). Then double-click the app one
       more time and click "Open" on the dialog that appears. Only
       needed once — after that it opens normally.
     - Windows, first time only: it may show "Windows protected your PC" —
       click "More info", then "Run anyway". Only needed once.
2. A window opens showing this computer's address and two QR codes (Crew /
   Viewer). Leave it open for the duration of the show — closing it stops
   the local broadcast for anyone using it.
3. The FIRST time you open Stage Manager, Crew, or Viewer from this app on
   any given device, that browser will warn the connection "isn't private".
   This is expected — the app makes its own certificate for this computer
   (it isn't a real security problem, just not one a browser recognizes by
   default) — click through it (e.g. "Advanced" → "Proceed"/"visit this
   website") once. It won't ask again on that device for this computer,
   even across different shows/networks.
4. In Stage Manager's Setup page, open "Local Network Broadcast". If Stage
   Manager is running on this same computer, it should find the app on its
   own and offer to turn it on with one click. Otherwise, type in the
   address shown in the app's window (now starting with https://) and tick
   "Also broadcast to the local network".
5. Click "Start Broadcasting" as usual (or turn it on if it's already on)
   — it now sends to both the internet and this local broadcast at once.
   The "Copy Viewer Link"/"Copy Crew Link" buttons up top now hand out the
   one combined link described above.
6. Hand crew the QR code from the app's window for the page they need
   (Crew or Viewer), or use its Copy Link buttons.

Notes
------
- This only reaches devices on the SAME Wi-Fi/network as this computer.
  Crew off-site or on mobile data automatically fall back to the internet
  link instead, as long as an internet broadcast is also running (see
  above) — with no internet broadcast configured, local-only is all there
  is, same as before.
- The app rechecks its address every few seconds, so if this computer
  changes networks mid-show its window will update — re-share the QR if
  that happens. A brand new network (venue this computer has never
  broadcast from before) means one more one-time certificate warning per
  device, same as the very first time.
- Make sure this computer's firewall allows incoming connections on the
  port it's using (8765 for Stage Effects, 8766 for Spaan, by default) —
  most home/venue Wi-Fi setups don't block this, but a strict venue network
  occasionally does.
- Crew Talk (voice) now works over a Local Broadcast link in every browser,
  including Safari and on phones, since the app serves itself over https
  (browsers only allow microphone access on a secure connection) — make
  sure you're on the latest version of the app if voice still doesn't work.
- To use a different port, run it from a terminal with the port as an
  argument, e.g. on Mac:
    ./"Stage Effects Local Broadcast.app/Contents/MacOS/Stage Effects Local Broadcast" 9000

For anyone technical who'd rather run it from source
------------------------------------------------------
local_broadcast_app.py in this folder is the shared implementation (both
brands); local_broadcast_app_spaan.py is the tiny entry point that runs it
as Spaan (local_broadcast_app.py itself runs as Stage Effects when run
directly). Run either with `python3 local_broadcast_app.py` /
`python3 local_broadcast_app_spaan.py` if you have Python 3 installed
(needs the `qrcode` and `cryptography` packages:
`pip install qrcode cryptography`). This is also what the "Build Local
Broadcast app" GitHub Action builds automatically into the ready-to-run
downloads above — see .github/workflows/build-local-broadcast-app.yml.

The self-signed certificate both brands share is kept in
~/.stage_effects_local_broadcast/ on whichever computer runs the app —
delete that folder to force a fresh certificate (e.g. if you ever suspect
it's been copied elsewhere) at the cost of one more warning per device.

local_broadcast_server.py is the older, terminal-only, plain-http version
(no window, prints the address to a console, pre-dates the brand split and
HTTPS) — kept here in case it's ever useful, but the app above is the one
to use day to day.
