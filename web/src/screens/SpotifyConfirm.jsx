import { theme } from '../theme.js';
import { Chip } from '../components/Chip.jsx';
import { StepHeader } from '../components/StepHeader.jsx';

// Shown right after a successful Spotify connection, before this silently fell straight
// through to the cuisine question with no visible confirmation of what was captured.
export function SpotifyConfirm({ artists, onContinue, onPickManually }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <StepHeader
        step={1} total={4}
        title="Found your taste"
        subtitle={`Pulled from your recent Spotify listening — this is what we'll match music picks against.`}
      />
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px 8px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {artists.map((a) => (
            <Chip key={a} label={a} selected checkIcon={false} />
          ))}
        </div>
      </div>
      <div style={{ padding: '16px 24px 32px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        <button
          onClick={onContinue}
          style={{
            background: theme.text, color: '#FFFFFF',
            width: '100%', height: 54, borderRadius: 27, border: 'none', fontWeight: 600, fontSize: 16,
          }}
        >
          Continue
        </button>
        <div
          onClick={onPickManually}
          style={{ textAlign: 'center', fontSize: 13.5, color: theme.textMuted, cursor: 'pointer' }}
        >
          Not quite right? Pick genres manually instead
        </div>
      </div>
    </div>
  );
}
