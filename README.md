# TravelDiscovery

Taste-matched travel experience discovery — food & music recommendations grounded in a
user's actual taste (Spotify listening history + cuisine preference) and sourced from
insider-curated venue data (YouTube food influencers, verified against Google Places).

See [`docs/2026-08-20-taste-matched-discovery-design.md`](docs/2026-08-20-taste-matched-discovery-design.md)
for the MVP design doc.

## Status

Design complete, MVP scope agreed. Implementation not yet started.

## Stack

- iOS app (SwiftUI)
- FastAPI backend on Google Cloud Run
- Firebase Auth + Firestore (closed pilot, manual approval)
- Spotify OAuth (Dev Mode)
- Google Places API (venue grounding)
