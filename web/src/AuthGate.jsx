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
//
// This used to also track a redirect-specific failure state (a "sign-in
// isn't completing" message with debug output), built up while chasing a
// broken signInWithRedirect flow against the default firebaseapp.com auth
// domain. A custom same-site auth domain (see firebase.js) fixed the
// original cross-site problem, but redirect turned out to have a second,
// independent one (see firebase.js's signInWithGoogle) — so sign-in goes
// through signInWithPopup, and onAuthChange alone is the reliable signal,
// same as it is in FfAdvisor.
export function AuthGate({ children }) {
  const [status, setStatus] = useState(fb.configured() ? 'loading' : 'open');
  const [email, setEmail] = useState('');
  const [rechecking, setRechecking] = useState(false);

  useEffect(() => {
    if (!fb.configured()) return;

    return fb.onAuthChange(async (user) => {
      if (!user) {
        setStatus('signed-out');
        setEmail('');
        return;
      }
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

  // Approval happens out of band (someone runs approve_users.py while this
  // tab is already sitting on the pending screen) — onAuthChange above only
  // fires once, at sign-in, so without this a now-approved user has no way
  // to find out short of a full page reload or signing out and back in.
  // Confirmed live: that reload step wasn't obvious, so every pilot invite
  // turned into "try refreshing" over text.
  const recheckApproval = async () => {
    setRechecking(true);
    try {
      const me = await api.me();
      setStatus(me.approved ? 'open' : 'pending');
    } catch {
      // stays pending — a transient failure here isn't evidence either way
    } finally {
      setRechecking(false);
    }
  };

  if (status === 'open') return children;

  if (status === 'loading') return <PhoneShell />;

  if (status === 'signed-out') {
    return (
      <PhoneShell>
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, alignItems: 'center', justifyContent: 'center', padding: 28, textAlign: 'center', gap: 20 }}>
          <div style={{ fontFamily: theme.fontDisplay, fontSize: 32 }}>Travel<br />Discovery</div>
          <div style={{ fontSize: 14, color: theme.textMuted, maxWidth: 280 }}>
            This is a closed pilot — sign in to see if you've been approved.
          </div>
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
          {email} isn't approved for this pilot yet. Once you've heard you're in, tap below.
        </div>
        <button
          onClick={recheckApproval}
          disabled={rechecking}
          style={{
            border: `1.5px solid ${theme.border}`, borderRadius: 18, padding: '12px 20px',
            background: theme.card, fontSize: 14, fontWeight: 600, color: theme.text,
            cursor: rechecking ? 'default' : 'pointer', opacity: rechecking ? 0.6 : 1,
          }}
        >
          {rechecking ? 'Checking…' : 'Try again'}
        </button>
        <div onClick={fb.signOutUser} style={{ fontSize: 13, color: theme.textFaint, cursor: 'pointer', textDecoration: 'underline' }}>
          Sign out
        </div>
      </div>
    </PhoneShell>
  );
}
