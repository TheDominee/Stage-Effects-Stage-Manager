#!/bin/bash
# Double-click this file to start the Local Broadcast Server on a Mac.
# The first time, macOS may warn about an unidentified developer — right-click
# (or Control-click) this file and choose "Open" instead, then confirm.
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  python3 local_broadcast_server.py
elif command -v python >/dev/null 2>&1; then
  python local_broadcast_server.py
else
  echo "Python 3 isn't installed on this Mac."
  echo "Install it from https://www.python.org/downloads/ (or via 'brew install python3'), then run this again."
fi
echo
echo "Press Enter to close this window..."
read
