import { useState } from 'react';
import { theme } from '../theme.js';
import { ONBOARDING_ASIDES, pickFrom } from '../funQuotes.js';

export function StepHeader({ step, total, title, subtitle }) {
  // Picked once per step (StepHeader remounts fresh on every onboarding
  // screen, since each step is a different component) rather than on a
  // timer — pilot feedback asked for personality throughout the app, not
  // just the results-loading screen, and every onboarding step shares
  // this component, so this is the one place that reaches all of them.
  const [aside] = useState(() => pickFrom(ONBOARDING_ASIDES));
  return (
    <div style={{ padding: '48px 26px 0' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 17 }}>
        <div style={{ fontSize: 11.5, letterSpacing: '0.12em', color: theme.accentBar, textTransform: 'uppercase', fontWeight: 700 }}>
          Your travel taste
        </div>
        <div style={{ fontSize: 12, color: theme.textMuted, fontWeight: 600 }}>0{step} / 0{total}</div>
      </div>
      <div style={{ height: 5, borderRadius: 999, background: '#F0E5E5', marginBottom: 20, overflow: 'hidden' }}>
        <div style={{ width: `${(step / total) * 100}%`, height: '100%', borderRadius: 999, background: `linear-gradient(90deg, ${theme.accentFood}, ${theme.berry})` }} />
      </div>
      <div style={{ fontFamily: theme.fontDisplay, fontSize: 31, fontWeight: 600, lineHeight: 1.1, color: theme.text, letterSpacing: '-0.03em' }}>{title}</div>
      {subtitle && (
        <div style={{ marginTop: 8, fontSize: 14.5, color: theme.textMuted, lineHeight: 1.5 }}>{subtitle}</div>
      )}
      <div style={{ marginTop: 11, fontSize: 12.5, color: theme.accentBar, fontStyle: 'italic' }}>{aside}</div>
    </div>
  );
}
