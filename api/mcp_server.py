"""MCP server exposing TravelDiscovery's taste-matched picks to any MCP
client (Claude, and increasingly Gemini's CLI/Vertex AI Agent Builder —
see the conversation this was scoped in for why "works everywhere" isn't
a safe claim yet for ChatGPT, which wants an OpenAPI Action instead of
MCP).

Runs as its own Cloud Run service (see deploy.sh's travel-mcp deploy),
sharing this same source directory and Firestore project with the main
API — set ASGI_APP=mcp_server:app to select this entrypoint instead of
main:app (see Dockerfile).

Auth: personal access tokens minted via POST /api/tokens on the main API
(requires being an already-approved Firebase user — see auth.py), passed
as a normal bearer token. This is deliberately the simpler of the two
options considered (vs. a full OAuth 2.1 authorization server) — it costs
a copy-paste step for the user instead of a click-to-connect flow, in
exchange for not having to build /authorize, /token, PKCE, and client
registration from scratch. See auth.py's mint_token/verify_pat.

Verified against the installed SDK directly (pip show mcp: 2.2.0) rather
than assumed from training data, since the SDK's public API had already
changed once (FastMCP -> MCPServer, mcp.server.fastmcp ->
mcp.server.mcpserver) between when that training data was likely current
and now. If deploying this hits an import error, check `pip show mcp` in
the deployed container against what's pinned in requirements.txt — the
SDK may have moved again.
"""

import os
import random

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

import auth
import main as api  # reuses _grounded_items, CITIES, etc. directly — same process, no HTTP hop


class FirestoreTokenVerifier(TokenVerifier):
    async def verify_token(self, token: str) -> AccessToken | None:
        uid = auth.verify_pat(token)
        if not uid:
            return None
        return AccessToken(token=token, client_id="traveldiscovery-mcp", scopes=["read"], subject=uid)


# Both required by AuthSettings even for this simpler token_verifier path
# (no full OAuth authorization server here) — issuer_url just needs to be
# somewhere a client/human can find out how to get a token (the web app's
# own settings screen, once that's added), resource_server_url is this
# service's own URL. Set by deploy.sh once both services' URLs are known,
# same two-pass pattern as WEB_URL/SPOTIFY_REDIRECT_URI elsewhere.
_issuer = os.environ.get("MCP_ISSUER_URL", "http://localhost:8000")
_resource = os.environ.get("MCP_RESOURCE_URL", "http://localhost:8001")

mcp = MCPServer(
    name="traveldiscovery",
    instructions=(
        "Taste-matched food, bar, and live-music picks for a city, sourced from insider-curated "
        "venue data grounded against Google Places (hallucinated/defunct venues are dropped, "
        "not shown). Use find_venues to browse a city, surprise_me for one paired pick, or "
        "get_saved_picks for the venues this account has already explicitly starred — the right "
        "one when asked to act on (e.g. book) specific picks rather than browse generally."
    ),
    token_verifier=FirestoreTokenVerifier(),
    # validate_token_resource=False: our AccessToken never sets `.resource`
    # (there's only one resource server, this one — no multi-audience
    # tokens to distinguish), so the SDK's default resource-matching check
    # would reject every token. FirestoreTokenVerifier.verify_token already
    # does the only validation that applies (hash lookup + still-approved).
    auth=AuthSettings(issuer_url=_issuer, resource_server_url=_resource, validate_token_resource=False),
)


@mcp.tool()
async def list_cities() -> list:
    """Cities with curated or ingested venue data available."""
    return [{"id": c["id"], "name": c["name"], "country": c["country"]} for c in api.CITIES]


@mcp.tool()
async def find_venues(city: str, filter: str = "all") -> list:
    """Taste-matched food, bar, and/or live-music venues for a city.

    Args:
        city: city id from list_cities (e.g. "lisbon", "tokyo").
        filter: "all", "food", "bar", or "music".
    """
    items = await api._grounded_items(city)
    if filter in ("food", "bar", "music"):
        items = [i for i in items if i["type"] == filter]
    return items


@mcp.tool()
async def get_saved_picks() -> list:
    """This account's saved picks — the ones explicitly starred in the app
    (the heart icon on a venue card), not the full taste-matched list for a
    city. Use this, not find_venues, when asked to act on "the ones I
    picked," "my saved spots," or similar — e.g. to go make reservations
    for them — rather than to browse a city generally. Same saved_picks/
    {uid} Firestore data as api/main.py's GET /api/saved.
    """
    token = get_access_token()
    if not token:
        return []
    doc = auth.firestore_client().collection("saved_picks").document(token.subject).get()
    items = doc.to_dict().get("items", {}) if doc.exists else {}
    return list(items.values())


@mcp.tool()
async def surprise_me(city: str, seed: int = 0) -> dict:
    """One paired food + music pick for a city — a single suggestion for
    tonight, not a list to browse.
    """
    items = await api._grounded_items(city)
    food = [i for i in items if i["type"] == "food"]
    music = [i for i in items if i["type"] == "music"]
    if not food or not music:
        return {"city": city, "items": []}
    rnd = random.Random(seed)
    pick_food = food[seed % len(food)] if seed else rnd.choice(food)
    pick_music = music[(seed * 2 + 1) % len(music)] if seed else rnd.choice(music)
    return {"city": city, "items": [pick_food, pick_music]}


# Cloud Run/uvicorn's entrypoint (see Dockerfile: uvicorn ${ASGI_APP:-main:app}).
app = mcp.streamable_http_app()
