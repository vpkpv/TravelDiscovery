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
      <div style={{ fontSize: 13, letterSpacing: '0.06em', color: theme.textFaint, textTransform: 'uppercase', marginBottom: 14 }}>
        Step {step} of {total}
      </div>
      <div style={{ fontFamily: theme.fontDisplay, fontSize: 28, lineHeight: 1.15, color: theme.text }}>{title}</div>
      {subtitle && (
        <div style={{ marginTop: 8, fontSize: 14.5, color: theme.textMuted, lineHeight: 1.5 }}>{subtitle}</div>
      )}
      <div style={{ marginTop: 8, fontSize: 12.5, color: theme.textFaint, fontStyle: 'italic' }}>{aside}</div>
    </div>
  );
}
