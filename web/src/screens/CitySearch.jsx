import { useEffect, useState } from 'react';
import { theme } from '../theme.js';
import { api } from '../api.js';
import { StepHeader } from '../components/StepHeader.jsx';

export function CitySearch({ step, visitedCities, onPickCity }) {
  const [query, setQuery] = useState('');
  const [cities, setCities] = useState([]);

  useEffect(() => {
    api.cities({ q: query, visited: visitedCities }).then((d) => setCities(d.cities));
  }, [query, visitedCities]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <StepHeader step={step} total={4} title="Where are you headed?" />
      <div style={{ padding: '18px 26px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: theme.card, border: `1px solid ${theme.border}`, borderRadius: 16, padding: '12px 16px' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={theme.textFaint} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" />
          </svg>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a city"
            style={{ border: 'none', background: 'transparent', fontSize: 15, color: theme.text, flex: 1, outline: 'none' }}
          />
        </div>
      </div>
      <div style={{ padding: '14px 26px 8px', fontSize: 12.5, letterSpacing: '0.06em', color: theme.textFaint, textTransform: 'uppercase' }}>
        Trending for your taste
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 20px 20px' }}>
        {cities.map((c) => (
          <div
            key={c.id}
            onClick={() => onPickCity(c)}
            style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 8px', borderRadius: 16, cursor: 'pointer' }}
          >
            <div style={{ width: 46, height: 46, borderRadius: 12, background: `linear-gradient(135deg, ${theme.accentFood}, ${theme.accentMusic})`, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 21s-7-6.1-7-11a7 7 0 0114 0c0 4.9-7 11-7 11z" /><circle cx="12" cy="10" r="2.6" />
              </svg>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ fontSize: 16, fontWeight: 500 }}>
                  {c.name} <span style={{ fontWeight: 400, color: theme.textFaint, fontSize: 14 }}>· {c.country}</span>
                </div>
                {c.visited && (
                  <span style={{ fontSize: 11, background: theme.chipBg, color: '#B85E38', padding: '2px 8px', borderRadius: 9, fontWeight: 600 }}>
                    Been here
                  </span>
                )}
              </div>
              <div style={{ fontSize: 13.5, color: theme.textMuted, marginTop: 3 }}>{c.pitch}</div>
            </div>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={theme.textFaint} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </div>
        ))}
      </div>
    </div>
  );
}
