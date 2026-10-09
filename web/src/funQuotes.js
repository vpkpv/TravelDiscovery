// Shared bank of short, food/travel-flavored one-liners — pilot feedback
// ("make this fun and have funny quotes on the page", then "how about
// having the quotes all through the experience") asked for personality
// spread across the app, not confined to one loading screen. Kept in one
// file, grouped by where each pool is used, so the voice stays consistent
// instead of drifting screen to screen, and so a tone pass later only
// touches one place.

export function pickFrom(pool) {
  return pool[Math.floor(Math.random() * pool.length)];
}

// ResultsFeed's loading state (the one piece of copy every user sees on
// every single city load).
export const LOADING_QUOTES = [
  'Googling "is it rude to ask for extra bread" on your behalf…',
  'Asking locals so you don’t have to post "any recs??" on Instagram…',
  'Separating the hidden gems from the tourist-trap tiramisu…',
  'Making sure nothing on this list is secretly a chain…',
  'Politely ignoring every restaurant with a laminated menu…',
  'Cross-checking against actual humans who’ve actually eaten here…',
  'Sniffing out the place with the suspiciously good reviews…',
  'Reserving judgment on the place that’s "famous for its vibe"…',
  'Making sure your trip has a soundtrack, not just a menu…',
  'Double-checking nobody’s favorite spot closed in 2019…',
  'Weighing ambiance against "will I regret the walk there"…',
  'Quietly vetoing anywhere with a tourist-menu QR code…',
];

// StepHeader's small caption under each onboarding step's subtitle — kept
// low-stakes and short since these screens still have a real job (collect
// an answer), not purely decorative like the loading state.
export const ONBOARDING_ASIDES = [
  'No pressure — you can change all of this later in Settings.',
  'We promise not to judge your answers. Mostly.',
  'This takes less time than deciding where to eat tonight.',
  'Somewhere, a "Top 10 Hidden Gems" listicle is furious we exist.',
  'Fun fact: nobody has ever regretted more garlic.',
  'A human does not read this. Don’t overthink it.',
  'Still faster than scrolling 40 tabs of "best restaurants near me."',
  'This part’s quick — we save the real work for Google Places.',
  'Picky eaters welcome. We don’t judge, we just filter.',
];

// ResultsFeed's empty state ("No picks yet for X") — shown below the
// functional line, never replacing it, since the functional line is the
// one that actually explains what happened.
export const EMPTY_STATE_ASIDES = [
  'Either this city keeps its secrets well, or we haven’t found them yet.',
  'Not every city gives up its best spots easily.',
  'We’re still working on this one — check back soon.',
  'Even we were surprised by how quiet this list is.',
];

// ResultsFeed's "Something different" (surprise) outro line, split by
// whether the pairing includes a bar or a restaurant.
export const SURPRISE_OUTROS_FOOD = [
  'Dinner, then a short walk to the show — that’s your pairing for tonight.',
  'A good meal and a short walk to the show. Our work here is done.',
  'Eat well, walk it off, enjoy the show. In that order.',
];

export const SURPRISE_OUTROS_BAR = [
  'Drinks, then a short walk to the show — that’s your pairing for tonight.',
  'A drink, a short walk, a show. No notes.',
  'Start with a drink, end with a show. Works every time.',
];

// Welcome screen's one-time aside under the taste-method disclaimer.
export const WELCOME_ASIDES = [
  'Built by people who’ve also stood outside a restaurant reading reviews for ten minutes.',
  'No algorithm has ever regretted more garlic either.',
  'We’ve all opened five tabs for "best tacos near me." This is the sixth, but better.',
];
