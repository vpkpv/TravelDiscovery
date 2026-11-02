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
  bg: '#FFF9F1',
  card: '#FFFFFF',
  text: '#201A27',
  textMuted: '#665D70',
  textFaint: '#978D9B',
  border: '#E9DDE2',
  accentFood: '#F06C4E',
  accentFoodSoft: '#FFAA87',
  accentMusic: '#4169E1',
  accentMusicSoft: '#8EA8FF',
  accentBar: '#7855B7',
  accentBarSoft: '#B59AE8',
  chipBg: '#FFF0E8',
  sunrise: '#FFCB6B',
  berry: '#D84671',
  ink: '#201A27',
  spotifyGreen: '#1DB954',
  fontDisplay: "'Fraunces', Georgia, serif",
  fontBody: "'Work Sans', -apple-system, 'Segoe UI', sans-serif",
};
