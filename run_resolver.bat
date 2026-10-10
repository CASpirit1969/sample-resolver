@echo off
rem Sample Jukoke resolver -- as is, no support. First run installs what it needs.
rem Also needs Deno (https://deno.com) on PATH; install it once, then open a NEW terminal.
py -3 -m pip install -U -r requirements.txt
py -3 reference_resolver.py %*
pause
