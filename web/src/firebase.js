// Same injection pattern as api.js's BASE: window.__FIREBASE_CONFIG__ is set
// by config.js at container startup in production (see
// docker-entrypoint.d/40-inject-config.sh), falling back to build-time
// VITE_FIREBASE_* vars for local dev. All of these values are public and
// safe to ship to the browser — Firebase's actual security boundary is
// Firestore rules / the backend's approval check, not hiding this config.
import { initializeApp } from 'firebase/app';
import { GoogleAuthProvider, getAuth, onAuthStateChanged, signInWithPopup, signOut } from 'firebase/auth';

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

// Tried switching this to signInWithRedirect (reasoning: the custom
// same-site auth domain should make redirect reliable, and popup has known
// multi-attempt flakiness) — made things strictly worse, an infinite
// redirect loop, confirmed live. Root cause: signInWithRedirect's own
// result-polling on the way back in uses a hidden iframe pointing at
// auth.traveldiscoveries.app, embedded on app.traveldiscoveries.app's page
// — still a cross-*origin* iframe even though the two share a registrable
// domain, so it's still subject to third-party storage partitioning. When
// that iframe can't see what the top-level authDomain context wrote
// moments earlier, the app never sees a signed-in user and is back to
// showing the sign-in screen — which looks like, and functionally is, an
// endless retry loop. So: back to signInWithPopup, same as FfAdvisor, which
// doesn't have that iframe-polling step at all.
export async function signInWithGoogle() {
  if (!auth) return;
  const provider = new GoogleAuthProvider();
  await signInWithPopup(auth, provider);
}

export async function signOutUser() {
  if (!auth) return;
  await signOut(auth);
}

export async function getIdToken() {
  if (!auth?.currentUser) return null;
  return auth.currentUser.getIdToken();
}
