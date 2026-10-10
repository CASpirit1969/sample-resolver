"""
reference_resolver.py -- sample external resolver for Jukoke (NICE Resolver Contract v1.0)

PROVIDED AS IS, WITHOUT WARRANTY OR SUPPORT OF ANY KIND. See LICENSE and README.md.
This is example code for people who want to see what an external resolver can do or
write their own. It is not part of Jukoke, is not supported by the Jukoke authors, and
may stop working at any time (the sites it talks to change often).

What it does: a tiny local web server that answers three requests from Jukoke --
search, resolve (turn an id or pasted link into playable stream URLs) and playlist
expand -- using the open-source yt-dlp library. Field names on the wire match the
contract's defaults, so Jukoke needs no field-mapping configuration to use it.

You are responsible for what you use it for. Make sure your use complies with the
terms of the sites you access and with copyright law where you live.

Usage:
    python reference_resolver.py                    # 127.0.0.1:8787
    python reference_resolver.py 9000               # another port
    python reference_resolver.py --host 0.0.0.0     # reachable from other devices on your
                                                    # network (only do this on a network you trust)

Then in Jukoke: Setup > Song Source > Resolver, tick "Use an external resolver for Net
Search", enter http://127.0.0.1:8787 (or this machine's address) and use Test Connection.

    python reference_resolver.py --selftest         # check this machine can really play a YouTube
                                                    # stream, print the result and exit (0 = ok)
    python reference_resolver.py --no-selftest      # skip the automatic check at startup

Dependencies: yt-dlp[default] (includes the YouTube challenge solver), flask, waitress -- see
requirements.txt -- PLUS a JavaScript runtime on PATH, Deno by default (https://deno.com).
Current yt-dlp needs one to get playable YouTube streams; without it you get only the weaker
fallback clients, and songs fail with 403 or "Requested format is not available" while Search
still looks fine. Keep yt-dlp current too (py -m pip install -U "yt-dlp[default]"): it is
usually fixed within days of YouTube changing something, and a build older than ~90 days is
likely to be broken. At startup this program checks both, says so in the log, and plays a
real test video. GET /status shows the same information.
"""

import sys
import argparse
import datetime
import importlib.util
import logging
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, request, jsonify
from waitress import serve
import yt_dlp

logger = logging.getLogger("reference_resolver")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)

HOST = "127.0.0.1"
DEFAULT_PORT = 8787

# ---------------------------------------------------------------------------
# yt-dlp options, one set per endpoint. Standalone on purpose: nothing here imports
# Jukoke code, so this file runs against a bare yt-dlp install.
#
# extract_info() is called on a fresh YoutubeDL(opts) per request rather than one shared
# instance. yt-dlp does not document YoutubeDL as safe for concurrent extract_info() calls
# from several threads, and waitress is multi-threaded by default. A shared instance behind
# a lock would also make /search and /playlist queue up behind a slow /resolve. Per-request
# instances avoid both problems: genuinely concurrent, no shared state to corrupt.
# ---------------------------------------------------------------------------

SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "extract_flat": "in_playlist",
    "default_search": "ytsearch",
}

RESOLVE_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "noplaylist": True,
    # Prefer a muxed (progressive) H.264/AAC format, which is the simplest thing for a
    # player to fetch. Fall back to a split video+audio pair only when no muxed option
    # exists (an increasingly common YouTube case).
    "format": ("best[ext=mp4][vcodec^=avc1][acodec^=mp4a]/"
               "best[vcodec^=avc1][acodec^=mp4a]/"
               "bestvideo[ext=mp4][vcodec^=avc1][height<=1080]+bestaudio[ext=m4a]/"
               "bestvideo[vcodec^=avc1][height<=1080]+bestaudio[acodec^=mp4a]"),
}

PLAYLIST_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "extract_flat": "in_playlist",
}


# ---------------------------------------------------------------------------
# Environment check and self-test. Most "it worked last month" failures are one of two
# things: yt-dlp is out of date, or there is no JavaScript runtime for it to use. Both
# are cheap to detect, so say so at startup and on request (GET /status) instead of
# leaving the first sign of trouble to be a song that will not play.
# ---------------------------------------------------------------------------

STALE_DAYS = 60                       # warn when yt-dlp is older than this
JS_RUNTIMES = ("deno", "node", "bun", "qjs")   # the runtimes yt-dlp can use; Deno is the default
SELFTEST_VIDEO = "jNQXAC9IVRw"        # "Me at the zoo": the first YouTube upload, stable for years
FIX_HINT = ('py -m pip install -U "yt-dlp[default]"  and install Deno (https://deno.com), '
            'then restart this resolver from a NEW terminal so the new PATH is seen')

_selftest = {"ran": False, "ok": None, "when": None, "detail": "not run yet", "client": None}
_selftest_lock = threading.Lock()


def _ytdlp_version() -> str:
    try:
        return yt_dlp.version.__version__
    except Exception:
        return "unknown"


