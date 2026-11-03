import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import { AuthGate } from './AuthGate.jsx';
import { SharedTrip } from './screens/SharedTrip.jsx';
import { Admin } from './screens/Admin.jsx';
import './global.css';

// A shared trip link (see ResultsFeed.jsx's "Share this trip") has to be
// openable by someone with no TravelDiscovery account at all, so this one
// route is checked before AuthGate even mounts — there's no router in this
// app otherwise (every other screen is plain in-memory state in App.jsx),
// so a plain pathname check here is the whole "routing" this needs.
const sharedTripMatch = window.location.pathname.match(/^\/trip\/shared\/([^/]+)/);

// /admin (the approval page — see api/auth.py's require_admin) still
// needs a real sign-in, unlike the shared-trip route above, so this one
// renders inside AuthGate rather than instead of it: Admin.jsx just
// replaces App.jsx as AuthGate's child once a session makes it through
// the normal signed-in-and-approved gate. Being ADMIN_EMAILS-gated too is
// enforced server-side on every /api/admin/* call, not here — a signed-in
// non-admin hitting this path just sees Admin.jsx's own 403 state.
const isAdminRoute = window.location.pathname === '/admin';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    {sharedTripMatch ? (
      <SharedTrip token={sharedTripMatch[1]} />
    ) : (
      <AuthGate>
        {isAdminRoute ? <Admin /> : <App />}
      </AuthGate>
    )}
  </React.StrictMode>,
);
