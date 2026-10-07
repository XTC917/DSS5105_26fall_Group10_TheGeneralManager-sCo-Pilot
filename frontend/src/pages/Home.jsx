import { useCallback, useEffect, useState } from "react";
import Sidebar from "../components/Sidebar.jsx";
import ChatPanel from "../components/ChatPanel.jsx";
import ConversationList from "../components/ConversationList.jsx";
import DataManagement from "./DataManagement.jsx";
import UserManagement from "./UserManagement.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import { fetchHealth } from "../services/api.js";
import { deactivateMe } from "../services/authApi.js";
import { friendlyAuthError } from "../services/authErrors.js";
import {
  createConversation,
  fetchAllConversationHistory,
  listConversations,
  turnsToMessages,
} from "../services/conversationsApi.js";

export default function Home() {
  const { user, logout } = useAuth();
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [boardTick, setBoardTick] = useState(0);
  const [activeView, setActiveView] = useState("copilot");
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [deactivateBusy, setDeactivateBusy] = useState(false);
  const [deactivateError, setDeactivateError] = useState("");
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [historyMessages, setHistoryMessages] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [createBusy, setCreateBusy] = useState(false);
  const [chatBusy, setChatBusy] = useState(false);
  const [historyRetry, setHistoryRetry] = useState(0);

  const refreshConversations = useCallback(async () => {
    const items = await listConversations();
    setConversations(items);
    return items;
  }, []);

  const openConversation = useCallback(async (id) => {
    const history = await fetchAllConversationHistory(id);
    setConversationId(id);
    setHistoryMessages(turnsToMessages(history.turns));
  }, []);

  const isAdmin = user?.role === "ADMIN";

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err) => setHealthError(err.message));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setHistoryLoading(true);
    setHistoryError("");
    listConversations()
      .then(async (items) => {
        if (cancelled) return;
        setConversations(items);
        if (items.length === 0) {
          const created = await createConversation();
          if (cancelled) return;
          setConversations([created]);
          setConversationId(created.id);
          setHistoryMessages([]);
        } else {
          const history = await fetchAllConversationHistory(items[0].id);
          if (cancelled) return;
          setConversationId(items[0].id);
          setHistoryMessages(turnsToMessages(history.turns));
        }
      })
      .catch((err) => {
        if (!cancelled) setHistoryError(err.message);
      })
      .finally(() => {
        if (!cancelled) setHistoryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user.id, historyRetry]);

  async function handleCreateConversation() {
    if (chatBusy || historyLoading || createBusy) return;
    setCreateBusy(true);
    setHistoryLoading(true);
    setHistoryError("");
    try {
      const created = await createConversation();
      setConversations((prev) => [created, ...prev]);
      setConversationId(created.id);
      setHistoryMessages([]);
    } catch (err) {
      setHistoryError(err.message);
    } finally {
      setCreateBusy(false);
      setHistoryLoading(false);
    }
  }

  async function handleSelectConversation(id) {
    if (id === conversationId || chatBusy || historyLoading || createBusy) return;
    setHistoryError("");
    setHistoryLoading(true);
    try {
      await openConversation(id);
    } catch (err) {
      setHistoryError(err.message);
    } finally {
      setHistoryLoading(false);
    }
  }

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
          {activeView === "copilot" && (
            <ConversationList
              conversations={conversations}
              activeConversationId={conversationId}
              loading={historyLoading}
              createBusy={createBusy}
              error={historyError}
              onSelect={handleSelectConversation}
              onCreate={handleCreateConversation}
              interactionDisabled={chatBusy}
              onRetry={() => setHistoryRetry((n) => n + 1)}
            />
          )}
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
          historyLoading ? (
            <p role="status" className="p-4 text-sm text-ink/60">Loading conversation history…</p>
          ) : conversationId && (
            <ChatPanel
              key={conversationId}
              conversationId={conversationId}
              llmReady={Boolean(health?.llm_configured)}
              onBoardChanged={() => setBoardTick((n) => n + 1)}
              onConversationUpdated={() => refreshConversations().catch(() => {})}
              onBusyChange={setChatBusy}
              initialMessages={historyMessages}
              onMessagesChange={setHistoryMessages}
            />
          )
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
