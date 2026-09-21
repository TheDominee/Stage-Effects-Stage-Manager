#!/usr/bin/env python3
"""
Entry point for the Spaan-branded Local Broadcast app.

Stage Effects and Spaan always run as two completely separate apps (see the
BRANDS dict and module docstring in local_broadcast_app.py, which holds the
actual shared implementation) — this file just tells it to run as Spaan
instead of the default (Stage Effects). It's what the "Spaan Local
Broadcast" build in .github/workflows/build-local-broadcast-app.yml is
built from.
"""

from local_broadcast_app import main

if __name__ == '__main__':
    main('spaan')
