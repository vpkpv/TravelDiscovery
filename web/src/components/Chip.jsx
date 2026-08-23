import { theme } from '../theme.js';

export function Chip({ label, selected, onClick, checkIcon = true }) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: '11px 18px',
        borderRadius: 20,
        fontSize: 15,
        fontWeight: 500,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        cursor: 'pointer',
        userSelect: 'none',
        background: selected ? theme.accentFood : theme.card,
        color: selected ? '#FFFFFF' : theme.text,
        border: `1px solid ${selected ? theme.accentFood : theme.border}`,
      }}
    >
      {selected && checkIcon && (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 6L9 17l-5-5" />
        </svg>
      )}
      {label}
    </div>
  );
}
