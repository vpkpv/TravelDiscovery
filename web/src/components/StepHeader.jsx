import { theme } from '../theme.js';

export function StepHeader({ step, total, title, subtitle }) {
  return (
    <div style={{ padding: '48px 26px 0' }}>
      <div style={{ fontSize: 13, letterSpacing: '0.06em', color: theme.textFaint, textTransform: 'uppercase', marginBottom: 14 }}>
        Step {step} of {total}
      </div>
      <div style={{ fontFamily: theme.fontDisplay, fontSize: 28, lineHeight: 1.15, color: theme.text }}>{title}</div>
      {subtitle && (
        <div style={{ marginTop: 8, fontSize: 14.5, color: theme.textMuted, lineHeight: 1.5 }}>{subtitle}</div>
      )}
    </div>
  );
}
