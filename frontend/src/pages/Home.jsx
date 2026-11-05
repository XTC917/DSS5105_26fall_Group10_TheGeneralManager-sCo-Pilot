import { useCallback, useEffect, useRef, useState } from "react";
import MorningBriefingModal from "../components/MorningBriefingModal.jsx";
import Sidebar from "../components/Sidebar.jsx";
import ChatPanel from "../components/ChatPanel.jsx";
import ConversationList from "../components/ConversationList.jsx";
import DataManagement from "./DataManagement.jsx";
import UserManagement from "./UserManagement.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import { fetchHealth } from "../services/api.js";
import { deactivateMe } from "../services/authApi.js";
import {
  createConversation,
  fetchConversationHistory,
  fetchConversations,
} from "../services/conversationsApi.js";
import { friendlyAuthError } from "../services/authErrors.js";
import {
  Button,
  Card,
  LoadingState,
  Modal,
  ThemeSwitcher,
} from "../components/ui/index.js";

function storageKey(userId) {
  return `sweaterco:last-conversation:${userId}`;
}

function messagesFromTurns(turns) {
  return turns.flatMap((turn) => {
    const metadata = turn.response_json || {};
    return [
      { role: "user", content: turn.question },
      {
        role: "assistant",
        content: turn.answer,
        toolsUsed: metadata.tools_used || [],
        traces: metadata.traces || [],
        limitation: metadata.limitation || null,
        proposedActions: metadata.proposed_actions || [],
        emailDrafts: metadata.email_drafts || [],
        turnId: turn.id,
        charts: metadata.charts || [],
        tables: metadata.tables || [],
        clarification: metadata.clarification || null,
        why: metadata.why || null,
        decision: metadata.decision || null,
      },
    ];
  });
}

function IconChat() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M5 6.5A2.5 2.5 0 0 1 7.5 4h9A2.5 2.5 0 0 1 19 6.5v6A2.5 2.5 0 0 1 16.5 15H11l-4 3.5V15H7.5A2.5 2.5 0 0 1 5 12.5v-6z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
    </svg>
  );
}

function IconOverview() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="3" y="3" width="8" height="8" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <rect x="13" y="3" width="8" height="5" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <rect x="13" y="10" width="8" height="11" rx="2" stroke="currentColor" strokeWidth="1.8" />
      <rect x="3" y="13" width="8" height="8" rx="2" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function IconDatabase() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <ellipse cx="12" cy="6" rx="7" ry="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

function IconUsers() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="9" cy="8" r="3" stroke="currentColor" strokeWidth="1.8" />
      <path d="M3 19c0-3 2.7-5 6-5s6 2 6 5M16 5a3 3 0 1 1 0 6M21 19c0-2.5-2-4.5-5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconSettings() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" stroke="currentColor" strokeWidth="1.8" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

function IconTheme() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8" />
      <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

function IconLogout() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 16l4-4-4-4M19 12H9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

const VIEW_META = {
  copilot: {
    eyebrow: "AI Workspace",
    title: "GM Co-Pilot",
    subtitle: "Ask grounded questions about orders, risk and new-order feasibility.",
  },
  overview: {
    eyebrow: "Insights",
    title: "Overview",
    subtitle: "Morning briefing, discovery issues, alerts, watches and audit trail.",
  },
  data: {
    eyebrow: "Administration",
    title: "Data Management",
    subtitle: "Upload, inspect and query factory datasets.",
  },
  users: {
    eyebrow: "Administration",
    title: "User Management",
    subtitle: "Approve, disable and review user accounts.",
  },
  settings: {
    eyebrow: "Account",
    title: "Settings",
    subtitle: "Appearance, account information and session controls.",
  },
};

