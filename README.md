# Sample resolver for Jukoke

**Provided as is, with no warranty and no support.** It is example code, not part of Jukoke.
It may break whenever the sites it talks to change.

Compatible with: NICE Resolver Contract v1.0.

Jukoke has no online song source of its own. If you want Net Search, Paste URL and playlist
import, you point Jukoke at a small program called a *resolver*. This is one working example,
built on the open-source [yt-dlp](https://github.com/yt-dlp/yt-dlp) library, so you can see what
a resolver does or use it as a starting point for your own. It speaks the NICE Resolver Contract
v1.0 (`/search`, `/resolve`, `/playlist`) using the contract's default field names, so Jukoke
needs no field-mapping setup.

## Run it

Needs Python 3.9 or newer, and **Deno** (https://deno.com) -- install it once, then open a *new* terminal so it is
on your PATH. Current yt-dlp uses a JavaScript runtime to get playable YouTube streams; without one, Search still
works but songs fail to play. (Node, Bun and QuickJS also work.)

- Windows: double-click `run_resolver.bat`
- macOS / Linux: `./run_resolver.sh`

Or by hand: `pip install -r requirements.txt` then `python reference_resolver.py`.
It listens on `http://127.0.0.1:8787` (this computer only). Another port: `python reference_resolver.py 9000`.
To reach it from another device on your network: `--host 0.0.0.0` (only on a network you trust --
anyone who can reach it can use it).

## Point Jukoke at it

1. In Jukoke open **Setup > Song Source > Resolver**.
2. Tick **Use an external resolver for Net Search**. Ticking it is your consent; read the info box first.
3. Enter the address, for example `http://127.0.0.1:8787`.
4. Press **Test Connection**. Search should report OK. Resolve is a real test: Jukoke asks for one well-known
   video and fetches the start of the stream from its own computer, so a green check means songs can really play.
   (Playlist can only use a made-up address, so it just reports "responded".) A "Stream refused" result means this
   resolver's yt-dlp or Deno is out of date -- see below.
5. To check for real, look at the resolver's window: at startup it plays a test video and logs
   `SELF-TEST OK` or `SELF-TEST FAILED` with the likely cause. The same information is at
   `http://127.0.0.1:8787/status` (add `?selftest=1` to run the check again now). From a terminal:
   `python reference_resolver.py --selftest` (exit code 0 = fine).

## When something doesn't play

- **Update yt-dlp first**: `python -m pip install -U "yt-dlp[default]"` (on Windows `py -m pip install -U "yt-dlp[default]"`;
  use the same Python that runs this resolver). YouTube changes every few weeks; a yt-dlp more than about 90 days old
  is likely broken. Most "403 Forbidden", "Requested format is not available", "no results" and "resolve failed"
  problems are fixed by a newer version. Then restart the resolver.
- **No JavaScript runtime**: if the log says `JS runtime: NONE`, install Deno and open a new terminal. A new
  yt-dlp without one still fails.
- Do this on every device that runs a resolver, and about once a month. Songs that play on one computer and not
  on another are almost always a difference here.
- Some videos cannot be fetched this way at all (restricted or age-gated uploads). Pick a different upload.
- This sample uses plain yt-dlp lookups, with no cookies and no workarounds.

## Your responsibility

You decide what to point this at and what to play. Make sure your use complies with the terms of the
sites you access and with the copyright laws where you live. The Jukoke authors don't vet, host or
endorse any content you reach through a resolver.

## Writing your own

Read `CONTRACT.md` for the three endpoints and their request and response shapes, then
`reference_resolver.py` for a working implementation. Both are short.

## License

MIT. See `LICENSE`.
