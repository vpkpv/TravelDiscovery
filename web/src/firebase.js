// Same injection pattern as api.js's BASE: window.__FIREBASE_CONFIG__ is set
// by config.js at container startup in production (see
// docker-entrypoint.d/40-inject-config.sh), falling back to build-time
// VITE_FIREBASE_* vars for local dev. All of these values are public and
// safe to ship to the browser — Firebase's actual security boundary is
// Firestore rules / the backend's approval check, not hiding this config.
import { initializeApp } from 'firebase/app';
import { GoogleAuthProvider, getAuth, onAuthStateChanged, signInWithPopup, signInWithRedirect, signOut } from 'firebase/auth';

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

// Plain signInWithPopup — matches FfAdvisor's sign-in (same author, same
// GCP/Cloud Run hosting pattern), which has no mobile/desktop branching, no
// redirect-result bookkeeping, and just works. TravelDiscovery used to have
// a lot more here: a mobile-forced signInWithRedirect path, sessionStorage
// markers, a checkRedirectResult() with a timing-based grace period, and a
// localStorage debug breadcrumb — all built up while chasing what turned
// out to be a red herring (a beta tester's genuinely broken redirect flow
// against the *default* firebaseapp.com auth domain, which a custom
// same-site auth domain, auth.traveldiscoveries.app, fixed at the
// infrastructure level — see deploy-env.sh.example). Once that was fixed
// and popup-based sign-in was already succeeding, none of that extra
// machinery was doing anything useful anymore, so it's gone. onAuthChange
// (above) alone reacts once sign-in actually resolves, same as FfAdvisor.
// Falls back to signInWithRedirect only if the popup itself is outright
// blocked (a thrown error) — rare, and doesn't need special handling
// beyond letting onAuthChange pick up whatever it eventually resolves to.
export async function signInWithGoogle() {
  if (!auth) return;
  const provider = new GoogleAuthProvider();
  try {
    await signInWithPopup(auth, provider);
  } catch (exc) {
    console.warn('Popup sign-in failed, falling back to redirect:', exc);
    await signInWithRedirect(auth, provider);
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
