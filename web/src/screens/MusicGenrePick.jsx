import { useEffect, useState } from 'react';
import { theme } from '../theme.js';
import { api } from '../api.js';
import { Chip } from '../components/Chip.jsx';
import { StepHeader } from '../components/StepHeader.jsx';

// Manual taste-entry path — the fallback described in the design doc for when Spotify
// isn't the right fit. Produces the same shape of taste signal (a set of genres) without
// needing OAuth. Also doubles as the Spotify-failure fallback: a successful Spotify
// connection skips this screen entirely (see App.jsx), so tasteMethod === 'spotify' here
// always means the OAuth flow failed and we're falling back to manual entry.
export function MusicGenrePick({ selected, onChange, onContinue, tasteMethod }) {
  const [genres, setGenres] = useState([]);

  useEffect(() => {
    api.musicGenres().then((d) => setGenres(d.genres));
  }, []);

  const toggle = (g) => {
    onChange(selected.includes(g) ? selected.filter((x) => x !== g) : [...selected, g]);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <StepHeader
        step={1} total={4}
        title="What do you listen to?"
        subtitle={
          tasteMethod === 'spotify'
            ? "We couldn't read your Spotify listening history just now — pick a few genres instead and we'll use those."
            : 'Pick a few genres or artists you gravitate toward — this stands in for a Spotify connection.'
        }
      />
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px 8px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {genres.map((g) => (
            <Chip key={g} label={g} selected={selected.includes(g)} onClick={() => toggle(g)} />
          ))}
        </div>
      </div>
      <div style={{ padding: '16px 24px 32px' }}>
        <button
          onClick={onContinue}
          style={{
            background: selected.length ? theme.text : theme.border,
            color: selected.length ? '#FFFFFF' : theme.textFaint,
            width: '100%', height: 54, borderRadius: 27, border: 'none', fontWeight: 600, fontSize: 16,
          }}
        >
          {selected.length ? `Continue (${selected.length} selected)` : 'Pick at least one'}
        </button>
      </div>
    </div>
  );
}