def env_check() -> dict:
    """What this machine has, and what is missing. Never raises."""
    ver = _ytdlp_version()
    age = None
    m = re.match(r"(\d{4})\.(\d{2})\.(\d{2})", ver)
    if m:
        try:
            age = (datetime.date.today() - datetime.date(int(m[1]), int(m[2]), int(m[3]))).days
        except ValueError:
            age = None
    runtime = next((r for r in JS_RUNTIMES if shutil.which(r)), None)
    ejs = importlib.util.find_spec("yt_dlp_ejs") is not None
    warnings = []
    if age is not None and age > STALE_DAYS:
        warnings.append(f"yt-dlp {ver} is {age} days old. YouTube changes often; old builds stop "
                        f"returning playable streams.")
    if not runtime:
        warnings.append("No JavaScript runtime (deno / node / bun / qjs) found on PATH. Without one "
                        "yt-dlp falls back to weaker YouTube clients and songs fail to play.")
    if not ejs:
        warnings.append('The yt-dlp challenge solver package (yt-dlp-ejs) is not installed; '
                        'install yt-dlp with its default extras: pip install -U "yt-dlp[default]"')
    return {"yt_dlp": ver, "yt_dlp_age_days": age, "js_runtime": runtime, "ejs_installed": ejs,
            "warnings": warnings, "fix": FIX_HINT if warnings else None}


def _hint(exc: Exception) -> str:
    """One plain sentence for a failed lookup: the likely cause on THIS machine."""
    warnings = env_check()["warnings"]
    if warnings:
        return warnings[0] + " Fix: " + FIX_HINT
    msg = str(exc)
    if "not available" in msg or "403" in msg or "Sign in" in msg or "bot" in msg:
        return "YouTube refused this request. Update yt-dlp first (py -m pip install -U \"yt-dlp[default]\"); if only this video fails it may be restricted."
    return "Update yt-dlp first (py -m pip install -U \"yt-dlp[default]\"); if only this video fails it may be restricted."


def _build_result(info: dict, ident: str) -> dict:
    """Turn yt-dlp's info dict into the contract's resolve answer (muxed or split)."""
    result = {
        "title": info.get("title"),
        "duration": info.get("duration"),
        "id": info.get("id", ident),
    }
    requested = info.get("requested_formats")
    if requested and len(requested) >= 2:
        # Split case -- yt-dlp already picked a video-only + audio-only pair to satisfy
        # RESOLVE_OPTS['format']'s bestvideo+bestaudio fallback tier. Identify each half by
        # presence of a real vcodec/acodec rather than assuming list order/count.
        video_fmt = next((f for f in requested if f.get("vcodec") not in (None, "none")), requested[0])
        audio_fmt = next((f for f in requested if f.get("acodec") not in (None, "none") and f is not video_fmt), requested[-1])
        result["video_url"] = video_fmt.get("url")
        result["audio_url"] = audio_fmt.get("url")
        if video_fmt.get("http_headers"):
            result["video_headers"] = video_fmt["http_headers"]
        if audio_fmt.get("http_headers"):
            result["audio_headers"] = audio_fmt["http_headers"]
    else:
        result["stream_url"] = info.get("url")
    return result


