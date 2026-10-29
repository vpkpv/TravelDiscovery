import { useEffect, useState } from 'react';
import { theme } from '../theme.js';
import { api, photoUrl } from '../api.js';
import { openExternal } from '../nativeLinks.js';

function mapsUrl(item) {
  const q = item.addr ? `${item.name}, ${item.addr}` : item.name;
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
}

const TYPE_LABEL = { food: 'Food', bar: 'Bar', music: 'Music' };

function SharedPickCard({ item }) {
  const accent = item.type === 'food' ? theme.accentFood : item.type === 'bar' ? theme.accentBar : theme.accentMusic;
  const accentSoft = item.type === 'food' ? theme.accentFoodSoft : item.type === 'bar' ? theme.accentBarSoft : theme.accentMusicSoft;
  return (
    <div
      onClick={() => openExternal(mapsUrl(item))}
      style={{ background: theme.card, borderRadius: 18, padding: 16, display: 'flex', gap: 14, boxShadow: '0 6px 16px rgba(43,36,32,0.06)', cursor: 'pointer' }}
    >
      {item.photo_ref ? (
        <img src={photoUrl(item.photo_ref, 200)} alt="" style={{ width: 72, height: 72, borderRadius: 14, flexShrink: 0, objectFit: 'cover' }} />
      ) : (
        <div style={{ width: 72, height: 72, borderRadius: 14, flexShrink: 0, background: `linear-gradient(135deg, ${accentSoft}, ${accent})` }} />
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 15.5, fontWeight: 600, lineHeight: 1.3 }}>{item.name}</div>
        <div style={{ fontSize: 12.5, color: accent, fontWeight: 600, marginTop: 2 }}>{TYPE_LABEL[item.type] || item.type}</div>
        {item.addr && <div style={{ fontSize: 13, color: theme.textFaint, marginTop: 3 }}>{item.addr}</div>}
      </div>
    </div>
  );
}

// Public, account-free counterpart to ResultsFeed/TripBanner — what someone
// gets when a trip owner taps "Share this trip" (see api/main.py's
// get_shared_trip). Rendered outside AuthGate entirely (see main.jsx), since
// whoever opens this link is never expected to sign in. Deliberately never
// shows base_address/distance — the server-side response already leaves
// those out (see the "hide base address" decision on this story), so there's
// nothing here to accidentally expose even if that changes later.
export function SharedTrip({ token }) {
  const [trip, setTrip] = useState(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    api.getSharedTrip(token).then(setTrip).catch(() => setNotFound(true));
  }, [token]);

  if (notFound) {
    return (
      <div style={{ minHeight: '100vh', background: theme.bg, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <div style={{ textAlign: 'center', color: theme.textMuted, fontFamily: theme.fontBody }}>
          This trip link isn't valid anymore — it may have been unshared.
        </div>
      </div>
    );
  }
  if (!trip) {
    return <div style={{ minHeight: '100vh', background: theme.bg }} />;
  }

  const fmt = (d) => new Date(`${d}T00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  const anchor = trip.anchor;

  return (
    <div style={{ minHeight: '100vh', background: theme.bg, fontFamily: theme.fontBody, color: theme.text }}>
      <div style={{ maxWidth: 480, margin: '0 auto', padding: '32px 24px 48px' }}>
        <div style={{ fontSize: 12.5, fontWeight: 600, color: theme.textFaint, letterSpacing: 0.3, textTransform: 'uppercase' }}>
          A trip shared from TravelDiscovery
        </div>
        <div style={{ fontFamily: theme.fontDisplay, fontSize: 30, marginTop: 6 }}>{trip.city_name}</div>
        <div style={{ fontSize: 14.5, color: theme.textMuted, marginTop: 4 }}>
          {fmt(trip.start_date)} – {fmt(trip.end_date)} · party of {trip.party_size || 1}
        </div>
        {anchor && (
          <div style={{ background: theme.chipBg, borderRadius: 14, padding: '12px 14px', marginTop: 16, fontSize: 13.5 }}>
            <div style={{ color: theme.textMuted }}>Anchor event</div>
            <div style={{ marginTop: 2, fontWeight: 600 }}>
              {anchor.venue_name} · {new Date(anchor.start_time).toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}
            </div>
          </div>
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 24 }}>
          {trip.items.length === 0 ? (
            <div style={{ fontSize: 13.5, color: theme.textFaint }}>No picks saved to this trip yet.</div>
          ) : (
            trip.items.map((item) => <SharedPickCard key={item.id || item.name} item={item} />)
          )}
        </div>
      </div>
    </div>
  );
}
