import { useState } from 'react';
import { theme } from '../theme.js';
import { StepHeader } from '../components/StepHeader.jsx';
import { api } from '../api.js';

// Trip planning's foundational story (see the Product Backlog artifact's
// "Trips" epic) — dates, base address and party size, saved to
// users/{uid}/trips so a later anchor event/time-slot/ranking story has a
// real trip id to hang off of. Skippable: a trip isn't required to browse
// discovery results, same as every other onboarding step in this flow.
export function TripSetup({ city, onContinue, onSkip }) {
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [baseAddress, setBaseAddress] = useState('');
  const [partySize, setPartySize] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const canContinue = startDate && endDate && baseAddress.trim();

  const handleContinue = async () => {
    if (!canContinue) return;
    setSaving(true);
    setError('');
    try {
      const trip = await api.createTrip({
        city: city.slug || city.id,
        start_date: startDate,
        end_date: endDate,
        base_address: baseAddress.trim(),
        party_size: partySize,
      });
      onContinue(trip);
    } catch {
      setError("Couldn't save your trip — check your connection and try again.");
    } finally {
      setSaving(false);
    }
  };

  const inputStyle = {
    border: `1px solid ${theme.border}`, borderRadius: 14, padding: '12px 16px',
    fontSize: 15, color: theme.text, background: theme.card, outline: 'none', width: '100%',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <StepHeader
        step={6} total={6}
        title="Set up your trip"
        subtitle={`A few details for ${city.name} — we'll use these to time and place your picks.`}
      />
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 26px 8px', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: theme.textMuted, marginBottom: 6 }}>Arrive</div>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, color: theme.textMuted, marginBottom: 6 }}>Depart</div>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} style={inputStyle} />
          </div>
        </div>
        <div>
          <div style={{ fontSize: 13, color: theme.textMuted, marginBottom: 6 }}>Where you're staying</div>
          <input
            type="text"
            value={baseAddress}
            onChange={(e) => setBaseAddress(e.target.value)}
            placeholder="Hotel or neighborhood address"
            style={inputStyle}
          />
        </div>
        <div>
          <div style={{ fontSize: 13, color: theme.textMuted, marginBottom: 6 }}>Party size</div>
          <input
            type="number"
            min={1}
            value={partySize}
            onChange={(e) => setPartySize(Math.max(1, Number(e.target.value) || 1))}
            style={{ ...inputStyle, width: 90 }}
          />
        </div>
        {error && <div style={{ fontSize: 13.5, color: theme.accentFood }}>{error}</div>}
      </div>
      <div style={{ padding: '14px 26px 32px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button
          onClick={handleContinue}
          disabled={!canContinue || saving}
          style={{
            background: theme.text, color: '#FFFFFF', width: '100%', height: 54, borderRadius: 27,
            border: 'none', fontWeight: 600, fontSize: 16, opacity: canContinue && !saving ? 1 : 0.5,
            cursor: canContinue && !saving ? 'pointer' : 'default',
          }}
        >
          {saving ? 'Saving…' : 'Continue'}
        </button>
        <div onClick={onSkip} style={{ textAlign: 'center', fontSize: 13.5, color: theme.textFaint, cursor: 'pointer' }}>
          Skip for now
        </div>
      </div>
    </div>
  );
}
