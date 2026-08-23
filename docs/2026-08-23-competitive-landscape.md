# Competitive Landscape

Status: Research pass before implementation planning, prompted by "AskLayla is one such
frequently used app." Findings below are from web research done 2026-08-23.

## Summary

No existing product combines both taste signals (music + food) into one discovery feed
for a new city the way this MVP is designed to. The closest analog — Spotify x Amex x
Resy's "Music Tastes" — proves the concept has appetite but shipped only as a time-limited
co-marketing campaign, not a standing product. Competitors cluster into three groups:
broad AI trip planners, food-only discovery apps, and music-only discovery apps. The gap
is the intersection of all three: bidirectional taste-matching, insider-curated content,
scoped to travel/new-city discovery.

## Direct AI trip planners (broad, itinerary-first)

These compete on breadth (full trip planning: flights, hotels, activities, dining) via
conversational AI, not on a music/cuisine taste profile.

- **AskLayla** — conversational AI planner. Learns preferences through chat, generates a
  day-by-day itinerary with hotels, flights, transfers, and a mix of popular sights and
  "hidden gems." Personalization comes from conversation, not a Spotify listening profile
  or explicit cuisine picks. Broader scope than our discovery-only MVP — it plans the
  whole trip, we're intentionally not doing that yet.
- **Mindtrip** — chatbot layered on an interactive map; strong for group trip planning;
  monetizes via booking commissions. ~350K monthly US visitors as of mid-2026.
- **Wonderplan** — fast, free itinerary generator. Skips clarifying questions for speed,
  which means less personalization depth.

## Food-only discovery

- **World of Mouth** — 800+ vetted food experts (chefs like Massimo Bottura, Ana Roš)
  hand-write recommendations across 3,000+ destinations, 20,000+ reviews. No ads, no star
  ratings. This is the closest existing analog to our "insider-curated, not generic LLM"
  principle — but curation is named human experts, not a YouTube-transcript-extraction
  pipeline.
- **Beli** — "Letterboxd for food": head-to-head restaurant ranking instead of star
  ratings, social friend-feed, 75M+ rankings as of early 2026. Personalization is social
  (what your friends ranked highly), not audio/cuisine-signal-based.
- **Ness** — matches diners to restaurants via a taste algorithm with price/cuisine
  controls. Closest food-only taste-matching precedent, but no travel/city-discovery
  framing and no music component.

## Music-only discovery

- **Dice** — connects Spotify/Apple Music to recommend gigs, club nights, and festivals
  based on actual listening data. This is the direct precedent for our "Spotify → music
  taste → venue match" mechanic — but scoped to ticketed concerts, not general travel
  discovery, and with no food component.
- **Sofar Sounds** — intimate live shows where the venue is hidden until 36 hours before
  showtime and the artist lineup is a surprise until you arrive. Notable as real prior art
  for a "surprise me" interaction pattern in this exact space (food/music experience
  discovery), even though it's a ticketing product, not a recommendation feed.

## The one existing food+music crossover

**"Music Tastes by Amex"** (Spotify × American Express × Resy, launched Nov 2024) is
nearly our exact core mechanic: Spotify derives a Music Taste profile (Smooth, Hearty,
Lush, Fiery, Buttery, Earthy, Saucy, Fresh) from listening habits, and Resy recommends
restaurants matching it. Key limitations that leave the gap open:

- Time-limited co-marketing campaign, not a standing product
- Restricted to 8 US cities (Atlanta, Austin, Chicago, LA, Miami, NYC, SF, DC) — no
  international / travel-destination framing
- Restaurant-only — no reciprocal music-venue recommendations
- Requires an Amex Gold card tie-in for the credit/booking flow

## Where our gap actually is

Nobody ships all of:

1. **Bidirectional taste-matching** — Spotify informs food picks *and* cuisine picks
   inform/complement music picks, in one combined feed (not two separate apps)
2. **Insider-curated via a repeatable content pipeline** — YouTube transcript extraction
   (reusing the FfAdvisor pattern), not named human curators (World of Mouth) or a generic
   POI database
