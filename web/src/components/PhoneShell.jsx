import { theme } from '../theme.js';

// A mobile-width app frame. No fake status bar or device bezel — this is meant to run
// as a real page (dev in a desktop browser, later a real mobile web view), not to look
// like a mockup screenshot.
export function PhoneShell({ children }) {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        background: 'transparent',
        fontFamily: theme.fontBody,
        color: theme.text,
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 460,
          minHeight: '100vh',
          background: `linear-gradient(180deg, ${theme.bg} 0%, ${theme.bgGradientEnd} 100%)`,
          display: 'flex',
          flexDirection: 'column',
          boxShadow: theme.shadowHairline,
          // Only matters once this runs as an installed PWA (see index.html's
          // viewport-fit=cover + manifest.json) — a normal browser tab's own
          // chrome already keeps content clear of the notch/home indicator,
          // and these resolve to 0 there, so this is a no-op in that case.
          paddingTop: 'env(safe-area-inset-top)',
          paddingBottom: 'env(safe-area-inset-bottom)',
        }}
        className="app-shell"
      >
        {children}
      </div>
    </div>
  );
}
