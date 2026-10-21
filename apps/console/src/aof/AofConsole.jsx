'use client';

import { useState } from 'react';

import { fetchAgents, fetchDevUsers, setCurrentUser, currentUser } from './api';
import AgentView from './AgentView';
import { Empty, ErrorNote, Loading } from './ui';
import { useAsync } from './useAsync';

/** The generic Agent One Finance shell: who you are, the agents you may use, and the selected one. */
export default function AofConsole() {
  const [user, setUser] = useState(() => currentUser());
  const [selectedId, setSelectedId] = useState(null);
  const users = useAsync(fetchDevUsers, []);
  const agents = useAsync(() => (user ? fetchAgents() : Promise.resolve([])), [user]);

  const switchUser = (id) => {
    setCurrentUser(id);
    setUser(id);
    setSelectedId(null);
  };
  const list = agents.data ?? [];
  const selected = list.find((c) => c.id === selectedId) ?? list[0];

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="flex flex-wrap items-center justify-between gap-3 bg-[#0b2a5b] px-6 py-3 text-white">
        <div>
          <h1 className="text-lg font-semibold">Agent One Finance</h1>
          <p className="text-xs text-blue-100">Agents onboarded as configuration</p>
        </div>
        {users.data?.length > 0 && (
          <label className="flex items-center gap-2 text-sm">
            Signed in as
            <select
              aria-label="Signed-in user"
              className="rounded bg-white px-2 py-1 text-gray-900"
              value={user ?? ''}
              onChange={(e) => switchUser(e.target.value)}
            >
              <option value="" disabled>
                Choose a user
              </option>
              {users.data.map((u) => (
                <option key={u.user_id} value={u.user_id}>
                  {u.name ?? u.user_id}
                </option>
              ))}
            </select>
          </label>
        )}
      </header>

      <div className="flex flex-col gap-4 p-4 md:flex-row">
        <nav aria-label="Agents" className="md:w-64 md:shrink-0">
          {!user && <Empty>Choose a user to see their agents.</Empty>}
          {user && agents.loading && <Loading what="agents" />}
          {user && agents.error && <ErrorNote error={agents.error} />}
          {user && !agents.loading && !agents.error && list.length === 0 && (
            <Empty>No agents for this user's roles.</Empty>
          )}
          <ul className="space-y-1">
            {list.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(c.id)}
                  aria-current={selected?.id === c.id ? 'page' : undefined}
                  className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                    selected?.id === c.id ? 'bg-white shadow-sm ring-1 ring-gray-200' : 'hover:bg-white'
                  }`}
                >
                  <span className="block font-medium">{c.name}</span>
                  <span className="block text-xs text-gray-500">
                    {c.id} · v{c.version}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <main className="min-w-0 flex-1">
          {selected && <AgentView key={`${user}:${selected.id}`} agent={selected} />}
        </main>
      </div>
    </div>
  );
}
