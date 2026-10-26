#!/usr/bin/env python3
"""Which way of fetching a resolved YouTube stream does the CDN accept? (standalone diagnostic)
Usage: python fetch_paths.py <youtube url> [wait_seconds=6]
It waits wait_seconds after resolving before fetching (yt-dlp itself sleeps ~5 s for some clients: "as required by the site").
Resolves once with yt-dlp, then fetches bytes 0-1023 of the stream by every route and prints the HTTP status only."""
import sys, time, subprocess, shutil, ssl
import requests, yt_dlp
from yt_dlp.networking import Request
url = sys.argv[1]
print("python:", sys.executable, "| yt-dlp", yt_dlp.version.__version__, "|", ssl.OPENSSL_VERSION, "| requests", requests.__version__)
try:
    import curl_cffi; print("curl_cffi:", curl_cffi.__version__)
except Exception as e:
    print("curl_cffi: not installed")
with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True, "format": "18/best"}) as y:
    print("yt-dlp request handlers:", [type(h).__name__ for h in y._request_director.handlers.values()])
    info = y.extract_info(url, download=False)
    u, h = info["url"], dict(info.get("http_headers") or {})
    print("client in URL:", u.split("c=")[1].split("&")[0] if "c=" in u else "?", "| headers sent:", sorted(h))
    h["Range"] = "bytes=0-1023"
    wait = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
    print("available_at/ready hints:", {f.get("format_id"): f.get("available_at") for f in (info.get("formats") or [])[:0]}, "| waiting", wait, "s")
    time.sleep(wait)
    def t(label, fn):
        try: print(f"  {label:34s} -> {fn()}")
        except Exception as e: print(f"  {label:34s} -> {type(e).__name__}: {str(e)[:80]}")
    t("requests + resolver headers", lambda: requests.get(u, headers=h, timeout=20).status_code)
    t("yt-dlp's own urlopen", lambda: y.urlopen(Request(u, headers=h)).status)
    c = shutil.which("curl.exe") or shutil.which("curl")
    if c:
        hh = [x for k, v in h.items() for x in ("-H", f"{k}: {v}")]
        t("curl (" + c.split("\\")[-1].split("/")[-1] + ")", lambda: subprocess.run([c, "-s", "-o", "NUL" if sys.platform == "win32" else "/dev/null", "-w", "%{http_code}", *hh, u], capture_output=True, text=True, timeout=30).stdout)
    ff = shutil.which("ffmpeg")
    if ff:
        hs = "".join(f"{k}: {v}\r\n" for k, v in h.items() if k != "Range")
        t("ffmpeg + resolver headers", lambda: "ok" if subprocess.run([ff, "-v", "error", "-headers", hs, "-i", u, "-t", "1", "-f", "null", "-"], capture_output=True, text=True, timeout=40).returncode == 0 else "FAILED")
