// Native-shell-safe link handling. In a plain browser, window.open works
// fine both for external links and for the Spotify OAuth popup (see
// App.jsx's connectSpotify). Inside the Capacitor-wrapped iOS app there is
// no browser tab/popup model at all — window.open() in a WKWebView is
// unreliable at best, and Apple's review guidelines require third-party
// OAuth (Spotify included) to run in the system browser, not an embedded
// WKWebView. @capacitor/browser's Browser.open() (ASWebAuthenticationSession
// on iOS) is the standard fix for both cases.
import { Capacitor } from '@capacitor/core';
import { Browser } from '@capacitor/browser';
import { App as CapApp } from '@capacitor/app';

export const isNative = Capacitor.isNativePlatform();

// Opens a plain external link (a Maps or booking-provider URL) — the
// in-app system browser on native, a normal new tab on web.
export function openExternal(url) {
  if (isNative) {
    Browser.open({ url });
  } else {
    window.open(url, '_blank', 'noopener,noreferrer');
  }
}

// Spotify OAuth inside the native shell: same two-leg flow as the web
// popup (connect -> approve on Spotify's own domain -> bounce back to us),
// run through the system browser instead of an embedded WKWebView, and
// handed back via a custom URL scheme deep link instead of localStorage —
// there's no second same-origin tab inside the app to share storage with.
// See api/main.py's spotify_callback `native:` state branch, which
// redirects to NATIVE_APP_SCHEME://spotify-callback instead of to
// spotify-popup-done.html, and web/ios/App/App/Info.plist, which registers
// that scheme with iOS so appUrlOpen fires here.
export function connectSpotifyNative(loginUrl) {
  return new Promise((resolve) => {
    let done = false;
    let urlListener;
    let finishedListener;

    const finish = (result) => {
      if (done) return;
      done = true;
      urlListener?.remove();
      finishedListener?.remove();
      Browser.close().catch(() => {});
      resolve(result);
    };

    CapApp.addListener('appUrlOpen', (data) => {
      let url;
      try {
        url = new URL(data.url);
      } catch {
        return;
      }
      if (url.host !== 'spotify-callback') return;
      const artistsRaw = url.searchParams.get('artists');
      const error = url.searchParams.get('error');
      if (artistsRaw) {
        try {
          finish({ artists: JSON.parse(artistsRaw) });
        } catch {
          finish({ error: 'denied' });
        }
      } else {
        finish({ error: error || 'denied' });
      }
    }).then((h) => { urlListener = h; });

    // Covers the in-app browser being dismissed by hand with no result
    // ever delivered (consent denied via its own close button) — same
    // gap the web popup flow's `popup.closed` poll covers.
    Browser.addListener('browserFinished', () => finish({ error: 'denied' }))
      .then((h) => { finishedListener = h; });

    Browser.open({ url: `${loginUrl}?native=1` });
  });
}

// Google OAuth inside the native shell — same shape as
// connectSpotifyNative above, but not optional the way that one's
// popup-vs-system-browser choice was: Google's own OAuth policy actively
// detects and refuses sign-in attempted inside an embedded WebView
// (`disallowed_useragent`), so without this, "Sign in with Google" would
// just fail outright inside the Capacitor shell, not merely look worse.
// See api/main.py's google_callback `native:` state branch, which
// redirects to NATIVE_APP_SCHEME://google-callback instead of to
// WEB_URL. Resolves to { token } or { error }, mirroring
// firebase.js's completeSignInFromUrl's authToken/auth_error shape so
// the caller can reuse the same signInWithCustomToken / error-message
// handling either way.
export function connectGoogleNative(loginUrl) {
  return new Promise((resolve) => {
    let done = false;
    let urlListener;
    let finishedListener;

    const finish = (result) => {
      if (done) return;
      done = true;
      urlListener?.remove();
      finishedListener?.remove();
      Browser.close().catch(() => {});
      resolve(result);
    };

    CapApp.addListener('appUrlOpen', (data) => {
      let url;
      try {
        url = new URL(data.url);
      } catch {
        return;
      }
      if (url.host !== 'google-callback') return;
      const token = url.searchParams.get('authToken');
      const error = url.searchParams.get('error');
      finish(token ? { token } : { error: error || 'denied' });
    }).then((h) => { urlListener = h; });

    Browser.addListener('browserFinished', () => finish({ error: 'denied' }))
      .then((h) => { finishedListener = h; });

    Browser.open({ url: `${loginUrl}?native=1` });
  });
}
