#!/bin/bash
cd "$(dirname "$0")"
echo "Starting Looney Tunes Catalog & Editor..."
python3 -c "import webbrowser, time; time.sleep(1); webbrowser.open('http://127.0.0.1:8000')" &
python3 server.py 8000
