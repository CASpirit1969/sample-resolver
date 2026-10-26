#!/usr/bin/env python3
"""Direct resolver check (standalone, not part of the release tree).
Usage:  python resolver_direct.py <youtube url or id> [--base http://127.0.0.1:8787] [--height 360]
Asks the resolver for a stream, then fetches the first bytes of each returned URL the way
Jukoke's preview does, and prints what the CDN says."""
import argparse, json, sys, urllib.parse as up
import requests

ap = argparse.ArgumentParser()
ap.add_argument("video")
ap.add_argument("--base", default="http://127.0.0.1:8787")
ap.add_argument("--height", type=int, default=360)
a = ap.parse_args()

def myip(host):
    try:
        return requests.get(f"https://{host}", timeout=5).text.strip()
    except Exception as e:
        return f"? ({type(e).__name__})"

print("This machine, outbound  IPv4:", myip("api.ipify.org"), "  IPv6:", myip("api6.ipify.org"))
r = requests.post(a.base.rstrip("/") + "/resolve", json={"id": a.video, "max_height": a.height}, timeout=60)
print("resolver HTTP", r.status_code)
if r.status_code != 200:
    sys.exit(r.text[:300])
info = r.json()
print("title:", info.get("title"), "| duration:", info.get("duration"))
parts = ([("video", info.get("video_url"), info.get("video_headers")), ("audio", info.get("audio_url"), info.get("audio_headers"))]
         if info.get("video_url") else [("muxed", info.get("stream_url"), info.get("headers"))])

def probe(label, url, headers, rng):
    h = dict(headers or {}); h["Range"] = rng
    try:
        with requests.get(url, headers=h, timeout=20, stream=True) as x:
            n = len(next(x.iter_content(1024), b"")) if x.status_code in (200, 206) else 0
            print(f"    {label:<28} HTTP {x.status_code}  Content-Range={x.headers.get('Content-Range','')!r}  got {n} bytes")
    except requests.RequestException as e:
        print(f"    {label:<28} {type(e).__name__}: {e}")

for kind, url, hdrs in parts:
    if not url:
        print(kind, "- no URL"); continue
    u = up.urlparse(url); q = dict(up.parse_qsl(u.query))
    print(f"\n[{kind}] host={u.netloc}")
    print("    itag=%s  client(c)=%s  mime=%s  ip=%s  expire=%s  pot=%s  sabr=%s" % (
        q.get("itag"), q.get("c"), q.get("mime"), q.get("ip"), q.get("expire"), "yes" if q.get("pot") else "NO", q.get("sabr")))
    print("    headers from resolver:", sorted((hdrs or {}).keys()) or "none")
    probe("with headers, bytes 0-1023", url, hdrs, "bytes=0-1023")
    probe("no headers,   bytes 0-1023", url, {}, "bytes=0-1023")
    probe("with headers, bytes 0-524287", url, hdrs, "bytes=0-524287")
