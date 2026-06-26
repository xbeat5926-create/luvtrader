import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

const API_URL = import.meta.env.VITE_API_URL || '/_/backend/api';

const demoUsers = [
  { role: 'Admin', email: 'admin@luvtrader.com' },
  { role: 'Operations', email: 'ops@luvtrader.com' },
  { role: 'Client', email: 'client@example.com' },
];

const cards = [
  { label: 'Active boards', value: '12', detail: 'Operations-ready clients' },
  { label: 'Sold this month', value: '$4,850', detail: 'Running sold total' },
  { label: 'Open flags', value: '3', detail: 'Needs owner review' },
  { label: 'Messages', value: '18', detail: 'Previewed or sent' },
];

const clients = [
  { name: 'Maya Johnson', status: 'active', base: 'DAL', balance: '$350 due' },
  { name: 'Chris Rivera', status: 'single month', base: 'PHX', balance: '$125 credit' },
  { name: 'Taylor Smith', status: 'TAP', base: 'HOU', balance: '$0' },
  { name: 'Jordan Lee', status: 'TAP retainer', base: 'LAS', balance: '$75 due' },
  { name: 'Avery Brooks', status: 'paused', base: 'DEN', balance: '$0' },
];

function App() {
  const [role, setRole] = useState('Admin');
  const visibleClients = useMemo(() => {
    if (role === 'Operations') {
      return clients.filter((client) => ['active', 'single month'].includes(client.status));
    }
    if (role === 'Client') {
      return clients.slice(0, 1);
    }
    return clients;
  }, [role]);

  return (
    <main className="app-shell">
      <section className="hero-card">
        <div>
          <p className="eyebrow">clients.luvtrader.com</p>
          <h1>LUVTrader</h1>
          <p className="tagline">A Clear Board Is a Happy Board</p>
        </div>
        <div className="login-card">
          <label htmlFor="role">Preview portal role</label>
          <select id="role" value={role} onChange={(event) => setRole(event.target.value)}>
            {demoUsers.map((user) => (
              <option key={user.role}>{user.role}</option>
            ))}
          </select>
          <small>Demo password for seeded users: password123</small>
        </div>
      </section>

      <section className="grid cards-grid">
        {cards.map((card) => (
          <article className="metric-card" key={card.label}>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
            <p>{card.detail}</p>
          </article>
        ))}
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <p className="eyebrow">{role} view</p>
            <h2>{role === 'Client' ? 'My Board' : 'Client boards'}</h2>
          </div>
          <span className="api-pill">API: {API_URL}</span>
        </div>
        <div className="client-list">
          {visibleClients.map((client) => (
            <article className="client-row" key={client.name}>
              <div>
                <strong>{client.name}</strong>
                <p>{client.base} base · {client.balance}</p>
              </div>
              <span className={`status status-${client.status.replace(' ', '-')}`}>{client.status}</span>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
