#!/bin/bash

# Install dependencies
# pip install -r requirements.txt

# Set display for X11
export DISPLAY=:1
export HEIGHT=768
export WIDTH=1024

# Start the server
python3 server.py
