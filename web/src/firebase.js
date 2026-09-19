// Same injection pattern as api.js's BASE: window.__FIREBASE_CONFIG__ is set
// by config.js at container startup in production (see
// docker-entrypoint.d/40-inject-config.sh), falling back to build-time
// VITE_FIREBASE_* vars for local dev. All of these values are public and
// safe to ship to the browser — Firebase's actual security boundary is
// Firestore rules / the backend's approval check, not hiding this config.
import { initializeApp } from 'firebase/app';
import { GoogleAuthProvider, getAuth, getRedirectResult, onAuthStateChanged, signInWithRedirect, signOut } from 'firebase/auth';

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

export async function signInWithGoogle() {
  if (!auth) return;
  // A popup, not a redirect, was the original implementation — switched
  // after real-world testing on mobile browsers kept re-showing the sign-in
  // screen on every visit. Mobile Safari/Chrome popups are prone to being
  // blocked or storage-partitioned from the opener page, so the sign-in can
  // silently fail to persist even though it looked like it completed. A
  // full-page redirect (Firebase's own recommendation for mobile web)
  // doesn't have that failure mode.
  await signInWithRedirect(auth, new GoogleAuthProvider());
}

// Call once on load: after signInWithRedirect sends the browser back here,
// this is what actually completes the sign-in and surfaces any error (an
// expired session, a blocked redirect, etc.) that would otherwise fail
// silently — onAuthStateChanged alone won't report *why* a redirect sign-in
// didn't go through, only that no user is signed in.
export async function checkRedirectResult() {
  if (!auth) return;
  try {
    await getRedirectResult(auth);
  } catch (exc) {
    console.warn('Google sign-in redirect failed:', exc);
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
