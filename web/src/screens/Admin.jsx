import { useEffect, useState } from 'react';
import { theme } from '../theme.js';
import { api } from '../api.js';

function fmtDate(ts) {
  return ts ? new Date(ts * 1000).toLocaleString() : 'never seen';
}

function Section({ title, count, children }) {
  return (
    <div style={{ marginTop: 28 }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: theme.textMuted, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 10 }}>
        {title}{count != null ? ` (${count})` : ''}
      </div>
      {children}
    </div>
  );
}

function Row({ primary, secondary, action, actionLabel, busy }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
      background: theme.card, borderRadius: 14, padding: '12px 14px', marginBottom: 8,
      border: `1px solid ${theme.border}`,
    }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 14.5, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis' }}>{primary}</div>
        {secondary && <div style={{ fontSize: 12.5, color: theme.textFaint, marginTop: 2 }}>{secondary}</div>}
      </div>
      {action && (
        <button
          onClick={action}
          disabled={busy}
          style={{
            flexShrink: 0, border: 'none', borderRadius: 10, padding: '8px 14px', fontSize: 13, fontWeight: 600,
            cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.5 : 1,
            background: actionLabel === 'Revoke' ? theme.accentFoodSoft : theme.accentMusic,
            color: theme.white,
          }}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

// Admin approval page — a browser front end for the same manual,
// per-person decision approve_users.py's CLI already makes (see
// api/auth.py's require_admin/ADMIN_EMAILS). Reachable at /admin (see
// main.jsx) once signed in through the normal AuthGate flow; a signed-in
// non-admin just gets a 403 from every call here, shown as the error
// state below rather than a crash.
export function Admin() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busyKey, setBusyKey] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [preapproving, setPreapproving] = useState(false);

  const load = () => {
    setError('');
    api.adminListUsers().then(setData).catch(() => setError('not-admin'));
  };

  useEffect(load, []);

  const withBusy = (key, fn) => async () => {
    setBusyKey(key);
    try {
      await fn();
      load();
    } catch {
      setError('action-failed');
    } finally {
      setBusyKey('');
    }
  };

  const handlePreapprove = async () => {
    const email = newEmail.trim();
    if (!email) return;
    setPreapproving(true);
    try {
      await api.adminPreapprove(email);
      setNewEmail('');
      load();
    } catch {
      setError('action-failed');
    } finally {
      setPreapproving(false);
    }
  };

  const inputStyle = {
    border: `1px solid ${theme.border}`, borderRadius: 12, padding: '10px 14px',
    fontSize: 14, color: theme.text, background: theme.card, outline: 'none', flex: 1,
  };

  if (error === 'not-admin') {
    return (
      <div style={{ minHeight: '100vh', background: theme.bg, fontFamily: theme.fontBody, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
        <div style={{ textAlign: 'center', color: theme.textMuted, maxWidth: 280 }}>
          Not authorized to view this page.
        </div>
      </div>
    );
  }

  if (!data) {
    return <div style={{ minHeight: '100vh', background: theme.bg }} />;
  }

  return (
    <div style={{ minHeight: '100vh', background: theme.bg, fontFamily: theme.fontBody, color: theme.text }}>
      <div style={{ maxWidth: 560, margin: '0 auto', padding: '32px 24px 64px' }}>
        <div style={{ fontFamily: theme.fontDisplay, fontSize: 28 }}>Approvals</div>
        <div style={{ fontSize: 13.5, color: theme.textMuted, marginTop: 4 }}>
          Same manual, per-person decision as <code>approve_users.py</code> — just from a browser.
        </div>

        {error === 'action-failed' && (
          <div style={{ marginTop: 16, fontSize: 13, color: theme.accentFood }}>
            That didn't go through — try again.
          </div>
        )}

        <Section title="Preapprove someone new">
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handlePreapprove()}
              placeholder="someone@example.com"
              style={inputStyle}
            />
            <button
              onClick={handlePreapprove}
              disabled={preapproving || !newEmail.trim()}
              style={{
                border: 'none', borderRadius: 12, padding: '10px 18px', fontSize: 14, fontWeight: 600,
                background: theme.accentMusic, color: theme.white,
                cursor: preapproving || !newEmail.trim() ? 'default' : 'pointer',
                opacity: preapproving || !newEmail.trim() ? 0.5 : 1,
              }}
            >
              Add
            </button>
          </div>
          <div style={{ fontSize: 12, color: theme.textFaint, marginTop: 6 }}>
            Unlocks automatically the moment they sign in — no need to wait for them to do that first.
          </div>
        </Section>

        <Section title="Pending — signed in, waiting" count={data.pending.length}>
          {data.pending.length === 0 && <div style={{ fontSize: 13.5, color: theme.textFaint }}>Nobody's waiting right now.</div>}
          {data.pending.map((u) => (
            <Row
              key={u.uid}
              primary={u.email || '(no email)'}
              secondary={`uid: ${u.uid}`}
              actionLabel={u.email ? 'Approve' : ''}
              busy={busyKey === `approve:${u.uid}`}
              action={u.email ? withBusy(`approve:${u.uid}`, () => api.adminApprove(u.email)) : null}
            />
          ))}
        </Section>

        <Section title="Approved" count={data.approved.length}>
          {data.approved.length === 0 && <div style={{ fontSize: 13.5, color: theme.textFaint }}>No one approved yet.</div>}
          {data.approved.map((u) => (
            <Row
              key={u.uid}
              primary={u.email || `(uid: ${u.uid})`}
              secondary={`last active: ${fmtDate(u.last_active)}`}
              actionLabel="Revoke"
              busy={busyKey === `revoke:${u.uid}`}
              action={withBusy(`revoke:${u.uid}`, () => api.adminRevoke(u.email))}
            />
          ))}
        </Section>

        <Section title="Preapproved — waiting on first sign-in" count={data.preapproved.length}>
          {data.preapproved.length === 0 && <div style={{ fontSize: 13.5, color: theme.textFaint }}>Nothing pending.</div>}
          {data.preapproved.map((u) => (
            <Row
              key={u.email}
              primary={u.email}
              secondary={`preapproved: ${fmtDate(u.preapproved_at)}`}
              actionLabel="Revoke"
              busy={busyKey === `revoke:${u.email}`}
              action={withBusy(`revoke:${u.email}`, () => api.adminRevoke(u.email))}
            />
          ))}
        </Section>
      </div>
    </div>
  );
}
