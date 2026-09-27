// Same injection pattern as api.js's BASE: window.__FIREBASE_CONFIG__ is set
// by config.js at container startup in production (see
// docker-entrypoint.d/40-inject-config.sh), falling back to build-time
// VITE_FIREBASE_* vars for local dev. All of these values are public and
// safe to ship to the browser — Firebase's actual security boundary is
// Firestore rules / the backend's approval check, not hiding this config.
import { initializeApp } from 'firebase/app';
import { GoogleAuthProvider, getAuth, onAuthStateChanged, signInWithRedirect, signOut } from 'firebase/auth';

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

// signInWithRedirect, not signInWithPopup — confirmed live: even after the
// custom same-site auth domain fixed the *cross-site* problems a popup
// flow used to work around, popup sign-in still needed 2-3 attempts to
// actually stick (a known class of flakiness independent of that fix —
// Firebase's popup flow depends on a same-origin-with-opener check and a
// same-window postMessage handshake that various browsers/extensions
// interfere with in ways a full-page redirect just doesn't hit). Now that
// redirect doesn't need the cross-site workaround it used to (the whole
// reason popup was chosen over it originally), it's the simpler, more
// reliable default: one navigation, no popup-blocker/COOP/postMessage
// surface at all. onAuthChange (above) picks up the result once Firebase
// finishes processing the redirect on the way back in, same as it did for
// popup — no separate getRedirectResult() bookkeeping needed here.
export async function signInWithGoogle() {
  if (!auth) return;
  const provider = new GoogleAuthProvider();
  await signInWithRedirect(auth, provider);
}

export async function signOutUser() {
  if (!auth) return;
  await signOut(auth);
}

export async function getIdToken() {
  if (!auth?.currentUser) return null;
  return auth.currentUser.getIdToken();
}
