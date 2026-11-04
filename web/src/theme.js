// Design tokens for the 40/50+ profile — larger type, higher-contrast text than the
// original discovery-MVP mockups, per docs/2026-08-20-taste-matched-discovery-design.md.
//
// fontDisplay was Instrument Serif until real-world feedback described it as
// "stretched" — its dramatic hairline/thick-stroke contrast reads that way
// at display sizes to eyes unfamiliar with the style, and works against the
// higher-legibility goal above. Fraunces keeps an editorial, warm serif feel
// (fits a food/travel app) without that contrast, and is a variable font
// (opsz axis) so it stays crisp from small labels up to large headlines.
// Converts a '#rrggbb' token to an rgba() string at the given alpha — keeps
// a translucent overlay/shadow tied to its named base color instead of a
// second, easily-drifting hex literal (e.g. a scrim that's really just
// `ink` at low opacity).
export function withAlpha(hex, alpha) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

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
  chipText: '#B85E38',
  musicChipBg: '#EAF2F2',
  badgeGold: '#9B6515',
  badgeGoldSoft: '#FFF1D3',
  quoteBg: '#FFF6EF',
  quoteIcon: '#B5AA9C',
  bannerGradientStart: '#F0EDFF',
  bannerGradientEnd: '#FFF0EA',
  bannerBorder: '#E4DBFA',
  shadowCard: '0 6px 16px rgba(43,36,32,0.06)',
  shadowButton: '0 5px 14px rgba(55,35,52,.08)',
  sunrise: '#FFCB6B',
  berry: '#D84671',
  ink: '#201A27',
  white: '#FFFFFF',
  spotifyGreen: '#1DB954',
  fontDisplay: "'Fraunces', Georgia, serif",
  fontBody: "'Work Sans', -apple-system, 'Segoe UI', sans-serif",
};
