import { useEffect, useState } from 'react';
import { theme } from '../theme.js';
import { api } from '../api.js';

function FoodIcon({ color = '#FFFFFF' }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 8h1a4 4 0 010 8h-1" /><path d="M2 8h16v9a4 4 0 01-4 4H6a4 4 0 01-4-4V8z" /><path d="M6 1v3M10 1v3M14 1v3" />
    </svg>
  );
}
function MusicIcon({ color = '#FFFFFF' }) {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 18V5l12-2v13" /><circle cx="6" cy="18" r="3" /><circle cx="18" cy="16" r="3" />
    </svg>
  );
}

function ResultCard({ item, saved, onToggleSave }) {
  const isFood = item.type === 'food';
  return (
    <div style={{ background: theme.card, borderRadius: 18, padding: 16, display: 'flex', gap: 14, boxShadow: '0 6px 16px rgba(43,36,32,0.06)' }}>
      <div
        style={{
          width: 60, height: 60, borderRadius: 14, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: isFood
            ? `linear-gradient(135deg, ${theme.accentFoodSoft}, ${theme.accentFood})`
            : `linear-gradient(135deg, ${theme.accentMusicSoft}, ${theme.accentMusic})`,
        }}
      >
        {isFood ? <FoodIcon /> : <MusicIcon />}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ fontSize: 16.5, fontWeight: 600, lineHeight: 1.3 }}>{item.name}</div>
          <div onClick={() => onToggleSave(item.id)} style={{ flexShrink: 0, padding: 2, cursor: 'pointer' }}>
            <svg width="19" height="19" viewBox="0 0 24 24" fill={saved ? theme.accentFood : 'none'} stroke={saved ? theme.accentFood : theme.textFaint} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
              <path d="M6 3h12a1 1 0 011 1v17l-7-4-7 4V4a1 1 0 011-1z" />
            </svg>
          </div>
        </div>
        <div style={{ fontSize: 13.5, color: theme.textMuted, marginTop: 4 }}>{item.meta}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8, fontSize: 13 }}>
          {isFood ? (
            <>
              <svg width="13" height="13" viewBox="0 0 24 24" fill={theme.accentFood} stroke="none"><path d="M12 2l2.9 6.4 6.9.8-5.1 4.8 1.4 6.9L12 17.7l-6.1 3.2 1.4-6.9-5.1-4.8 6.9-.8z" /></svg>
              <span style={{ fontWeight: 500 }}>{item.rating}</span>
              <span style={{ color: theme.textFaint }}>· {item.addr}</span>
            </>
          ) : (
            <>
              <span style={{ background: '#EAF2F2', color: theme.accentMusic, padding: '3px 9px', borderRadius: 10, fontWeight: 500, fontSize: 12.5 }}>{item.genre}</span>
              <span style={{ color: theme.textFaint }}>· {item.addr}</span>
            </>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginTop: 10, background: '#F7F2E9', borderRadius: 10, padding: '9px 11px' }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#B5AA9C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ marginTop: 2, flexShrink: 0 }}>
            <path d="M12 3l1.9 4.6L18 9l-4.1 1.4L12 15l-1.9-4.6L6 9l4.1-1.4z" />
          </svg>
          <div style={{ fontSize: 13, color: theme.textMuted, lineHeight: 1.45, fontStyle: 'italic' }}>{item.why}</div>
        </div>
      </div>
    </div>
  );
}

export function ResultsFeed({ city }) {
  const [filter, setFilter] = useState('all');
  const [items, setItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [saved, setSaved] = useState({});
  const [surprise, setSurprise] = useState(null); // null = browsing, {items, seed} = surprise mode

  useEffect(() => {
    api.results({ city: city.id, filter }).then((d) => {
      setItems(d.items);
      setTotalCount(d.count);
    });
  }, [city.id, filter]);

  const toggleSave = (id) => setSaved((s) => ({ ...s, [id]: !s[id] }));

  const rollSurprise = (seed) => {
    api.surprise({ city: city.id, seed }).then((d) => setSurprise({ items: d.items, seed }));
  };

  const showing = surprise ? surprise.items : items;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <div style={{ padding: '48px 24px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontFamily: theme.fontDisplay, fontSize: 32, lineHeight: 1 }}>{city.name}</div>
            <div style={{ marginTop: 6, fontSize: 14, color: theme.textMuted }}>
              {surprise ? 'One perfect pairing, chosen for you' : `${totalCount} picks matched to your taste`}
            </div>
          </div>
          <div style={{ width: 40, height: 40, borderRadius: 12, background: theme.card, border: `1px solid ${theme.border}`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={theme.text} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1 14h6M9 8h6M17 16h6" />
            </svg>
          </div>
        </div>

        {!surprise ? (
          <div style={{ display: 'flex', gap: 10, marginTop: 18, alignItems: 'center' }}>
            {['all', 'food', 'music'].map((f) => (
              <div
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  padding: '9px 16px', borderRadius: 16, fontSize: 14, fontWeight: 500, cursor: 'pointer', textTransform: 'capitalize',
                  background: filter === f ? (f === 'food' ? theme.accentFood : f === 'music' ? theme.accentMusic : theme.text) : theme.card,
                  color: filter === f ? '#FFFFFF' : theme.text,
                  border: filter === f ? 'none' : `1px solid ${theme.border}`,
                }}
              >
                {f}
              </div>
            ))}
            <div
              onClick={() => rollSurprise(0)}
              style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6, background: theme.chipBg, borderRadius: 14, padding: '8px 12px', cursor: 'pointer' }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#B85E38" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3l1.9 4.6L18 9l-4.1 1.4L12 15l-1.9-4.6L6 9l4.1-1.4z" />
              </svg>
              <span style={{ fontSize: 13, color: '#B85E38', fontWeight: 600 }}>Something different</span>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 18 }}>
            <div onClick={() => setSurprise(null)} style={{ cursor: 'pointer', fontSize: 14, color: theme.textMuted, display: 'flex', alignItems: 'center', gap: 4 }}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={theme.textMuted} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 18l-6-6 6-6" /></svg>
              Back to all picks
            </div>
            <div onClick={() => rollSurprise(surprise.seed + 1)} style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, background: theme.text, color: '#fff', padding: '9px 16px', borderRadius: 16, fontSize: 14, fontWeight: 500 }}>
              Shuffle again
            </div>
          </div>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 22px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {showing.length === 0 && (
          <div style={{ fontSize: 14, color: theme.textFaint, padding: '24px 4px' }}>
            No picks yet for {city.name} — only Lisbon has sample data in this scaffold.
          </div>
        )}
        {showing.map((item) => (
          <ResultCard key={item.id} item={item} saved={!!saved[item.id]} onToggleSave={toggleSave} />
        ))}
        {surprise && showing.length > 0 && (
          <div style={{ textAlign: 'center', fontSize: 13, color: theme.textFaint, marginTop: 4 }}>
            Dinner, then a short walk to the show — that's your pairing for tonight.
          </div>
        )}
      </div>
    </div>
  );
}
