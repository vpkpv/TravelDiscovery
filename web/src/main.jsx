import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import { AuthGate } from './AuthGate.jsx';
import { SharedTrip } from './screens/SharedTrip.jsx';
import './global.css';

// A shared trip link (see ResultsFeed.jsx's "Share this trip") has to be
// openable by someone with no TravelDiscovery account at all, so this one
// route is checked before AuthGate even mounts — there's no router in this
// app otherwise (every other screen is plain in-memory state in App.jsx),
// so a plain pathname check here is the whole "routing" this needs.
const sharedTripMatch = window.location.pathname.match(/^\/trip\/shared\/([^/]+)/);

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {sharedTripMatch ? (
      <SharedTrip token={sharedTripMatch[1]} />
    ) : (
      <AuthGate>
        <App />
      </AuthGate>
    )}
  </React.StrictMode>,
);
