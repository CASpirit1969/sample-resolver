#!/bin/sh
# Sample Jukoke resolver -- as is, no support. First run installs what it needs.
# Also needs Deno (https://deno.com) on PATH; install it once, then open a NEW terminal.
#
# OPTIONS: to turn something on for every start, set it on the OPTIONS line below, for example
#     OPTIONS="--auto-update"
#     OPTIONS="--auto-update --update-hours 12"
# Anything typed after the file name is added too:  ./run_resolver.sh 9000
# List every option:  ./run_resolver.sh --help
#   --auto-update   keep yt-dlp current while this runs (this file already upgrades it at each start)
OPTIONS=""
#
# Uses its own virtual environment (.venv, next to this script) because Ubuntu 24.04,
# Debian 12 and recent macOS Homebrew Pythons refuse system-wide "pip install"
# (error: externally-managed-environment). If the venv cannot be created on
# Ubuntu/Debian:  sudo apt install python3-venv
# Every run also upgrades yt-dlp, which YouTube changes break within weeks.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python3 ]; then
  python3 -m venv .venv || {
    echo "Could not create a virtual environment. On Ubuntu/Debian: sudo apt install python3-venv" >&2
    exit 1
  }
fi
# $OPTIONS is deliberately not quoted: it holds several words.
.venv/bin/python3 -m pip install -q -U -r requirements.txt && exec .venv/bin/python3 reference_resolver.py $OPTIONS "$@"
