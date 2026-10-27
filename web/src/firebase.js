// Same injection pattern as api.js's BASE: window.__FIREBASE_CONFIG__ is set
// by config.js at container startup in production (see
// docker-entrypoint.d/40-inject-config.sh), falling back to build-time
// VITE_FIREBASE_* vars for local dev. All of these values are public and
// safe to ship to the browser — Firebase's actual security boundary is
// Firestore rules / the backend's approval check, not hiding this config.
import { initializeApp } from 'firebase/app';
import { getAuth, onAuthStateChanged, signInWithCustomToken, signOut } from 'firebase/auth';
import { API_BASE } from './apiBase.js';

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

// History: first tried signInWithRedirect (reasoning: a custom same-site
// auth domain should make redirect reliable, and popup has known
// multi-attempt flakiness) — made things strictly worse, an infinite
// redirect loop, confirmed live. Root cause: signInWithRedirect's own
// result-polling on the way back in uses a hidden iframe pointing at
// auth.traveldiscoveries.app, embedded on app.traveldiscoveries.app's page
// — still a cross-*origin* iframe even though the two share a registrable
// domain, so it's still subject to third-party storage partitioning. Fell
// back to signInWithPopup instead, which doesn't have that iframe-polling
// step — but it has its own version of the same underlying problem
// (confirmed live: Safari popups needed several attempts, worst right
// after clearing history/cookies), and there was no further client-SDK
// fix left to try.
//
// Now does the whole OAuth exchange server-side instead (see
// api/google_oauth.py) — a full top-level navigation to the backend,
// which redirects to Google, exchanges the code itself, and hands back a
// one-time custom token via completeSignInFromUrl below. No popup, no
// redirect, no iframe-based handback for Safari to partition.
export const googleLoginUrl = `${API_BASE}/auth/google/login`;

export function signInWithGoogle() {
  window.location.href = googleLoginUrl;
}

// Shared by completeSignInFromUrl (web, below) and AuthGate's native path
// (connectGoogleNative's resolved token) — one place that actually calls
// signInWithCustomToken, so both entry points stay in sync on how a
// custom token becomes a real session.
export async function completeSignInWithToken(token) {
  if (!auth) return 'not_configured';
  try {
    await signInWithCustomToken(auth, token);
    return '';
  } catch (exc) {
    console.error('signInWithCustomToken failed:', exc);
    return 'sign_in_failed';
  }
}

// Called once on app load (see AuthGate.jsx) to pick up the token
// api/main.py's /auth/google/callback redirects back with, if the user
// just came from there. signInWithCustomToken is a plain authenticated
// network call — unlike signInWithPopup/signInWithRedirect, it has no
// popup/iframe choreography for Safari's storage partitioning to break,
// which is what actually fixes the flakiness rather than just smoothing
// over it client-side.
//
// Strips authToken/auth_error from the URL immediately either way, before
// awaiting anything — a custom token is a short-lived (1hr) credential
// that shouldn't linger in the visible URL bar or browser history any
// longer than it takes to read it once.
//
// Returns the auth_error code from a failed server-side attempt (e.g.
// "denied", "unverified_email"), or "" — callers show this as an error
// message; it's never thrown, since a user just arriving at the app with
// no token/error at all (the common case) isn't a failure.
export async function completeSignInFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('authToken');
  const authError = params.get('auth_error');
  if (!token && !authError) return '';

  params.delete('authToken');
  params.delete('auth_error');
  const cleanedSearch = params.toString();
  window.history.replaceState({}, '', window.location.pathname + (cleanedSearch ? `?${cleanedSearch}` : '') + window.location.hash);

  if (!auth || !token) return authError || '';
  return completeSignInWithToken(token);
}

export async function signOutUser() {
  if (!auth) return;
  await signOut(auth);
}

export async function getIdToken() {
  if (!auth?.currentUser) return null;
  return auth.currentUser.getIdToken();
}
