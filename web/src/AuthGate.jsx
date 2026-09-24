import { useEffect, useState } from 'react';
import { theme } from './theme.js';
import { api } from './api.js';
import { PhoneShell } from './components/PhoneShell.jsx';
import * as fb from './firebase.js';

// Wraps the whole app. Three states beyond "let them through": Firebase
// isn't configured yet (renders children unmodified — same
// graceful-degradation stance as every other not-yet-set-up integration in
// this codebase), signed out (show a Google Sign-In button), or signed in
// but not yet approved (closed-pilot manual approval gate — see
// api/auth.py and CLAUDE.md's "Access control is manual Firestore
// approval").
export function AuthGate({ children }) {
  const [status, setStatus] = useState(fb.configured() ? 'loading' : 'open');
  const [email, setEmail] = useState('');
  const [redirectFailed, setRedirectFailed] = useState(false);

  useEffect(() => {
    if (!fb.configured()) return;

    fb.checkRedirectResult().then(({ attempted, succeeded }) => {
      if (attempted && !succeeded) setRedirectFailed(true);
    });

    return fb.onAuthChange(async (user) => {
      if (!user) {
        setStatus('signed-out');
        setEmail('');
        return;
      }
      setRedirectFailed(false);
      setEmail(user.email || '');
      try {
        const me = await api.me();
        setStatus(me.approved ? 'open' : 'pending');
      } catch {
        // A transient /api/me failure shouldn't strand a signed-in user on
        // a blank screen — treat it as still pending rather than open, the
        // safer default for a closed pilot.
        setStatus('pending');
      }
    });
  }, []);

  if (status === 'open') return children;

  if (status === 'loading') return <PhoneShell />;

  if (status === 'signed-out') {
    return (
      <PhoneShell>
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28, textAlign: 'center', gap: 20 }}>
          <div style={{ fontFamily: theme.fontDisplay, fontSize: 32 }}>Travel<br />Discovery</div>
          {redirectFailed ? (
            <div style={{ fontSize: 14, color: theme.textMuted, maxWidth: 280 }}>
              Sign-in isn't completing — this looks like Safari's "Prevent Cross-Site Tracking"
              privacy setting blocking it, not something wrong on your end. Try turning that off
              in Settings → Safari → Advanced → Privacy, or make sure you're not in Private
              Browsing, then try again.
            </div>
          ) : (
            <div style={{ fontSize: 14, color: theme.textMuted, maxWidth: 280 }}>
              This is a closed pilot — sign in to see if you've been approved.
            </div>
          )}
          <button
            onClick={fb.signInWithGoogle}
            style={{
              border: `1.5px solid ${theme.border}`, borderRadius: 18, padding: '14px 22px',
              background: theme.card, fontSize: 15, fontWeight: 600, color: theme.text, cursor: 'pointer',
            }}
          >
            Sign in with Google
          </button>
        </div>
      </PhoneShell>
    );
  }

  // pending
  return (
    <PhoneShell>
      <div style={{ display: 'flex', flexDirection: 'column', flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28, textAlign: 'center', gap: 16 }}>
        <div style={{ fontFamily: theme.fontDisplay, fontSize: 26 }}>You're on the list</div>
        <div style={{ fontSize: 14, color: theme.textMuted, maxWidth: 280 }}>
          {email} isn't approved for this pilot yet. Check back once you've heard from us.
        </div>
        <div onClick={fb.signOutUser} style={{ fontSize: 13, color: theme.textFaint, cursor: 'pointer', textDecoration: 'underline' }}>
          Sign out
        </div>
      </div>
    </PhoneShell>
  );
}
