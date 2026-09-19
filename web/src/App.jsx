import { useEffect, useState } from 'react';
import { PhoneShell } from './components/PhoneShell.jsx';
import { Welcome } from './screens/Welcome.jsx';
import { MusicGenrePick } from './screens/MusicGenrePick.jsx';
import { CuisinePick } from './screens/CuisinePick.jsx';
import { FavoriteChefs } from './screens/FavoriteChefs.jsx';
import { CitiesVisited } from './screens/CitiesVisited.jsx';
import { CitySearch } from './screens/CitySearch.jsx';
import { ResultsFeed } from './screens/ResultsFeed.jsx';
import { SpotifyConfirm } from './screens/SpotifyConfirm.jsx';
import { api, spotifyLoginUrl } from './api.js';
import * as fb from './firebase.js';

const STORAGE_KEY = 'traveldiscovery.onboarding.v1';

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const DEFAULT_STATE = {
  step: 'welcome', // welcome -> genres (manual, or Spotify-failure fallback) -> cuisines -> chefs -> visited -> search -> results
  tasteMethod: null, // 'spotify' | 'manual'
  musicGenres: [], // manual path's fixed-vocabulary picks
  musicArtists: [], // Spotify path's top artist names — a freeform signal, not genre-bucketed (see api/spotify.py)
  spotifyFailed: false,
  cuisines: [],
  favoriteChefs: [], // manual, typed names — see FavoriteChefs.jsx's docstring on why this isn't Instagram-sourced
  visitedCities: [],
  city: null,
};

// Merged, not `loadState() || DEFAULT_STATE`: a device with progress saved
// before a field like favoriteChefs existed would otherwise resume with
// that key simply missing (not even undefined-via-default), which crashed
// FavoriteChefs.jsx on render (`chefs.map` on undefined) — confirmed live,
// looked like the app "hanging" right after the cuisines step. Merging
// backfills any field a saved object predates, so this can't recur the
// next time a new field is added to this state shape.
const initial = { ...DEFAULT_STATE, ...(loadState() || {}) };

export default function App() {
  const [state, setState] = useState(initial);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    // Best-effort cross-device sync (see /api/prefs) — fire-and-forget, same
    // as the localStorage write above. A signed-out or auth-not-configured
    // app just gets a rejected promise here, which is fine to ignore: local
    // storage above is already the source of truth for that case.
    if (fb.configured()) {
      api.savePrefs(state).catch(() => {});
    }
  }, [state]);

  // Landing back here after /auth/spotify/callback redirects the browser
  // with the result in the query string — there's no session store yet, so
  // this is the handoff point. Runs once on mount; the URL is cleaned up
  // immediately after so a refresh doesn't re-process stale params.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const artistsRaw = params.get('spotify_artists');
    const error = params.get('spotify_error');
    if (artistsRaw) {
      let artists = [];
      try {
        artists = JSON.parse(artistsRaw);
      } catch {
        // malformed — treat like any other failure below
      }
      if (artists.length) {
        set({ tasteMethod: 'spotify', musicArtists: artists, step: 'spotify-confirm' });
      } else {
        set({ tasteMethod: 'spotify', spotifyFailed: true, step: 'genres' });
      }
      window.history.replaceState(null, '', window.location.pathname);
      return; // mid Spotify handoff — skip the cross-device fetch below, it'd race this
    } else if (error) {
      set({ tasteMethod: 'spotify', spotifyFailed: true, step: 'genres' });
      window.history.replaceState(null, '', window.location.pathname);
      return;
    }

    // Cross-device sync: pulls this account's saved preferences (see
    // /api/prefs) so a device with no local progress of its own — or one
    // that's had its site data cleared — still resumes where the account
    // left off, instead of only ever working on the one browser that set
    // it. Only overwrites state when the server actually has something
    // saved; a signed-out or auth-not-configured app just keeps whatever
    // loadState() already produced.
    if (fb.configured()) {
      api.getPrefs().then((d) => {
        if (d.prefs) set(d.prefs);
      }).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const set = (patch) => setState((s) => ({ ...s, ...patch }));

  let screen;
  switch (state.step) {
    case 'welcome':
      screen = (
        <Welcome
          onChooseSpotify={() => { window.location.href = spotifyLoginUrl; }}
          onChooseManual={() => set({ tasteMethod: 'manual', step: 'genres' })}
        />
      );
      break;

    case 'spotify-confirm':
      screen = (
        <SpotifyConfirm
          artists={state.musicArtists}
          onContinue={() => set({ step: 'cuisines' })}
          onPickManually={() => set({ tasteMethod: 'manual', musicGenres: [], step: 'genres' })}
        />
      );
      break;

    case 'genres':
      screen = (
        <MusicGenrePick
          tasteMethod={state.tasteMethod}
          selected={state.musicGenres}
          onChange={(musicGenres) => set({ musicGenres })}
          onContinue={() => state.musicGenres.length && set({ step: 'cuisines' })}
        />
      );
      break;

    case 'cuisines':
      screen = (
        <CuisinePick
          step={2}
          selected={state.cuisines}
          onChange={(cuisines) => set({ cuisines })}
          onContinue={() => state.cuisines.length && set({ step: 'chefs' })}
        />
      );
      break;

    case 'chefs':
      screen = (
        <FavoriteChefs
          step={3}
          chefs={state.favoriteChefs}
          onChange={(favoriteChefs) => set({ favoriteChefs })}
          onContinue={() => set({ step: 'visited' })}
          onSkip={() => set({ step: 'visited' })}
        />
      );
      break;

    case 'visited':
      screen = (
        <CitiesVisited
          step={4}
          visited={state.visitedCities}
          onChange={(visitedCities) => set({ visitedCities })}
          onContinue={() => set({ step: 'search' })}
          onSkip={() => set({ step: 'search' })}
        />
      );
      break;

    case 'search':
      screen = (
        <CitySearch
          step={5}
          visitedCities={state.visitedCities}
          onPickCity={(city) => set({ city, step: 'results' })}
        />
      );
      break;

    case 'results':
      // Only the manual picker's fixed-vocabulary genres bias which live-music
      // venues get found for cities with no music data of their own — Spotify's
      // artist-name signal has no genre to key off (see api/spotify.py).
      screen = <ResultsFeed city={state.city} musicGenre={state.musicGenres[0] || ''} favoriteChefs={state.favoriteChefs} cuisines={state.cuisines} />;
      break;

    default:
      screen = null;
  }

  return (
    <PhoneShell>
      {state.step !== 'welcome' && (
        <div
          onClick={() => {
            if (state.step === 'results') set({ step: 'search' });
            else if (state.step === 'search') set({ step: 'visited' });
            else if (state.step === 'visited') set({ step: 'chefs' });
            else if (state.step === 'chefs') set({ step: 'cuisines' });
            else if (state.step === 'cuisines') {
              // A successful Spotify connection shows the confirmation
              // screen instead of the genre picker — go back to whichever
              // one this taste method actually used.
              set({ step: state.tasteMethod === 'spotify' && !state.spotifyFailed ? 'spotify-confirm' : 'genres' });
            }
            else if (state.step === 'spotify-confirm') set({ step: 'welcome' });
            else if (state.step === 'genres') set({ step: 'welcome' });
          }}
          style={{ position: 'absolute', margin: '16px 0 0 16px', cursor: 'pointer', opacity: 0.5, fontSize: 13 }}
        >
          ← back
        </div>
      )}
      {screen}
    </PhoneShell>
  );
}