def _probe(url: str, headers: dict) -> str:
    """Fetch the first KB of a stream the way a player would. '' = fine, else why not."""
    if not url:
        return "no stream URL returned"
    req = urllib.request.Request(url, headers={**(headers or {}), "Range": "bytes=0-1023"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read(1024)
        return ""
    except urllib.error.HTTPError as e:
        return f"stream returned HTTP {e.code}"
    except Exception as e:
        return f"stream not reachable: {e}"


def run_selftest() -> dict:
    """Resolve one stable video and really fetch its stream. Records and returns the outcome."""
    with _selftest_lock:
        try:
            info = _extract(RESOLVE_OPTS, f"https://www.youtube.com/watch?v={SELFTEST_VIDEO}")
            res = _build_result(info, SELFTEST_VIDEO)
            urls = [(res.get("stream_url"), info.get("http_headers"))] if res.get("stream_url") else \
                   [(res.get("video_url"), res.get("video_headers")), (res.get("audio_url"), res.get("audio_headers"))]
            problem = next((p for p in (_probe(u, h) for u, h in urls) if p), "")
            first = urls[0][0] or ""
            q = urllib.parse.parse_qs(urllib.parse.urlparse(first).query)
            client = (q.get("c") or [None])[0]
            ok, detail = (not problem), (problem or "resolved and stream fetched")
        except Exception as e:
            ok, detail, client = False, f"{_hint(e)} ({str(e).splitlines()[0][:160] if str(e) else type(e).__name__})", None
        _selftest.update(ran=True, ok=ok, when=time.strftime("%Y-%m-%d %H:%M:%S"), detail=detail, client=client)
        return dict(_selftest)


def _log_environment():
    env = env_check()
    logger.info(f"[reference_resolver] yt-dlp {env['yt_dlp']}, JS runtime: {env['js_runtime'] or 'NONE'}, "
                f"challenge solver: {'yes' if env['ejs_installed'] else 'NO'}")
    for w in env["warnings"]:
        logger.warning(f"[reference_resolver] {w}")
    if env["warnings"]:
        logger.warning(f"[reference_resolver] Fix: {FIX_HINT}")


def _log_selftest(r: dict):
    if r["ok"]:
        logger.info(f"[reference_resolver] SELF-TEST OK -- played a real YouTube stream"
                    f"{' (client ' + r['client'] + ')' if r['client'] else ''}")
    else:
        logger.warning(f"[reference_resolver] SELF-TEST FAILED -- songs will probably not play: {r['detail']}")


def _extract(opts: dict, target: str):
    """Fresh YoutubeDL(opts) per call -- see the comment above SEARCH_OPTS for why."""
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(target, download=False)


@app.route("/search", methods=["GET"])
def search():
    query = (request.args.get("q") or "").strip()
    limit = request.args.get("limit", default=10, type=int) or 10
    if not query:
        return jsonify({"error": "missing q"}), 400

    try:
        info = _extract(SEARCH_OPTS, f"ytsearch{max(1, limit)}:{query}")
    except Exception as e:
        logger.warning(f"[search] failed for query={query!r}: {e}")
        return jsonify({"error": "search failed"}), 502

    entries = [e for e in (info or {}).get("entries") or [] if e]
    results = [
        {
            "id": e.get("id"),
            "title": e.get("title"),
            "channel": e.get("uploader") or e.get("channel"),
            "duration": e.get("duration"),
        }
        for e in entries[:limit]
    ]
    return jsonify({"results": results})


@app.route("/resolve", methods=["POST"])
def resolve():
    body = request.get_json(silent=True) or {}
    ident = (body.get("id") or "").strip()
    if not ident:
        return jsonify({"error": "missing id"}), 400

    # Accept either the opaque id /search returned or a raw pasted URL (see CONTRACT.md).
    # A bare id is turned into an explicit watch URL: passing a bare 11-character id
    # straight to yt-dlp is ambiguous and can be misread as a search term.
    target = ident if "://" in ident else f"https://www.youtube.com/watch?v={ident}"

    try:
        info = _extract(RESOLVE_OPTS, target)
    except Exception as e:
        hint = _hint(e)
        logger.warning(f"[resolve] failed for id={ident!r}: {e}\n    -> {hint}")
        # "detail" is extra to the contract's {"error": ...}; a client that ignores it is unaffected.
        return jsonify({"error": "resolve failed", "detail": hint}), 502

    if not info:
        return jsonify({"error": "resolve failed"}), 502

    return jsonify(_build_result(info, ident))


@app.route("/status", methods=["GET"])
def status():
    """Not part of the contract: what this resolver has and whether it can really play a stream.
    ?selftest=1 runs the real check now (a few seconds); otherwise the last result is returned."""
    if request.args.get("selftest"):
        run_selftest()
    env = env_check()
    return jsonify({**env, "selftest": dict(_selftest),
                    "ok": not env["warnings"] and _selftest["ok"] is not False})


@app.route("/playlist", methods=["POST"])
def playlist():
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    max_songs = body.get("max_songs") or 100
    if not url:
        return jsonify({"error": "missing url"}), 400

    try:
        info = _extract(PLAYLIST_OPTS, url)
    except Exception as e:
        logger.warning(f"[playlist] failed for url={url!r}: {e}")
        return jsonify({"error": "playlist expand failed"}), 502

    if not info:
        return jsonify({"error": "playlist expand failed"}), 502

    # Skip unavailable/deleted entries here rather than returning null-titled placeholders:
    # the client treats the returned list as final and does not re-validate titles.
    entries = [e for e in (info.get("entries") or []) if e]
    playlist_total = info.get("playlist_count") or len(entries)

    songs = []
    for e in entries[:max_songs]:
        vid = e.get("id")
        songs.append({
            "id": vid,
            "url": e.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else None),
            "title": e.get("title"),
            "channel": e.get("uploader") or e.get("channel"),
        })

    return jsonify({
        "playlist_title": info.get("title") or "",
        "playlist_total": playlist_total,
        "songs": songs,
    })


def main():
    ap = argparse.ArgumentParser(description="Sample Jukoke external resolver (as is, no support)")
    ap.add_argument("port", nargs="?", type=int, default=DEFAULT_PORT)
    ap.add_argument("--host", default=HOST,
                    help="address to bind (default 127.0.0.1 = this computer only)")
    ap.add_argument("--selftest", action="store_true",
                    help="check that this machine can play a real YouTube stream, print the result, exit")
    ap.add_argument("--no-selftest", action="store_true", help="do not run the check at startup")
    args = ap.parse_args()
    _log_environment()
    if args.selftest:
        r = run_selftest()
        _log_selftest(r)
        sys.exit(0 if r["ok"] else 1)
    if args.host not in ("127.0.0.1", "localhost"):
        logger.warning("[reference_resolver] bound beyond this computer: anyone who can reach this "
                       "address can use it. Only do this on a network you trust.")
    logger.info(f"[reference_resolver] Serving NICE resolver contract on http://{args.host}:{args.port}")
    if not args.no_selftest:
        threading.Thread(target=lambda: _log_selftest(run_selftest()), daemon=True, name="selftest").start()
    serve(app, host=args.host, port=args.port, threads=8)


if __name__ == "__main__":
    main()
