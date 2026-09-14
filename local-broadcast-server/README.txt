STAGE EFFECTS — LOCAL BROADCAST SERVER
=======================================

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

Requires Python 3, which is already installed on most Macs and many
Windows machines. If it's missing, both launchers will tell you and link
to where to get it (a one-time install, a couple of minutes).

Setup (one time per venue/network)
-----------------------------------
1. Copy this whole "local-broadcast-server" folder onto the computer running
   Stage Manager.
2. Double-click:
     - Mac:      "Start Local Broadcast (Mac).command"
     - Windows:  "Start Local Broadcast (Windows).bat"
   (On a Mac, the first time you may need to right-click it and choose
   "Open" to get past the unidentified-developer warning.)
3. A window opens and prints one or more addresses, like:
     http://192.168.1.50:8765
   That's this computer's address on the current Wi-Fi — it can change if
   you switch networks or venues, so check it again each time.
4. In Stage Manager, open Setup, scroll to "Broadcast to a Public Link",
   and open "Local Network Broadcast". Paste that address into
   "Local server address" and tick "Also broadcast to the local network".
5. Click "Start Broadcasting" as usual (or turn it on if it's already on)
   — it now sends to both the internet and this local server at once.
6. Use "Copy Local Crew Link" / its QR button to hand out the local link
   to crew on the venue Wi-Fi.

Every show
-----------
Just double-click the launcher again before the show and leave the window
open — closing it stops the local broadcast for anyone using it. Nothing
is saved between runs, same as a fresh broadcast room.

Notes
------
- This only reaches devices on the SAME Wi-Fi/network as this computer.
  Crew off-site or on mobile data need the regular internet link instead.
- Make sure this computer's firewall allows incoming connections on the
  port it's using (8765 by default) — most home/venue Wi-Fi setups don't
  block this, but a strict venue network occasionally does.
- Crew Talk (voice) should still work fine between phones on the same
  Wi-Fi even with no internet, but hasn't been tested on every possible
  venue network configuration.
- To use a different port, run it from a terminal with the port as an
  argument, e.g.: python3 local_broadcast_server.py 9000
