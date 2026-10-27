# Connecting TravelDiscovery to Muse, ChatGPT, and Gemini

Two integration surfaces, not one — Muse and Gemini speak MCP directly;
ChatGPT wants an OpenAPI Action instead (no MCP support as of this
writing). Both surfaces share the same credential: a TravelDiscovery
personal access token (PAT).

## 1. Get a personal access token

Sign in to the app once (already-approved account required — this is
still a closed pilot, see CLAUDE.md), then:

```
POST https://travel-api-911993008582.us-central1.run.app/api/tokens
Authorization: Bearer <your Firebase ID token>
```

Returns `{"token": "td_..."}` — shown once, never retrievable again (only
its hash is stored). This token works as a normal bearer token on both
the MCP server and every REST endpoint listed in `chatgpt-action.yaml`.

## 2. MCP: Muse and Gemini

Deploy the MCP server (if not already live):

```bash
grep DEPLOY_MCP deploy-env.sh   # should be "export DEPLOY_MCP=true"
source deploy-env.sh && ./deploy.sh
```

Prints the live URL as `MCP server live at: https://travel-mcp-<hash>-uc.a.run.app/mcp`.

**Muse**: add it as a custom MCP connector (Muse's own settings — reported
to support arbitrary MCP servers as of its Sept 2026 launch, though
whether there's a self-serve developer portal for this vs. a curated
list was unconfirmed as of Oct 2026; check Muse's own docs if the option
isn't visible). Server URL + the PAT as its bearer token.

**Gemini**: point Gemini's CLI or Vertex AI Agent Builder at the same MCP
URL — same PAT, same server, no separate setup needed.

Both get the same 6 tools: `list_cities`, `find_venues`, `get_saved_picks`,
`surprise_me`, `list_trips`, `get_trip_booking_targets`. The last two are
built for exactly the hand-off flow above — `list_trips` resolves which
trip the user means by name (e.g. "my Lisbon trip") to an id, since
there's no other way to look that up; `get_trip_booking_targets` then
bundles that trip's details for a booking agent to act on (see both
docstrings in `api/mcp_server.py`).

## 3. ChatGPT: OpenAPI Action

ChatGPT can't consume MCP, so it gets a hand-authored subset spec instead
— `docs/chatgpt-action.yaml`, covering the same 5 read operations as REST
endpoints on the main `travel-api` service (no separate deploy needed,
these ship with every normal `travel-api` deploy).

1. ChatGPT → **Create a GPT** → **Configure** → **Actions** → **Create new action**.
2. Paste the contents of `docs/chatgpt-action.yaml` into the schema box
   (or **Import from URL** if you host the file somewhere reachable).
3. Authentication → **API Key** → Auth Type **Bearer** → paste the PAT
   from step 1.
4. Give the GPT instructions matching the app's own framing: taste-matched
   discovery and trip planning, not booking — if asked to actually book
   something, it should call `getTripBookingTargets` and hand the result
   to whatever booking-capable tool/assistant is available, not try to
   book directly itself.

## Keeping these in sync

`get_trip_booking_targets` (MCP) and `GET /api/trips/{trip_id}/booking-targets`
(REST, used by the ChatGPT Action) share one implementation —
`main.py`'s `_trip_booking_targets()` — so the two surfaces can't drift
apart on what a trip handoff actually contains. Any other endpoint added
to `chatgpt-action.yaml` should have a corresponding MCP tool (and vice
versa) for the same reason, unless there's a specific reason one surface
needs something the other doesn't.
