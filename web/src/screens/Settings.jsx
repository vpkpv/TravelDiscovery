import { useEffect, useState } from 'react';
import { theme } from '../theme.js';
import { api, spotifyLoginUrl } from '../api.js';
import { Chip } from '../components/Chip.jsx';

// Edits the same onboarding state App.jsx already persists (localStorage +
// /api/prefs) — there's no separate "settings" storage, this just gives
// direct access to fields that were previously only ever set once during
// onboarding and never revisitable, despite Welcome.jsx's copy claiming
// "you can switch methods later in Settings" (aspirational until now).
export function Settings({ state, onChange, onDone }) {
  const [cuisineOptions, setCuisineOptions] = useState([]);
  const [genreOptions, setGenreOptions] = useState([]);
  const [chefDraft, setChefDraft] = useState('');
  const [mcpToken, setMcpToken] = useState('');
  const [mintingToken, setMintingToken] = useState(false);
  const [tokenError, setTokenError] = useState('');

  useEffect(() => {
    api.cuisines().then((d) => setCuisineOptions(d.cuisines));
    api.musicGenres().then((d) => setGenreOptions(d.genres));
  }, []);

  // Lets an external MCP client (Claude, or an agent like Muse that can
  // build its own connector from a URL + token — see api/mcp_server.py)
  // authenticate as this account, without needing to dig a Firebase ID
  // token out of browser devtools by hand. Shown once; there's no way to
  // retrieve the same token again afterward (see /api/tokens' docstring),
  // only mint a new one.
  const mintToken = async () => {
    setMintingToken(true);
    setTokenError('');
    try {
      const { token } = await api.createToken();
      setMcpToken(token);
    } catch {
      setTokenError("Couldn't generate a token — check your connection and try again.");
    } finally {
      setMintingToken(false);
    }
  };

  const toggleCuisine = (c) => {
    onChange({ cuisines: state.cuisines.includes(c) ? state.cuisines.filter((x) => x !== c) : [...state.cuisines, c] });
  };
  const toggleGenre = (g) => {
    onChange({ musicGenres: state.musicGenres.includes(g) ? state.musicGenres.filter((x) => x !== g) : [...state.musicGenres, g] });
  };
  const addChef = () => {
    const name = chefDraft.trim();
    if (!name || state.favoriteChefs.includes(name)) {
      setChefDraft('');
      return;
    }
    onChange({ favoriteChefs: [...state.favoriteChefs, name] });
    setChefDraft('');
  };
  const removeChef = (name) => onChange({ favoriteChefs: state.favoriteChefs.filter((c) => c !== name) });
  const switchToManualGenres = () => onChange({ tasteMethod: 'manual', musicArtists: [], spotifyFailed: false });

  const sectionLabelStyle = { fontSize: 13, letterSpacing: '0.06em', color: theme.textFaint, textTransform: 'uppercase', margin: '28px 0 10px' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1 }}>
      <div style={{ padding: '48px 24px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ fontFamily: theme.fontDisplay, fontWeight: 600, fontSize: 28 }}>Your taste</div>
        <div onClick={onDone} style={{ cursor: 'pointer', fontSize: 14, fontWeight: 600, color: theme.text }}>Done</div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '0 24px 32px' }}>
        <div style={{ ...sectionLabelStyle, marginTop: 20 }}>Cuisines</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {cuisineOptions.map((c) => (
            <Chip key={c} label={c} selected={state.cuisines.includes(c)} onClick={() => toggleCuisine(c)} />
          ))}
        </div>

        <div style={sectionLabelStyle}>Chefs, foodie accounts & restaurants you love</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: theme.card, border: `1px solid ${theme.border}`, borderRadius: 16, padding: '12px 16px' }}>
          <input
            value={chefDraft}
            onChange={(e) => setChefDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addChef();
              }
            }}
            placeholder="e.g. Gordon Ramsay, or a restaurant you love"
            style={{ border: 'none', background: 'transparent', fontSize: 15, color: theme.text, flex: 1, outline: 'none' }}
          />
          <div onClick={addChef} style={{ cursor: 'pointer', color: theme.accentFood, fontWeight: 600, fontSize: 14 }}>
            Add
          </div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 12 }}>
          {state.favoriteChefs.length === 0 && (
            <div style={{ fontSize: 13.5, color: theme.textFaint }}>None added yet.</div>
          )}
          {state.favoriteChefs.map((c) => (
            <div key={c} style={{ display: 'flex', alignItems: 'center', gap: 8, background: theme.chipBg, borderRadius: 16, padding: '8px 14px', fontSize: 14 }}>
              {c}
              <span onClick={() => removeChef(c)} style={{ cursor: 'pointer', color: theme.textFaint, fontWeight: 700, lineHeight: 1 }}>
                ×
              </span>
            </div>
          ))}
        </div>

        <div style={sectionLabelStyle}>Music taste</div>
        {state.tasteMethod === 'spotify' ? (
          <div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
              {state.musicArtists.map((a) => (
                <span key={a} style={{ background: theme.chipBg, borderRadius: 14, padding: '6px 12px', fontSize: 13 }}>{a}</span>
              ))}
            </div>
            <div style={{ display: 'flex', gap: 18, marginTop: 14 }}>
              <div onClick={() => { window.location.href = spotifyLoginUrl; }} style={{ cursor: 'pointer', fontSize: 13.5, color: theme.accentMusic, fontWeight: 600 }}>
                Reconnect Spotify
              </div>
              <div onClick={switchToManualGenres} style={{ cursor: 'pointer', fontSize: 13.5, color: theme.textFaint, textDecoration: 'underline' }}>
                Switch to picking genres
              </div>
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {genreOptions.map((g) => (
              <Chip key={g} label={g} selected={state.musicGenres.includes(g)} onClick={() => toggleGenre(g)} />
            ))}
          </div>
        )}

        <div style={sectionLabelStyle}>Developer: MCP access</div>
        <div style={{ fontSize: 13.5, color: theme.textMuted, lineHeight: 1.5 }}>
          Generates a personal access token so an MCP-compatible client (Claude, or an
          agent that can connect to an MCP server URL) can read your picks on your behalf.
        </div>
        {mcpToken ? (
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 13, color: theme.accentFood, fontWeight: 600, marginBottom: 6 }}>
              Copy this now — it won't be shown again:
            </div>
            <div
              style={{
                background: theme.chipBg, borderRadius: 12, padding: '10px 14px',
                fontFamily: 'monospace', fontSize: 12.5, wordBreak: 'break-all', userSelect: 'all',
              }}
            >
              {mcpToken}
            </div>
          </div>
        ) : (
          <div
            onClick={mintingToken ? undefined : mintToken}
            style={{
              marginTop: 12, display: 'inline-flex', cursor: mintingToken ? 'default' : 'pointer',
              border: `1.5px solid ${theme.border}`, borderRadius: 16, padding: '10px 18px',
              fontSize: 14, fontWeight: 600, color: theme.text, opacity: mintingToken ? 0.6 : 1,
            }}
          >
            {mintingToken ? 'Generating…' : 'Generate access token'}
          </div>
        )}
        {tokenError && <div style={{ fontSize: 13, color: theme.accentFood, marginTop: 8 }}>{tokenError}</div>}
      </div>
    </div>
  );
}
