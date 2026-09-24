// Same injection pattern as api.js's BASE: window.__FIREBASE_CONFIG__ is set
// by config.js at container startup in production (see
// docker-entrypoint.d/40-inject-config.sh), falling back to build-time
// VITE_FIREBASE_* vars for local dev. All of these values are public and
// safe to ship to the browser — Firebase's actual security boundary is
// Firestore rules / the backend's approval check, not hiding this config.
import { initializeApp } from 'firebase/app';
import { GoogleAuthProvider, getAuth, getRedirectResult, onAuthStateChanged, signInWithPopup, signInWithRedirect, signOut } from 'firebase/auth';

const injected = window.__FIREBASE_CONFIG__ || {};

const firebaseConfig = {
  apiKey: injected.apiKey || import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: injected.authDomain || import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: injected.projectId || import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: injected.appId || import.meta.env.VITE_FIREBASE_APP_ID,
};

// Firebase Auth is only usable once config is present — configured() lets
// the rest of the app check that before trying to use it, same pattern as
// api/auth.py's configured() on the backend.
export function configured() {
  return Boolean(firebaseConfig.apiKey && firebaseConfig.projectId);
}

let app = null;
let auth = null;
if (configured()) {
  app = initializeApp(firebaseConfig);
  auth = getAuth(app);
}

export function onAuthChange(callback) {
  if (!auth) return () => {};
  return onAuthStateChanged(auth, callback);
}

// Firebase's authDomain (gen-lang-client-....firebaseapp.com) is a
// different site than this app (travel-web-....run.app) — Safari's
// Intelligent Tracking Prevention treats storage set during that
// cross-domain hop as third-party and can silently drop it, on both
// popup and redirect alike, bouncing the user back to signed-out with no
// error. There's no code fix for that (the real fix is a custom auth
// domain matching this app's own site, a bigger infra change); this is a
// platform-by-platform heuristic instead. Mobile browsers were the
// original popup failure (blocked/partitioned popups on Safari/Chrome
// mobile — see git history), so they get redirect; desktop tends to
// handle a same-tab-group popup more reliably, so it's tried first there,
// falling back to redirect if the popup itself is blocked.
function isMobile() {
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
}

// Set right before signInWithRedirect() so checkRedirectResult() can tell
// "we just attempted a redirect and it silently produced no user" (the ITP
// case above) apart from "this is a normal fresh page load, no redirect was
// ever in flight" — getRedirectResult() alone resolves to null in both
// cases, with no error, so there'd be nothing else to distinguish them by.
// sessionStorage survives a same-tab top-level redirect-and-back, unlike
// the cross-domain storage ITP actually blocks.
const REDIRECT_PENDING_KEY = 'td_redirect_pending';

export async function signInWithGoogle() {
  if (!auth) return;
  const provider = new GoogleAuthProvider();
  if (isMobile()) {
    sessionStorage.setItem(REDIRECT_PENDING_KEY, '1');
    await signInWithRedirect(auth, provider);
    return;
  }
  try {
    await signInWithPopup(auth, provider);
  } catch (exc) {
    console.warn('Popup sign-in failed, falling back to redirect:', exc);
    sessionStorage.setItem(REDIRECT_PENDING_KEY, '1');
    await signInWithRedirect(auth, provider);
  }
}

// Call once on load: after signInWithRedirect sends the browser back here,
// this is what actually completes the sign-in and surfaces any error (an
// expired session, a blocked redirect, etc.) that would otherwise fail
// silently — onAuthStateChanged alone won't report *why* a redirect sign-in
// didn't go through, only that no user is signed in.
//
// Returns { attempted, succeeded } so the caller (AuthGate) can tell a
// silently-failed redirect (attempted && !succeeded — confirmed live: an
// iPhone Safari beta tester stuck bouncing back to the same sign-in button
// with no feedback, over and over) apart from an ordinary signed-out state.
export async function checkRedirectResult() {
  if (!auth) return { attempted: false, succeeded: false };
  const attempted = sessionStorage.getItem(REDIRECT_PENDING_KEY) === '1';
  sessionStorage.removeItem(REDIRECT_PENDING_KEY);
  try {
    const result = await getRedirectResult(auth);
    return { attempted, succeeded: Boolean(result?.user) };
  } catch (exc) {
    console.warn('Google sign-in redirect failed:', exc);
    return { attempted, succeeded: false };
  }
}

export async function signOutUser() {
  if (!auth) return;
  await signOut(auth);
}

export async function getIdToken() {
  if (!auth?.currentUser) return null;
  return auth.currentUser.getIdToken();
}
