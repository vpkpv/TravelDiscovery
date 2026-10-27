import { useEffect, useState } from 'react';
import { theme } from './theme.js';
import { api } from './api.js';
import { PhoneShell } from './components/PhoneShell.jsx';
import * as fb from './firebase.js';
import { isNative, connectGoogleNative } from './nativeLinks.js';

// Wraps the whole app. Three states beyond "let them through": Firebase
// isn't configured yet (renders children unmodified — same
// graceful-degradation stance as every other not-yet-set-up integration in
// this codebase), signed out (show a Google Sign-In button), or signed in
// but not yet approved (closed-pilot manual approval gate — see
// api/auth.py and CLAUDE.md's "Access control is manual Firestore
// approval").
//
// History: used to also track a redirect-specific failure state (a
// "sign-in isn't completing" message with debug output), built up while
// chasing a broken signInWithRedirect flow, then later a "tap again, this
// is a known Safari quirk" retry hint once signInWithPopup turned out to
// have its own version of the same problem. Both were UX smoothing over a
// client-SDK limitation, not a real fix — see firebase.js's
// signInWithGoogle for the actual fix (a server-side OAuth exchange with
// no popup/redirect/iframe handback at all), which made both obsolete.
const _ERROR_MESSAGES = {
  denied: 'Sign-in was cancelled.',
  unverified_email: "That Google account's email isn't verified — try a different account.",
  token_exchange_failed: 'Something went wrong signing you in — please try again.',
  sign_in_failed: 'Something went wrong signing you in — please try again.',
  not_configured: 'Sign-in isn’t set up yet.',
};

export function AuthGate({ children }) {
  const [status, setStatus] = useState(fb.configured() ? 'loading' : 'open');
  const [email, setEmail] = useState('');
  const [rechecking, setRechecking] = useState(false);
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    if (!fb.configured()) return;
    // Picks up the token (or error) api/main.py's /auth/google/callback
    // redirects back with, if the user just came from there — a no-op
    // otherwise. Runs once, before onAuthChange below ever needs to fire
    // from it.
    fb.completeSignInFromUrl().then((errorCode) => {
      if (errorCode) setAuthError(errorCode);
    });

    return fb.onAuthChange(async (user) => {
      if (!user) {
        setStatus('signed-out');
        setEmail('');
        return;
      }
      setAuthError('');
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
  // Google's OAuth policy blocks sign-in inside an embedded WebView
  // outright (disallowed_useragent) — unlike Spotify, there's no "it'll
  // just look worse" fallback here, so the native branch is load-bearing,
  // not a nicety. See nativeLinks.js's connectGoogleNative.
  const handleGoogleSignIn = () => {
    if (!isNative) {
      fb.signInWithGoogle();
      return;
    }
    connectGoogleNative(fb.googleLoginUrl).then(async (result) => {
      if (result.token) {
        const errorCode = await fb.completeSignInWithToken(result.token);
        if (errorCode) setAuthError(errorCode);
      } else {
        setAuthError(result.error || 'sign_in_failed');
      }
    });
  };

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
            onClick={handleGoogleSignIn}
            style={{
              border: `1.5px solid ${theme.border}`, borderRadius: 18, padding: '14px 22px',
              background: theme.card, fontSize: 15, fontWeight: 600, color: theme.text, cursor: 'pointer',
            }}
          >
            Sign in with Google
          </button>
          {authError && (
            <div style={{ fontSize: 12, color: theme.textFaint, maxWidth: 260 }}>
              {_ERROR_MESSAGES[authError] || 'Something went wrong signing you in — please try again.'}
            </div>
          )}
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
