import { useState } from 'react';
import { theme, withAlpha } from '../theme.js';
import { WELCOME_ASIDES, pickFrom } from '../funQuotes.js';

export function Welcome({ onChooseSpotify, onChooseManual }) {
  const [aside] = useState(() => pickFrom(WELCOME_ASIDES));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <div style={{ padding: '48px 28px 0', position: 'relative' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 7, padding: '7px 11px', borderRadius: 99, background: theme.chipBg, color: theme.accentFood, fontSize: 11.5, fontWeight: 700, letterSpacing: '.09em', textTransform: 'uppercase' }}>
          <span style={{ width: 7, height: 7, borderRadius: '50%', background: theme.accentFood, boxShadow: `0 0 0 4px ${theme.accentFood}22` }} /> Taste-led travel
        </div>
        <div style={{ fontFamily: theme.fontDisplay, fontWeight: 600, fontSize: 43, lineHeight: .98, letterSpacing: '-.05em', marginTop: 18 }}>
          Go where your<br /><span style={{ color: theme.accentFood }}>taste</span> takes you.
        </div>
        <div style={{ marginTop: 17, fontSize: 16, color: theme.textMuted, maxWidth: 316, lineHeight: 1.55 }}>
          Matched to your real Spotify taste, not a quiz. Picks sourced from food insiders, not crowd reviews — every one verified still open.
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '30px 28px 26px', gap: 13 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 4 }}>
          <div style={{ fontSize: 15, color: theme.text, fontWeight: 700 }}>Start with your soundtrack</div>
          <div style={{ fontSize: 12.5, color: theme.textFaint }}>About 1 minute</div>
        </div>

        <button
          onClick={onChooseSpotify}
          style={{
            border: 'none', borderRadius: 20, padding: 18,
            display: 'flex', alignItems: 'center', gap: 14, background: `linear-gradient(135deg, ${theme.spotifyGreen}, ${theme.spotifyGreenDark})`, textAlign: 'left', color: theme.white, boxShadow: `0 12px 24px ${withAlpha(theme.spotifyGreen, 0.22)}`,
          }}
        >
          <div style={{ width: 44, height: 44, borderRadius: 13, background: withAlpha(theme.white, 0.18), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={theme.white} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 14v-2a8 8 0 0116 0v2" /><rect x="2" y="14" width="4" height="7" rx="2" /><rect x="18" y="14" width="4" height="7" rx="2" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>Connect Spotify</div>
            <div style={{ fontSize: 13.5, color: withAlpha(theme.white, 0.82), marginTop: 2 }}>Use your listening history</div>
          </div>
        </button>

        <button
          onClick={onChooseManual}
          style={{
            border: `1.5px solid ${theme.border}`, borderRadius: 20, padding: 18,
            display: 'flex', alignItems: 'center', gap: 14, background: theme.card, textAlign: 'left',
          }}
        >
          <div style={{ width: 44, height: 44, borderRadius: 13, background: theme.musicIconBg, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={theme.accentMusic} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: theme.text }}>Tell us what you like</div>
            <div style={{ fontSize: 13.5, color: theme.textMuted, marginTop: 2 }}>Pick genres yourself, no account needed</div>
          </div>
        </button>

        <div style={{ fontSize: 13, color: theme.textFaint, lineHeight: 1.5, marginTop: 8 }}>
          Your profile stays private. You can switch methods whenever you like.
        </div>
        <div style={{ fontSize: 12.5, color: theme.textFaint, lineHeight: 1.5, fontStyle: 'italic' }}>
          {aside}
        </div>
      </div>
    </div>
  );
}
