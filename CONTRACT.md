# NICE Resolver Contract v1.1

A *resolver* is a small web service that turns a search or a pasted link into playable stream URLs. A client such as Jukoke calls it over HTTP. This file describes what a resolver must answer. `reference_resolver.py` is a working implementation.

All requests and responses are JSON. Field names below are the contract's defaults; a client may allow remapping them, but a resolver that uses these names needs no mapping.

## Errors

Return a non-2xx status and a JSON body `{"error": "<short message>"}`.

| Status | Meaning |
|---|---|
| 400 | A required parameter is missing |
| 502 | The lookup failed (upstream error, nothing found, unavailable) |

A resolver may add extra fields to an error body (for example `"detail"`, a human-readable hint). Clients ignore fields they do not know.

## GET /search

Query parameters:

| Name | Required | Notes |
|---|---|---|
| `q` | yes | Search text |
| `limit` | no | Maximum results; default 10 |

Response:

```json
{
  "results": [
    { "id": "jNQXAC9IVRw", "title": "Me at the zoo", "channel": "jawed", "duration": 19 }
  ]
}
```

- `id` is opaque to the client. It is handed back unchanged to `/resolve`.
- `duration` is in seconds and may be null.

## POST /resolve

Request:

```json
{ "id": "jNQXAC9IVRw", "max_height": 360 }
```

`id` is either the opaque id from `/search` or a full pasted URL (anything containing `://`).

`max_height` is optional (added in v1.1). It means "a stream no taller than this many pixels is enough"; a client sends it when it only needs a small picture, such as a short preview. A resolver should prefer a stream at or below that height, and must still answer with its usual stream when nothing that small exists. A resolver that does not support the field ignores it, so a client must be prepared for any size.

Response, one of two shapes.

**Muxed** (one stream carrying video and audio):

```json
{ "id": "jNQXAC9IVRw", "title": "Me at the zoo", "duration": 19, "stream_url": "https://..." }
```

**Split** (separate video and audio streams):

```json
{
  "id": "jNQXAC9IVRw", "title": "Me at the zoo", "duration": 19,
  "video_url": "https://...", "audio_url": "https://...",
  "video_headers": { "User-Agent": "..." }, "audio_headers": { "User-Agent": "..." }
}
```

- The client looks at which fields are present to decide muxed or split. Return a muxed stream when one exists.
- `video_headers` and `audio_headers` are optional. If given, the client sends them when fetching that stream.
- The client fetches the stream URLs itself, from its own computer. The URLs must be reachable from there and must stay valid long enough to play the song.

## POST /playlist

Request:

```json
{ "url": "https://...", "max_songs": 100 }
```

Response:

```json
{
  "playlist_title": "My playlist",
  "playlist_total": 250,
  "songs": [
    { "id": "jNQXAC9IVRw", "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "title": "Me at the zoo", "channel": "jawed" }
  ]
}
```

- Return at most `max_songs` songs.
- `playlist_total` is the full size of the playlist. A client compares it with the number of songs returned to tell the user the list was truncated.
- Leave out unavailable or deleted entries instead of returning placeholders with null titles. The client treats the list as final and does not re-validate titles.

## Behavior

- **Concurrency.** Handle requests concurrently. A slow `/resolve` should not hold up `/search` or `/playlist`.
- **Timeouts.** Clients apply their own timeout to each call. Fail fast rather than hang.
- **Availability.** A resolver may implement only some endpoints. Clients check each one separately and turn off only the features that need a missing one.
- **Network.** Bind to `127.0.0.1` by default. Binding to other addresses lets anyone who can reach the port use the resolver, so do it only on a network you trust.
- **Optional status.** `GET /status` in the reference resolver is not part of the contract.

## Responsibility

A resolver decides what content it reaches. Its operator is responsible for complying with the terms of the sites it accesses and with applicable copyright law.
