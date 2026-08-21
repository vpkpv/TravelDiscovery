# TravelDiscovery

A taste-matched travel discovery app: recommends food and music experiences in a city,
matched to the user's actual taste (Spotify listening history for music, a cuisine
quick-pick for food), sourced from insider-curated venue data (YouTube food influencers,
transcript-extracted with Gemini, grounded against Google Places to drop hallucinated or
defunct venues).

This is a separate project from FfAdvisor (fantasy football analyzer) — separate repo,
separate GCP project, separate billing. It reuses FfAdvisor's YouTube transcript → Gemini
extraction *pattern* but shares no code or infra.

**`docs/2026-08-20-taste-matched-discovery-design.md`** is the MVP design doc — read it
before re-deriving product scope or architecture from the codebase.

## Current scope: discovery only

The long-term product has three subsystems (discovery, planning, budgeting). MVP is
**discovery only** — planning and budgeting are explicitly out of scope until discovery is
validated with real users.

## Durable do's and don'ts

- Spotify integration runs in **Dev Mode** deliberately — it caps the app to allowlisted
  users, which matches the closed-pilot access model already in place for other reasons.
  Don't treat this as a bug to "fix" by requesting production quota without discussing
  the tradeoff (production approval is slow and not guaranteed).
- Food taste comes from an explicit **cuisine quick-pick**, not inferred from an external
  API. Don't replace this with automatic inference for MVP.
- Access control is **manual Firestore approval**, same pattern as FfAdvisor — closed
  pilot by design, not open signup.
- Venue candidates that don't resolve to a real Google Places record must be **dropped**,
  not shown — this is the mechanism that prevents hallucinated/defunct venues.
