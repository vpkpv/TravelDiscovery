import { useEffect, useState } from 'react';
import { theme } from '../theme.js';
import { api } from '../api.js';
import { StepHeader } from '../components/StepHeader.jsx';

export function CitiesVisited({ step, visited, onChange, onContinue, onSkip }) {
  const [cities, setCities] = useState([]);

  useEffect(() => {
    api.cities().then((d) => setCities(d.cities));
  }, []);

  const toggle = (id) => {
    onChange(visited.includes(id) ? visited.filter((x) => x !== id) : [...visited, id]);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <StepHeader
        step={step} total={4}
        title="Where have you already been?"
        subtitle="We'll spotlight new picks in cities you know, and prioritize places that are new to you."
      />
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px 8px' }}>
        {cities.map((c) => {
          const isVisited = visited.includes(c.id);
          return (
            <div
              key={c.id}
              onClick={() => toggle(c.id)}
              style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 6px', borderRadius: 14, cursor: 'pointer' }}
            >
              <div
                style={{
                  width: 24, height: 24, borderRadius: 7, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: isVisited ? theme.text : 'transparent',
                  border: isVisited ? 'none' : `1.5px solid ${theme.border}`,
                }}
              >
                {isVisited && (
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M20 6L9 17l-5-5" />
                  </svg>
                )}
              </div>
              <div style={{ fontSize: 16, fontWeight: 500 }}>
                {c.name} <span style={{ fontWeight: 400, color: theme.textFaint, fontSize: 14.5 }}>· {c.country}</span>
              </div>
            </div>
          );
        })}
      </div>
      <div style={{ padding: '14px 26px 32px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button
          onClick={onContinue}
          style={{ background: theme.text, color: '#FFFFFF', width: '100%', height: 54, borderRadius: 27, border: 'none', fontWeight: 600, fontSize: 16 }}
        >
          {visited.length ? `Continue (${visited.length} marked)` : 'Continue'}
        </button>
        <div onClick={onSkip} style={{ textAlign: 'center', fontSize: 13.5, color: theme.textFaint, cursor: 'pointer' }}>
          Skip for now
        </div>
      </div>
    </div>
  );
}
