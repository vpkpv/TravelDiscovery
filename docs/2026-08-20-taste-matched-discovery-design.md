# Taste-Matched Discovery — MVP Design

Status: Approved, reconstructed from prior session handoff (original design work happened
in an earlier session; this doc recreates it in the new `TravelDiscovery` repo).

## What this is

A travel app that recommends food and music experiences in a city, matched to the user's
actual taste rather than generic "best of" lists. This is a separate project from
FfAdvisor (the fantasy football app) — new product, new codebase, new GCP project.

## Scope: three subsystems, one MVP

The long-term product has three subsystems:

1. **Discovery** — taste-matched food & music recommendations for a city
2. **Planning** — turning discovered picks into an itinerary
3. **Budgeting** — trip cost tracking

We are starting with **discovery only**. Planning and budgeting are explicitly out of
scope until discovery is validated with real users.

## Core differentiator

Two things distinguish this from a generic "ask an LLM for restaurant recommendations"
app:

- **Taste-matched, not popularity-matched.** Music taste comes from the user's Spotify
  listening history (via OAuth). Food taste comes from a cuisine quick-pick onboarding
  flow (lighter-weight than trying to infer food taste from an external API). Recommendations
  are filtered/ranked against this taste profile, not just "top rated near you."
- **Insider-curated venue data, not generic LLM knowledge.** Food picks are sourced from
  YouTube food-influencer videos for the target city, transcript-extracted the same way
  FfAdvisor extracts player sentiment from fantasy football YouTube channels (reusing that
  pipeline's transcript → Gemini extraction pattern). This avoids the generic, often stale
  or hallucinated venue lists an LLM produces from training data alone.

## Architecture

- **Client:** iOS app, SwiftUI
- **Backend:** FastAPI on Cloud Run — new GCP project, kept separate from FfAdvisor's
  GCP project (no shared infra, no shared billing)
- **Auth & access:** Firebase Auth + Firestore, closed pilot with a manual approval gate
  (same pattern as FfAdvisor's `approved_users/{uid}` — deliberate, not open signup)
- **Taste signal — music:** Spotify OAuth, run in Spotify's **Dev Mode**. This is a
  deliberate constraint, not an oversight: Dev Mode quota-caps the app for a small number
  of individually-allowlisted users, which happens to line up with the closed-pilot access
  model. See "Spotify quota constraint" below.
- **Taste signal — food:** cuisine quick-pick during onboarding (explicit multi-select,
  not inferred from an external API)
- **Venue data pipeline:** YouTube food-influencer channels → transcript extraction →
  Gemini structured extraction → venue candidates. Reuses FfAdvisor's ingestion pattern
  (`services/transcript.py`-style pipeline) against a different channel set and a
  different extraction schema (venues/dishes instead of players/sentiment).
- **Grounding:** Google Places API cross-references every venue candidate pulled from
  YouTube transcripts against a real place record (address, open/closed status, rating).
  Candidates that don't resolve to a real Places record are dropped. This is the mechanism
  that prevents hallucinated or defunct venues from reaching the user.

## MVP feature set

- Spotify OAuth login
- Cuisine quick-pick (onboarding, one-time, editable later)
- City search
- Combined results feed per city: food picks (YouTube-sourced, Places-verified) + music
  picks (Spotify-matched) in a single feed
- Each result includes a short "why this fits you" narrative connecting the pick back to
  the user's taste signal
- Closed pilot: new users require manual approval before they can use the app

## Spotify quota constraint (why Dev Mode, and why it's OK for MVP)

Spotify's standard API access for a personal/small project is capped at **Dev Mode**,
which limits the app to a small number of explicitly allowlisted Spotify accounts and
blocks moving to production-tier quota without Spotify's extension approval (which is slow
and not guaranteed for a hobby-scale app).

Rather than treating this as a blocker, the design leans into it: the closed-pilot access
model (manual Firestore approval) was already the plan for other reasons (curating an
early user set, controlling cost exposure on Gemini/Places calls), so capping active users
to what Dev Mode allows is not an additional constraint in practice.

To keep this from becoming a hard ceiling later, the taste-profile module is built generic:
the "music taste profile" interface doesn't assume Spotify specifically. If Dev Mode's cap
becomes binding, the fallback is a manual "tell us artists/genres you like" input that
produces the same shape of taste profile without needing Spotify OAuth at all. This swap
is a P2 item, not built for MVP, but the taste-profile interface is designed so it doesn't
require a rewrite later.

## Open design questions (P1/P2 — not blocking MVP build)

- Music insider signal: is there a YouTube-equivalent curated source for music
  recommendations (playlists, DJ sets, local scene coverage), or is Spotify-only taste
  matching sufficient for v1?
- Cache-key bucketing scheme for city + taste-profile combinations (avoid recomputing
  Gemini extraction / Places lookups per user when many users share a city)
- Google Places API cost model at scale — need a per-city, per-request cost estimate
  before this goes beyond a handful of pilot users
- City-name disambiguation (e.g. "Springfield", "Portland") in the city search flow
- Spotify-failure fallback behavior (API down, token refresh failure, user revokes access
  mid-session) — what does the music half of the feed show?
- Food/music spatial pairing — should picks in the combined feed be geographically
  clustered (e.g. dinner near the venue with live music after), or shown as two
  independent ranked lists?

## Explicitly out of scope for MVP

- Itinerary/planning subsystem
- Budget tracking subsystem
- Android client
- Production-tier Spotify quota / open signup
- Any inference of food taste from external data (kept to explicit quick-pick for MVP)

## Age-segmented profiles (exploratory, post-MVP)

Raised as a direction to explore: curating the app differently for a 50+ audience versus
a 20s/30s audience, rather than one undifferentiated experience. Starting point is 50+,
with a 20s/30s variant to follow for comparison. This is exploratory design work, not a
committed roadmap item — the single-profile MVP described above remains the near-term
build target.

Early hypothesis for a 50+ variant (see session design canvas for mockups):

- Taste-signal collection doesn't default to Spotify as the obvious choice — "Connect
  Spotify" and "tell us what you like" (manual genre/artist entry) are presented as
  equal-weight options, not primary/secondary.
- Larger, higher-contrast type throughout (roughly +2px body size, darker text color) and
  more breathing room per card.
- Sample curation leans toward sit-down dining, jazz clubs, wine bars, and supper clubs
  rather than nightlife/clubs — reflects a pacing and venue-type assumption to validate,
  not a hard rule.
- The "surprise me" action carries a text label ("Something different") alongside the
  icon, not icon-only.
- Ties into the rewards/booking portfolio idea below — a 50+ audience is more likely to
  hold premium cards and have established Resy/Yelp habits, which is why that idea
  surfaced in this profile's context first.

None of this is validated with real users yet. Before building a second profile, worth
deciding whether "profile" means a different curated experience for the same account, a
one-time onboarding branch, or a fully separate product surface — that's a real product
decision, not just a visual one.

## Relationship to FfAdvisor

This is a new, separate project — separate repo, separate GCP project, separate billing.
It reuses one *pattern* from FfAdvisor (YouTube transcript → Gemini structured extraction)
but shares no code, infra, or data with it. Decisions made for FfAdvisor (e.g. Firebase
Auth + Firestore approval gate, Cloud Run FastAPI backend) were reused here because they
worked well there, not because of any coupling between the two systems.
