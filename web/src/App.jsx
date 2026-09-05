import { useEffect, useState } from 'react';
import { PhoneShell } from './components/PhoneShell.jsx';
import { Welcome } from './screens/Welcome.jsx';
import { MusicGenrePick } from './screens/MusicGenrePick.jsx';
import { CuisinePick } from './screens/CuisinePick.jsx';
import { CitiesVisited } from './screens/CitiesVisited.jsx';
import { CitySearch } from './screens/CitySearch.jsx';
import { ResultsFeed } from './screens/ResultsFeed.jsx';

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
  step: 'welcome', // welcome -> genres (manual only) -> cuisines -> visited -> search -> results
  tasteMethod: null, // 'spotify' | 'manual'
  musicGenres: [],
  cuisines: [],
  visitedCities: [],
  city: null,
};

export default function App() {
  const [state, setState] = useState(initial);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }, [state]);

  const set = (patch) => setState((s) => ({ ...s, ...patch }));

  let screen;
  switch (state.step) {
    case 'welcome':
      screen = (
        <Welcome
          // Real Spotify OAuth isn't wired yet (tracked separately) — route
          // through the same genre picker as the manual path rather than
          // silently skipping music-taste capture and landing on the food
          // question with no music step ever shown.
          onChooseSpotify={() => set({ tasteMethod: 'spotify', step: 'genres' })}
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
            else if (state.step === 'cuisines') set({ step: 'genres' });
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
