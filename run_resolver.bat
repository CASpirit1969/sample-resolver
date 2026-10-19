@echo off
rem Sample Jukoke resolver -- as is, no support. First run installs what it needs.
rem Also needs Deno (https://deno.com) on PATH; install it once, then open a NEW terminal.
rem
rem OPTIONS: to turn something on for every start, put it on the "set OPTIONS=" line below, for example
rem     set OPTIONS=--auto-update
rem     set OPTIONS=--auto-update --update-hours 12
rem Anything typed after the file name is added too:  run_resolver.bat 9000
rem List every option:  run_resolver.bat --help
rem   --auto-update   keep yt-dlp current while this runs (this file already upgrades it at each start)
set OPTIONS=
py -3 -m pip install -U -r requirements.txt
py -3 reference_resolver.py %OPTIONS% %*
pause
