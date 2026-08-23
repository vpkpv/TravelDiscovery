import { theme } from '../theme.js';

export function Welcome({ onChooseSpotify, onChooseManual }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <div style={{ padding: '48px 28px 0' }}>
        <div style={{ fontFamily: theme.fontDisplay, fontSize: 36, lineHeight: 1.1 }}>
          Travel<br />Discovery
        </div>
        <div style={{ marginTop: 14, fontSize: 16, color: theme.textMuted, maxWidth: 300, lineHeight: 1.5 }}>
          Recommendations built around what you actually enjoy — not what's popular.
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '24px 28px', gap: 16 }}>
        <div style={{ fontSize: 14, color: theme.textMuted, fontWeight: 500 }}>
          How should we learn your music taste?
        </div>

        <button
          onClick={onChooseSpotify}
          style={{
            border: `1.5px solid ${theme.border}`, borderRadius: 18, padding: 18,
            display: 'flex', alignItems: 'center', gap: 14, background: theme.card, textAlign: 'left',
          }}
        >
          <div style={{ width: 44, height: 44, borderRadius: 12, background: theme.spotifyGreen, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0B2E14" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 14v-2a8 8 0 0116 0v2" /><rect x="2" y="14" width="4" height="7" rx="2" /><rect x="18" y="14" width="4" height="7" rx="2" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: theme.text }}>Connect Spotify</div>
            <div style={{ fontSize: 13.5, color: theme.textMuted, marginTop: 2 }}>Fastest option, if you already use it</div>
          </div>
        </button>

        <button
          onClick={onChooseManual}
          style={{
            border: `1.5px solid ${theme.border}`, borderRadius: 18, padding: 18,
            display: 'flex', alignItems: 'center', gap: 14, background: theme.card, textAlign: 'left',
          }}
        >
          <div style={{ width: 44, height: 44, borderRadius: 12, background: '#EAF2F2', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={theme.accentMusic} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" />
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, color: theme.text }}>Tell us what you like</div>
            <div style={{ fontSize: 13.5, color: theme.textMuted, marginTop: 2 }}>Pick a few genres — takes about a minute</div>
          </div>
        </button>

        <div style={{ fontSize: 13, color: theme.textFaint, lineHeight: 1.5, marginTop: 4 }}>
          Either way, we never post anything or change your accounts. You can switch methods later in Settings.
        </div>
      </div>
    </div>
  );
}
