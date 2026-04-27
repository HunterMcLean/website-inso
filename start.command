#!/usr/bin/env bash
# Double-click to launch a local server and open the library.
cd "$(dirname "$0")"
PORT=8765
( sleep 1; open "http://localhost:${PORT}/" ) &
python3 -m http.server "${PORT}"
