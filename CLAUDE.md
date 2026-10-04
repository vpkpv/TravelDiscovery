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

## Current scope: discovery + trip planning (Phase 1). Budgeting is still deferred.

The long-term product has three subsystems (discovery, planning, budgeting). Originally MVP
was discovery-only, with planning and budgeting deferred until discovery was validated with
real users. That's since changed: trip planning is now active Phase 1 scope, not deferred —
trip structure (city, dates, base address, party size), an anchor event, open time slots,
distance/slot-aware ranking, a shareable trip page, and before/after-trip scorecards are all
Phase 1 stories, alongside discovery itself. Budgeting remains out of scope.

**The "TravelDiscovery: Product Backlog" artifact** (linked from this repo's Claude Code
session history) is the authoritative story list and phase/priority/status tracker — read it
before re-deriving scope from the codebase or this file. It cross-checks its "Done" statuses
against this branch directly, so it's generally more current than a quick read of the code.

Per-user storage underlies all of Phase 1: every choice (genres, cuisines, visited cities,
trips, saves, scores) is stored against the signed-in account, not just locally — see the
backlog's "Per-user data model" section for the Firestore shape (`user_prefs/{uid}`,
`saved_picks/{uid}` today; a `users/{uid}` subcollection shape is the target once trips and
scores actually land, not before).

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
