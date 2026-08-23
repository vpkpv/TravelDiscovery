import { useEffect, useState } from 'react';
import { theme } from '../theme.js';
import { api } from '../api.js';
import { Chip } from '../components/Chip.jsx';
import { StepHeader } from '../components/StepHeader.jsx';

export function CuisinePick({ step, selected, onChange, onContinue }) {
  const [cuisines, setCuisines] = useState([]);

  useEffect(() => {
    api.cuisines().then((d) => setCuisines(d.cuisines));
  }, []);

  const toggle = (c) => {
    onChange(selected.includes(c) ? selected.filter((x) => x !== c) : [...selected, c]);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <StepHeader
        step={step} total={4}
        title="What flavors do you crave?"
        subtitle="Pick a few — we'll match food recs to your taste, sourced from real food-influencer videos, not generic listings."
      />
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px 8px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {cuisines.map((c) => (
            <Chip key={c} label={c} selected={selected.includes(c)} onClick={() => toggle(c)} />
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
