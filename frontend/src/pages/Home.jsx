import { useEffect, useMemo, useState } from "react";
import Sidebar from "../components/Sidebar.jsx";
import ChatPanel from "../components/ChatPanel.jsx";
import DataManagement from "./DataManagement.jsx";
import UserManagement from "./UserManagement.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import { fetchHealth } from "../services/api.js";
import { deactivateMe } from "../services/authApi.js";
import { friendlyAuthError } from "../services/authErrors.js";

function newConversationId() {
  return `gm-${Date.now()}`;
}

export default function Home() {
  const { user, logout } = useAuth();
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [boardTick, setBoardTick] = useState(0);
  const [activeView, setActiveView] = useState("copilot");
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [deactivateBusy, setDeactivateBusy] = useState(false);
  const [deactivateError, setDeactivateError] = useState("");
  const conversationId = useMemo(newConversationId, []);

  const isAdmin = user?.role === "ADMIN";

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err) => setHealthError(err.message));
  }, []);

  // Route protection: only ADMIN may view data/users; EMPLOYEE is bounced back.
  useEffect(() => {
    if (!isAdmin && (activeView === "data" || activeView === "users")) {
      setActiveView("copilot");
    }
  }, [isAdmin, activeView]);

  async function handleDeactivate() {
    setDeactivateBusy(true);
    setDeactivateError("");
    try {
      await deactivateMe();
      logout();
    } catch (err) {
      setDeactivateError(friendlyAuthError(err, "Deactivation failed. Please try again."));
    } finally {
      setDeactivateBusy(false);
    }
  }

  const navButton = (key, label) => (
    <button
      key={key}
      type="button"
      onClick={() => setActiveView(key)}
      className={`block w-full rounded-md px-3 py-2 text-left text-sm font-medium ${
        activeView === key ? "bg-ink text-paper" : "text-ink/70 hover:bg-paper"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-ink/10 bg-ink text-paper">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-brass">
              SweaterCo · Track 1
            </p>
            <h1 className="text-lg font-semibold">General Manager&apos;s Co-Pilot</h1>
          </div>
          <div className="flex items-center gap-4 text-right text-xs text-paper/70">
            <div>
              <p>Factory date: 1 Apr 2026</p>
              <p>
                {user && (
                  <span>
                    {user.username} · {user.role}
                  </span>
                )}
              </p>
              <p>
                {healthError && <span className="text-red-300">API offline — {healthError}</span>}
                {!healthError && health && (
                  <span>
                    API {health.ok ? "ready" : "down"}
                    {health.llm_configured ? "" : " · set GOOGLE_API_KEY (gemini) or OPENAI_API_KEY for chat"}
                  </span>
                )}
              </p>
            </div>
            <button
              type="button"
              onClick={logout}
              className="rounded-md border border-paper/30 px-3 py-1.5 text-xs font-medium text-paper hover:border-brass"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-5 px-5 py-5 lg:grid-cols-[260px_1fr]">
        <div className="space-y-3">
          <nav className="rounded-lg border border-ink/10 bg-white p-2 shadow-sm">
            {navButton("copilot", "GM Co-Pilot")}
            {isAdmin && (
              <div className="mt-1">
                {navButton("data", "Data Management")}
              </div>
            )}
            {isAdmin && (
              <div className="mt-1">
                {navButton("users", "User Management")}
              </div>
            )}
          </nav>
          {activeView === "copilot" && <Sidebar refreshToken={boardTick} />}
          <div className="rounded-lg border border-ink/10 bg-white p-3 shadow-sm">
            <p className="text-xs font-medium text-ink/70">Account</p>
            {confirmDeactivate ? (
              <div className="mt-2">
                <p className="text-xs text-ink/70">Deactivate your own account? This cannot be undone here.</p>
                {deactivateError && <p className="mt-1 text-xs text-red-600">{deactivateError}</p>}
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    disabled={deactivateBusy}
                    onClick={handleDeactivate}
                    className="rounded-md bg-red-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
                  >
                    {deactivateBusy ? "Deactivating…" : "Confirm deactivate"}
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setConfirmDeactivate(false);
                      setDeactivateError("");
                    }}
                    className="rounded-md border border-ink/15 px-3 py-1.5 text-xs text-ink/70"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmDeactivate(true)}
                className="mt-2 w-full rounded-md border border-ink/15 px-3 py-1.5 text-left text-xs text-ink/70 hover:border-red-400 hover:text-red-600"
              >
                Deactivate my account
              </button>
            )}
          </div>
        </div>
        {activeView === "copilot" ? (
          <ChatPanel
            conversationId={conversationId}
            llmReady={Boolean(health?.llm_configured)}
            onBoardChanged={() => setBoardTick((n) => n + 1)}
          />
        ) : activeView === "data" && isAdmin ? (
          <DataManagement />
        ) : activeView === "users" && isAdmin ? (
          <UserManagement />
        ) : (
          <ChatPanel
            conversationId={conversationId}
            llmReady={Boolean(health?.llm_configured)}
            onBoardChanged={() => setBoardTick((n) => n + 1)}
          />
        )}
      </main>
    </div>
  );
}
