#!/bin/bash

# Start virtual display
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

# Small wait to ensure Xvfb starts
sleep 2

# Run your app
exec python -u -m src.main "$@"
