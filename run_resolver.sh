#!/bin/sh
# Sample Jukoke resolver -- as is, no support. First run installs what it needs.
# Also needs Deno (https://deno.com) on PATH; install it once, then open a NEW terminal.
python3 -m pip install -U -r requirements.txt && python3 reference_resolver.py "$@"