3. **Scoped explicitly to travel/new-city discovery** — not home-city dining (Beli, Ness),
   not ticketed events only (Dice, Sofar), not full-itinerary planning (AskLayla, Mindtrip)

AskLayla and Mindtrip compete on breadth; World of Mouth and Beli compete on trust/social
proof for food only; Dice and Sofar compete on music only; Music Tastes by Amex proved
demand for the taste-matching mechanic but never turned it into a durable, city-agnostic,
bidirectional product. That intersection is the bet this MVP is making.

## Differentiation as scope grows to full itinerary planning

The founder has confirmed intent to expand past discovery into full itinerary planning —
which puts AskLayla and Mindtrip in direct competition, not just adjacent. Discovery-only
differentiation (bidirectional taste-matching, insider curation) doesn't automatically
survive that expansion, because AskLayla/Mindtrip already do itinerary logistics well
(routing, timing, booking). The wedge that does survive: **taste-fit is the itinerary's
sequencing objective, not a filter applied before it.**

Concretely: AskLayla and Mindtrip build itineraries by optimizing for logistics (what's
open, what's nearby, what fits the day) and layer personalization on as a preference
filter over an otherwise generic candidate pool. This product's bet is the reverse — the
itinerary is assembled by chaining taste-matched food + music picks (the discovery MVP's
core mechanic) into a day/multi-day sequence, with logistics as the constraint, not the
objective. A stop makes it into the plan because it fits the user's taste graph, not
because it's popular and nearby.

Two things make this defensible rather than just a feature flag:

1. It's not a bolt-on — it's the discovery MVP's mechanic (taste-matched food+music pairs,
   the "surprise me" pairing logic) extended in time instead of shown as a single-city
   feed. No separate itinerary-personalization system to build.
2. It compounds with the insider-curation + Places-grounding trust story: competitors'
   itinerary stops come from general LLM/web knowledge; ours come from a vetted pipeline.
   "Every stop in your itinerary is something a real insider recommended and we verified
   exists" is a claim AskLayla/Mindtrip can't make without rebuilding their sourcing.

This is a product-strategy note, not a build decision — worth revisiting explicitly when
itinerary planning moves from "intent" to a scoped subsystem (it's currently still
explicitly out of scope per the MVP design doc).

## Rewards/booking portfolio integration (speculative, not MVP-scoped)

Raised as an idea for the 50+ profile specifically: link a user's existing rewards and
booking accounts (American Express Platinum, Resy, Yelp) so the app can (1) surface picks
already covered by a card benefit ("covered by your $50 Resy dining credit") and (2) let a
user reserve a food pick inline via Resy instead of leaving the app.

This isn't speculative in the sense of "nobody would want it" — the **Music Tastes by
Amex** precedent above (Spotify × Amex × Resy) is direct evidence that Amex and Resy
already see commercial value in taste-based discovery tied to a card benefit. It's
speculative in scope: linking real financial/loyalty accounts is an OAuth/API integration
against a different trust and compliance bar than Spotify or Google Places (the MVP's
current external dependencies), and would likely require an actual partnership
conversation with Amex/Resy rather than just API access. Treat this as a post-MVP,
partnership-dependent backlog item, not a build task — see the mockup in the session's
design canvas (Connected Accounts screen + a food card with an inline "Reserve on Resy"
action) for what it could look like.

## Open questions this raises (worth revisiting before/during implementation)

- Music Tastes by Amex suggests restaurant partners (Resy, Amex) may already see value in
  this exact mechanic — worth knowing whether a similar partnership path is realistic for
  us, or whether we stay fully independent.
- Sofar Sounds' "hidden until 36 hours before" pattern is a stronger, more literal
  "surprise" mechanic than our current "surprise me" pill (which reveals immediately) —
  worth deciding if we want to borrow any of that suspense, or if immediate reveal is
  correct for a travel-planning (not spontaneous local) use case.
- World of Mouth's expert-curator model is a viable alternative or complement to
  YouTube-transcript extraction if transcript quality/coverage turns out to be thin for a
  given city — worth a fallback note in the architecture doc once we're building ingestion.
