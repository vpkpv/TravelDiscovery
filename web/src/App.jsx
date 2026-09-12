import { useEffect, useState } from 'react';
import { PhoneShell } from './components/PhoneShell.jsx';
import { Welcome } from './screens/Welcome.jsx';
import { MusicGenrePick } from './screens/MusicGenrePick.jsx';
import { CuisinePick } from './screens/CuisinePick.jsx';
import { CitiesVisited } from './screens/CitiesVisited.jsx';
import { CitySearch } from './screens/CitySearch.jsx';
import { ResultsFeed } from './screens/ResultsFeed.jsx';
import { spotifyLoginUrl } from './api.js';

const STORAGE_KEY = 'traveldiscovery.onboarding.v1';

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const initial = loadState() || {
  step: 'welcome', // welcome -> genres (manual, or Spotify-failure fallback) -> cuisines -> visited -> search -> results
  tasteMethod: null, // 'spotify' | 'manual'
  musicGenres: [], // manual path's fixed-vocabulary picks
  musicArtists: [], // Spotify path's top artist names — a freeform signal, not genre-bucketed (see api/spotify.py)
  spotifyFailed: false,
  cuisines: [],
  visitedCities: [],
  city: null,
};

export default function App() {
  const [state, setState] = useState(initial);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
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
        set({ tasteMethod: 'spotify', musicArtists: artists, step: 'cuisines' });
      } else {
        set({ tasteMethod: 'spotify', spotifyFailed: true, step: 'genres' });
      }
      window.history.replaceState(null, '', window.location.pathname);
    } else if (error) {
      set({ tasteMethod: 'spotify', spotifyFailed: true, step: 'genres' });
      window.history.replaceState(null, '', window.location.pathname);
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
          onContinue={() => state.cuisines.length && set({ step: 'visited' })}
        />
      );
      break;

    case 'visited':
      screen = (
        <CitiesVisited
          step={3}
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
          step={4}
          visitedCities={state.visitedCities}
          onPickCity={(city) => set({ city, step: 'results' })}
        />
      );
      break;

    case 'results':
      screen = <ResultsFeed city={state.city} />;
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
            else if (state.step === 'visited') set({ step: 'cuisines' });
            else if (state.step === 'cuisines') {
              // A successful Spotify connection skips the genre-picker step
              // entirely (musicArtists comes straight from the OAuth
              // callback) — there's nothing to go back to there, so return
              // to the taste-method choice instead.
              set({ step: state.tasteMethod === 'spotify' && !state.spotifyFailed ? 'welcome' : 'genres' });
            }
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
