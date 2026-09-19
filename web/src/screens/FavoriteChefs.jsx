import { useState } from 'react';
import { theme } from '../theme.js';
import { StepHeader } from '../components/StepHeader.jsx';

// Manual, typed input only — same as the cuisine quick-pick, deliberately not
// inferred from Instagram/any social API (see CLAUDE.md's food-taste
// constraint). Used to check whether a chef/foodie account someone follows
// has a real restaurant in the city being searched (see places.find_chef_venues).
export function FavoriteChefs({ step, chefs = [], onChange, onContinue, onSkip }) {
  const [draft, setDraft] = useState('');

  const add = () => {
    const name = draft.trim();
    if (!name || chefs.includes(name)) {
      setDraft('');
      return;
    }
    onChange([...chefs, name]);
    setDraft('');
  };

  const remove = (name) => onChange(chefs.filter((c) => c !== name));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <StepHeader
        step={step} total={5}
        title="Follow any chefs or foodie accounts?"
        subtitle="Add a few names — we'll check for a real restaurant of theirs in every city you search."
      />
      <div style={{ padding: '18px 26px 8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: theme.card, border: `1px solid ${theme.border}`, borderRadius: 16, padding: '12px 16px' }}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                add();
              }
            }}
            placeholder="e.g. Gordon Ramsay"
            style={{ border: 'none', background: 'transparent', fontSize: 15, color: theme.text, flex: 1, outline: 'none' }}
          />
          <div onClick={add} style={{ cursor: 'pointer', color: theme.accentFood, fontWeight: 600, fontSize: 14 }}>
            Add
          </div>
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px 8px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {chefs.map((c) => (
            <div
              key={c}
              style={{ display: 'flex', alignItems: 'center', gap: 8, background: theme.chipBg, borderRadius: 16, padding: '8px 14px', fontSize: 14 }}
            >
              {c}
              <span onClick={() => remove(c)} style={{ cursor: 'pointer', color: theme.textFaint, fontWeight: 700, lineHeight: 1 }}>
                ×
              </span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ padding: '14px 26px 32px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button
          onClick={onContinue}
          style={{ background: theme.text, color: '#FFFFFF', width: '100%', height: 54, borderRadius: 27, border: 'none', fontWeight: 600, fontSize: 16 }}
        >
          {chefs.length ? `Continue (${chefs.length} added)` : 'Continue'}
        </button>
        <div onClick={onSkip} style={{ textAlign: 'center', fontSize: 13.5, color: theme.textFaint, cursor: 'pointer' }}>
          Skip for now
        </div>
      </div>
    </div>
  );
}
