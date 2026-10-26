#!/usr/bin/env python3
"""Which yt-dlp YouTube client gives URLs the CDN will actually serve? (standalone diagnostic)
Usage: python client_sweep.py <youtube url>      (run with the resolver's Python, where yt_dlp is installed)"""
import sys, requests, yt_dlp
url = sys.argv[1]
FMT = ("best[ext=mp4][vcodec^=avc1][acodec^=mp4a]/best[vcodec^=avc1][acodec^=mp4a]/"
       "bestvideo[ext=mp4][vcodec^=avc1][height<=1080]+bestaudio[ext=m4a]")
def probe(u, h):
    h = dict(h or {}); h["Range"] = "bytes=0-1023"
    try:
        return requests.get(u, headers=h, timeout=20).status_code
    except Exception as e:
        return type(e).__name__
for clients in (None, "tv", "web_safari", "mweb", "ios", "android_vr", "web", "tv,web_safari", "default,mweb"):
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "noplaylist": True, "format": FMT}
    if clients:
        opts["extractor_args"] = {"youtube": {"player_client": clients.split(",")}}
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            info = y.extract_info(url, download=False)
    except Exception as e:
        print(f"{str(clients):<16} resolve failed: {str(e)[:90]}"); continue
    req = info.get("requested_formats") or [info]
    res = [(f.get("format_id"), f.get("height"), probe(f.get("url"), f.get("http_headers"))) for f in req]
    print(f"{str(clients):<16} " + "  ".join(f"itag {i} {h}p -> HTTP {s}" for i, h, s in res))
