// Design tokens for the 40/50+ profile — larger type, higher-contrast text than the
// original discovery-MVP mockups, per docs/2026-08-20-taste-matched-discovery-design.md.
//
// fontDisplay was Instrument Serif until real-world feedback described it as
// "stretched" — its dramatic hairline/thick-stroke contrast reads that way
// at display sizes to eyes unfamiliar with the style, and works against the
// higher-legibility goal above. Fraunces keeps an editorial, warm serif feel
// (fits a food/travel app) without that contrast, and is a variable font
// (opsz axis) so it stays crisp from small labels up to large headlines.
export const theme = {
  bg: '#FBF8F3',
  card: '#FFFFFF',
  text: '#221D19',
  textMuted: '#6B6259',
  textFaint: '#A79C8E',
  border: '#E4DACB',
  accentFood: '#D9754A',
  accentFoodSoft: '#EFA179',
  accentMusic: '#3E7F86',
  accentMusicSoft: '#6FA7AE',
  chipBg: '#F3EDE1',
  spotifyGreen: '#1DB954',
  fontDisplay: "'Fraunces', Georgia, serif",
  fontBody: "'Work Sans', -apple-system, 'Segoe UI', sans-serif",
};