export default function Home() {
  const { user, logout } = useAuth();
  const [briefingOpen, setBriefingOpen] = useState(false);
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [boardTick, setBoardTick] = useState(0);
  const [activeView, setActiveView] = useState("copilot");
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [deactivateBusy, setDeactivateBusy] = useState(false);
  const [deactivateError, setDeactivateError] = useState("");
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [initialMessages, setInitialMessages] = useState([]);
  const [conversationLoading, setConversationLoading] = useState(true);
  const [conversationError, setConversationError] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const historyRequest = useRef(0);

  const isAdmin = user?.role === "ADMIN";

  useEffect(() => {
    fetchHealth()
      .then(setHealth)
      .catch((err) => setHealthError(err.message));
  }, []);

  useEffect(() => {
    if (!isAdmin && (activeView === "data" || activeView === "users")) {
      setActiveView("copilot");
    }
  }, [isAdmin, activeView]);

  const refreshConversationList = useCallback(async () => {
    const rows = await fetchConversations();
    setConversations(rows);
    return rows;
  }, []);

  const openConversation = useCallback(
    async (conversationId) => {
      if (!user?.id || !conversationId) return;
      const requestId = ++historyRequest.current;
      setConversationLoading(true);
      setConversationError("");
      try {
        const history = await fetchConversationHistory(conversationId);
        if (requestId !== historyRequest.current) return;
        setActiveConversationId(history.conversation.id);
        setInitialMessages(messagesFromTurns(history.turns));
        localStorage.setItem(storageKey(user.id), history.conversation.id);
        setActiveView("copilot");
        setHistoryDrawerOpen(false);
      } catch (err) {
        if (requestId === historyRequest.current) setConversationError(err.message);
      } finally {
        if (requestId === historyRequest.current) setConversationLoading(false);
      }
    },
    [user?.id],
  );

  useEffect(() => {
    let cancelled = false;
    historyRequest.current += 1;
    setConversations([]);
    setActiveConversationId(null);
    setInitialMessages([]);
    setConversationError("");
    setConversationLoading(true);

    async function restoreConversations() {
      if (!user?.id) return;
      try {
        let rows = await fetchConversations();
        if (cancelled) return;
        if (rows.length === 0) {
          const created = await createConversation();
          rows = [created];
        }
        if (cancelled) return;
        setConversations(rows);
        const remembered = localStorage.getItem(storageKey(user.id));
        const selected = rows.some((item) => item.id === remembered) ? remembered : rows[0].id;
        await openConversation(selected);
      } catch (err) {
        if (!cancelled) {
          setConversationError(err.message);
          setConversationLoading(false);
        }
      }
    }

    restoreConversations();
    return () => {
      cancelled = true;
      historyRequest.current += 1;
    };
  }, [openConversation, user?.id]);

  async function handleNewConversation() {
    if (chatBusy) return;
    setConversationError("");
    try {
      const created = await createConversation();
      setConversations((current) => [created, ...current]);
      await openConversation(created.id);
    } catch (err) {
      setConversationError(err.message);
    }
  }

  async function handleConversationUpdated() {
    try {
      await refreshConversationList();
    } catch (err) {
      setConversationError(err.message);
    }
  }

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

  function handleNav(key) {
    setActiveView(key);
  }

  const navItems = [
    { key: "copilot", label: "Ask AI", icon: <IconChat /> },
    { key: "overview", label: "Overview / Insights", icon: <IconOverview /> },
    ...(isAdmin ? [{ key: "data", label: "Data Management", icon: <IconDatabase /> }] : []),
    ...(isAdmin ? [{ key: "users", label: "User Management", icon: <IconUsers /> }] : []),
    { key: "settings", label: "Settings", icon: <IconSettings /> },
  ];

  const navButton = (item) => {
    const active = activeView === item.key;
    return (
      <button
        key={item.key}
        type="button"
        onClick={() => handleNav(item.key)}
        className={`focus-ring flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-left type-sm font-medium transition-colors duration-[var(--dur-fast)] ${
          active
            ? "bg-accent text-accentContrast shadow-xs"
            : "text-muted hover:bg-accentSoft/50 hover:text-foreground"
        }`}
      >
        <span className={active ? "text-accentContrast" : "text-muted"}>{item.icon}</span>
        <span>{item.label}</span>
      </button>
    );
  };

  const viewMeta = VIEW_META[activeView] || VIEW_META.copilot;

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-canvas text-foreground">
      <header className="flex h-12 shrink-0 items-center justify-between gap-3 border-b border-line bg-canvas/85 px-3 backdrop-blur-md md:h-14 md:px-6">
        <div className="flex min-w-0 items-center gap-2.5 md:gap-3">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-control bg-accent text-accentContrast shadow-xs md:h-9 md:w-9">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M4 7.5A3.5 3.5 0 0 1 7.5 4h9A3.5 3.5 0 0 1 20 7.5v5A3.5 3.5 0 0 1 16.5 16H11l-4.5 4v-4H7.5A3.5 3.5 0 0 1 4 12.5v-5z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            </svg>
          </span>
          <div className="min-w-0">
            <p className="hidden type-overline text-accentText sm:block">SweaterCo · Track 1</p>
            <h1 className="truncate text-[15px] font-semibold leading-tight text-foreground md:type-h3">General Manager&apos;s Co-Pilot</h1>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <div className="hidden items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5 md:flex">
            <span
              className={`h-2 w-2 rounded-full ${
                healthError ? "bg-danger" : health?.ok ? "bg-success" : "bg-muted"
              }`}
            />
            <span className="type-caption text-muted">
              {healthError ? "API offline" : health ? `API ${health.ok ? "ready" : "down"}` : "Checking API…"}
            </span>
          </div>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-72 shrink-0 flex-col border-r border-line bg-surface/60 md:flex">
          <nav className="shrink-0 space-y-1 p-3">
            {navItems.map(navButton)}
          </nav>

          <div className="flex shrink-0 items-center justify-between gap-2 border-t border-line px-3 py-2">
            <p className="type-overline text-muted">Conversations</p>
            <button
              type="button"
              disabled={chatBusy || conversationLoading}
              onClick={handleNewConversation}
              className="focus-ring rounded-control border border-line px-2 py-1 type-caption font-medium text-foreground transition-colors hover:border-accentText hover:text-accentText disabled:opacity-50"
            >
              New
            </button>
          </div>

          <div id="conversation-history" className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
            <ConversationList
              conversations={conversations}
              activeConversationId={activeConversationId}
              loading={conversationLoading && conversations.length === 0}
              disabled={chatBusy || conversationLoading}
              onCreate={handleNewConversation}
              onSelect={openConversation}
            />
            {conversationError && (
              <p className="mt-2 rounded-card border border-danger/30 bg-dangerSoft px-3 py-2 type-sm text-danger">
                {conversationError}
              </p>
            )}
          </div>
        </aside>

        <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {activeView === "copilot" && (
            <>
              {activeConversationId ? (
                <div className="min-h-0 flex-1 overflow-hidden">
                  <ChatPanel
                    key={activeConversationId}
                    conversationId={activeConversationId}
                    initialMessages={initialMessages}
                    llmReady={Boolean(health?.llm_configured)}
                    onBusyChange={setChatBusy}
                    onConversationUpdated={handleConversationUpdated}
                    onBoardChanged={() => setBoardTick((n) => n + 1)}
                    onOpenConversations={() => setHistoryDrawerOpen(true)}
                    onNewConversation={handleNewConversation}
                  />
                </div>
              ) : (
                <div className="flex min-h-0 flex-1 items-center justify-center p-4">
                  <Card>
                    <LoadingState
                      label={
                        conversationLoading
                          ? "Loading conversation history…"
                          : "Conversation history is unavailable."
                      }
                    />
                  </Card>
                </div>
              )}
            </>
          )}

          {activeView === "overview" && (
            <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
              <div className="mx-auto max-w-5xl space-y-4">
                <div className="mb-2">
                  <p className="type-overline text-accentText">{viewMeta.eyebrow}</p>
                  <h2 className="type-h2 text-foreground">{viewMeta.title}</h2>
                  <p className="type-sm text-muted">{viewMeta.subtitle}</p>
                  <p className="mt-1 type-caption text-subtle">Factory date: 1 Apr 2026</p>
                </div>
                <Sidebar refreshToken={boardTick} onOpenBriefing={() => setBriefingOpen(true)} />
              </div>
            </div>
          )}

          {activeView === "data" && isAdmin && (
            <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
              <DataManagement />
            </div>
          )}

          {activeView === "users" && isAdmin && (
            <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
              <UserManagement />
            </div>
          )}

          {activeView === "settings" && (
            <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
              <div className="mx-auto max-w-3xl space-y-5">
                <div>
                  <p className="type-overline text-accentText">{viewMeta.eyebrow}</p>
                  <h2 className="type-h2 text-foreground">{viewMeta.title}</h2>
                  <p className="type-sm text-muted">{viewMeta.subtitle}</p>
                </div>

                <section className="rounded-card border border-line bg-surface p-5 shadow-xs">
                  <h3 className="type-h3 text-foreground">Account</h3>
                  <dl className="mt-4 grid gap-3 type-sm">
                    <div className="flex items-center justify-between gap-3 border-b border-line/60 pb-3">
                      <dt className="text-muted">Username</dt>
                      <dd className="font-medium text-foreground">{user?.username || "—"}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3 border-b border-line/60 pb-3">
                      <dt className="text-muted">Role</dt>
                      <dd className="font-medium text-foreground">{user?.role || "—"}</dd>
                    </div>
                    <div className="flex items-center justify-between gap-3 border-b border-line/60 pb-3">
                      <dt className="text-muted">Status</dt>
                      <dd className="font-medium text-foreground">{user?.status || "Active"}</dd>
                    </div>
                    {user?.email && (
                      <div className="flex items-center justify-between gap-3 pb-1">
                        <dt className="text-muted">Email</dt>
                        <dd className="font-medium text-foreground">{user.email}</dd>
                      </div>
                    )}
                  </dl>
                </section>

                <section className="rounded-card border border-line bg-surface p-5 shadow-xs">
                  <h3 className="type-h3 text-foreground">Appearance</h3>
                  <p className="mt-1 type-sm text-muted">Choose light, dark or system, and an accent colour. Settings persist across reloads.</p>
                  <div className="mt-4">
                    <ThemeSwitcher />
                  </div>
                </section>

                <section className="rounded-card border border-line bg-surface p-5 shadow-xs">
                  <h3 className="type-h3 text-foreground">Security & Session</h3>
                  <p className="mt-1 type-sm text-muted">Sign out ends the current browser session.</p>
                  <button
                    type="button"
                    onClick={logout}
                    className="focus-ring mt-4 inline-flex items-center gap-2 rounded-control border border-line bg-surface px-4 py-2 type-sm font-medium text-foreground transition-colors hover:bg-surfaceMuted"
                  >
                    <IconLogout />
                    Log out
                  </button>
                </section>

                {isAdmin && (
                  <section className="rounded-card border border-line bg-surface p-5 shadow-xs md:hidden">
                    <h3 className="type-h3 text-foreground">Administration</h3>
                    <p className="mt-1 type-sm text-muted">Open management tools for data and user accounts.</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button size="sm" variant="secondary" onClick={() => setActiveView("data")}>
                        Data Management
                      </Button>
                      <Button size="sm" variant="secondary" onClick={() => setActiveView("users")}>
                        User Management
                      </Button>
                    </div>
                  </section>
                )}

                <section className="rounded-card border border-line bg-surface p-5 shadow-xs">
                  <h3 className="type-h3 text-foreground">Account Deactivation</h3>
                  <p className="mt-1 type-sm text-muted">Deactivate your own account. This cannot be undone here.</p>
                  {confirmDeactivate ? (
                    <div className="mt-4">
                      {deactivateError && (
                        <p className="mb-2 type-caption text-danger">{deactivateError}</p>
                      )}
                      <div className="flex gap-2">
                        <Button size="sm" variant="danger" disabled={deactivateBusy} onClick={handleDeactivate}>
                          {deactivateBusy ? "Deactivating…" : "Confirm deactivate"}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => { setConfirmDeactivate(false); setDeactivateError(""); }}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setConfirmDeactivate(true)}
                      className="focus-ring mt-4 rounded-control border border-danger/40 px-4 py-2 type-sm font-medium text-danger transition-colors hover:bg-dangerSoft"
                    >
                      Deactivate my account
                    </button>
                  )}
                </section>
              </div>
            </div>
          )}
        </main>
      </div>

      <nav
        className="flex shrink-0 items-center justify-around border-t border-line bg-surface/95 px-2 pt-1 backdrop-blur-md md:hidden"
        style={{ paddingBottom: "max(0.25rem, env(safe-area-inset-bottom))" }}
      >
        <button
          type="button"
          onClick={() => setActiveView("overview")}
          className={`focus-ring flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-control px-1 py-1 type-caption font-medium transition-colors ${
            activeView === "overview" ? "text-accent" : "text-muted"
          }`}
        >
          <IconOverview />
          <span className="truncate">Overview</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveView("copilot")}
          className={`focus-ring flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-control px-1 py-1 type-caption font-medium transition-colors ${
            activeView === "copilot" ? "text-accent" : "text-muted"
          }`}
          aria-label="Ask AI"
        >
          <IconChat />
          <span className="truncate">Ask AI</span>
        </button>
        <button
          type="button"
          onClick={() => setActiveView("settings")}
          className={`focus-ring flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-control px-1 py-1 type-caption font-medium transition-colors ${
            activeView === "settings" ? "text-accent" : "text-muted"
          }`}
        >
          <IconSettings />
          <span className="truncate">Settings</span>
        </button>
      </nav>

      {historyDrawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Conversation history">
          <button
            type="button"
            aria-label="Close conversations"
            className="absolute inset-0 bg-black/40"
            onClick={() => setHistoryDrawerOpen(false)}
          />
          <div
            className="absolute inset-x-0 bottom-0 flex max-h-[75dvh] flex-col rounded-t-2xl border-t border-line bg-surface px-4 pt-3 shadow-float"
            style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
          >
            <div className="mb-3 flex shrink-0 items-center justify-between gap-3">
              <div>
                <p className="type-overline text-accentText">Conversations</p>
                <p className="type-caption text-subtle">Tap a conversation to restore its messages.</p>
              </div>
              <button
                type="button"
                onClick={() => setHistoryDrawerOpen(false)}
                className="focus-ring rounded-control border border-line px-2.5 py-1.5 type-caption font-medium text-muted"
              >
                Close
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain pb-1">
              <ConversationList
                conversations={conversations}
                activeConversationId={activeConversationId}
                loading={conversationLoading && conversations.length === 0}
                disabled={chatBusy || conversationLoading}
                onCreate={handleNewConversation}
                onSelect={openConversation}
                scrollable={false}
              />
              {conversationError && (
                <p className="mt-2 rounded-card border border-danger/30 bg-dangerSoft px-3 py-2 type-sm text-danger">
                  {conversationError}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {briefingOpen && (
        <MorningBriefingModal
          onClose={() => setBriefingOpen(false)}
          refreshToken={boardTick}
          onAlertCreated={() => setBoardTick((n) => n + 1)}
        />
      )}
    </div>
  );
}
