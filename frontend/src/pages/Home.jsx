import { useCallback, useEffect, useRef, useState } from "react";
import Sidebar from "../components/Sidebar.jsx";
import ChatPanel from "../components/ChatPanel.jsx";
import ConversationList from "../components/ConversationList.jsx";
import AlertsRail from "../components/AlertsRail.jsx";
import AlertsPage from "../components/AlertsPage.jsx";
import NotificationBell from "../components/NotificationBell.jsx";
import { ErrorBoundary } from "../components/ui/ErrorBoundary.jsx";
import DataManagement from "./DataManagement.jsx";
import UserManagement from "./UserManagement.jsx";
import { useAuth } from "../auth/AuthContext.jsx";
import { fetchHealth, setFactoryDate } from "../services/api.js";
import { deactivateMe } from "../services/authApi.js";
import {
  createConversation,
  deleteConversation,
  detectConversationCapabilities,
  fetchConversationHistory,
  fetchConversations,
} from "../services/conversationsApi.js";
import { invalidateOverviewCache, loadOverviewData, peekOverviewCache } from "../services/overviewCache.js";
import { friendlyAuthError } from "../services/authErrors.js";
import { listPendingUsers } from "../services/usersApi.js";
import {
  Button,
  Card,
  LoadingState,
  Modal,
  ThemeSwitcher,
} from "../components/ui/index.js";
import { Avatar, BrandMark, Icon } from "../pages/design-preview/bits.jsx";

const SEARCH_DEBOUNCE_MS = 300;

function storageKey(userId) {
  return `sweaterco:last-conversation:${userId}`;
}

function pinStorageKey(userId) {
  return `sweaterco:pinned-conversations:${userId}`;
}

function readPinnedIds(userId) {
  if (!userId) return new Set();
  try {
    const parsed = JSON.parse(localStorage.getItem(pinStorageKey(userId)) || "[]");
    return new Set(Array.isArray(parsed) ? parsed : []);
  } catch {
    return new Set();
  }
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
        actionOffer: metadata.action_offer || null,
        actionOfferDecision: metadata.action_offer_decision || null,
        turnId: turn.id,
        charts: metadata.charts || [],
        tables: metadata.tables || [],
        clarification: metadata.clarification || null,
        clarificationChoice: metadata.clarification_choice || "",
        why: metadata.why || null,
        decision: metadata.decision || null,
      },
    ];
  });
}

function RailButton({ icon, label, active, badge = 0, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label={label}
      aria-current={active ? "page" : undefined}
      className={`dp-rail-btn focus-ring ${active ? "is-active" : ""}`}
    >
      <Icon name={icon} size={18} />
      {badge > 0 && (
        <span className="absolute right-1 top-1 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-danger px-0.5 text-[8px] font-bold text-white">
          {badge}
        </span>
      )}
      <span className="dp-rail-tip">{label}</span>
    </button>
  );
}

function formatFactoryDateLabel(iso) {
  if (!iso) return "";
  const parts = String(iso).slice(0, 10).split("-");
  if (parts.length !== 3) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const month = months[Number(parts[1]) - 1];
  return month ? `${Number(parts[2])} ${month} ${parts[0]}` : iso;
}

const VIEW_META = {
  copilot: {
    eyebrow: "AI Workspace",
    title: "Ask AI",
    subtitle: "Grounded factory answers",
  },
  overview: {
    eyebrow: "Insights",
    title: "Overview",
    subtitle: "Top issues with morning and weekly factory briefing.",
  },
  alerts: {
    eyebrow: "Alerts",
    title: "Alerts & watches",
    subtitle: "Triggered alerts, active watches and watch history.",
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
  const [health, setHealth] = useState(null);
  const [healthError, setHealthError] = useState("");
  const [boardTick, setBoardTick] = useState(0);
  const [activeView, setActiveView] = useState("copilot");
  const [confirmDeactivate, setConfirmDeactivate] = useState(false);
  const [deactivateBusy, setDeactivateBusy] = useState(false);
  const [deactivateError, setDeactivateError] = useState("");
  const [conversationCatalog, setConversationCatalog] = useState([]);
  const [searchResults, setSearchResults] = useState(null);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [searchLoading, setSearchLoading] = useState(false);
  const [listError, setListError] = useState("");
  const [capabilities, setCapabilities] = useState({ search: false, delete: false });
  const [capabilitiesReady, setCapabilitiesReady] = useState(false);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [messageSeeds, setMessageSeeds] = useState({});
  const [conversationLoading, setConversationLoading] = useState(true);
  const [conversationError, setConversationError] = useState("");
  const [busyIds, setBusyIds] = useState(() => new Set());
  const [pinnedConversationIds, setPinnedConversationIds] = useState(() => new Set());
  const busyIdsRef = useRef(busyIds);
  busyIdsRef.current = busyIds;
  const watchSaveHolds = useRef(0);
  const [composerDraft, setComposerDraft] = useState("");
  const [factoryDate, setFactoryDateState] = useState(() => peekOverviewCache()?.briefing?.clock_date || peekOverviewCache()?.briefing?.factory_today || "");
  const [dateDraft, setDateDraft] = useState(() => peekOverviewCache()?.briefing?.clock_date || peekOverviewCache()?.briefing?.factory_today || "");
  const [dateSaving, setDateSaving] = useState(false);
  const [dateError, setDateError] = useState("");
  const [dateNotice, setDateNotice] = useState("");
  const [watches, setWatches] = useState(() => peekOverviewCache()?.watches || { fired: [], active: [], cancelled: [] });
  const [watchesLoading, setWatchesLoading] = useState(false);
  const [pendingUsers, setPendingUsers] = useState([]);
  const [usersReopenNonce, setUsersReopenNonce] = useState(0);
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const [alertsDrawerOpen, setAlertsDrawerOpen] = useState(false);
  const [contextCollapsed, setContextCollapsed] = useState(() => {
    try {
      return localStorage.getItem("sweaterco:context-collapsed") === "true";
    } catch {
      return false;
    }
  });
  const [pendingDelete, setPendingDelete] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [deleteError, setDeleteError] = useState("");
  const [askAiNotice, setAskAiNotice] = useState("");
  const historyRequest = useRef(0);
  const searchRequest = useRef(0);
  const searchInputRef = useRef("");
  const bootstrappedRef = useRef(false);
  const pinnedIdsRef = useRef(new Set());
  const pinnedRowsRef = useRef(new Map());
  const conversationCatalogRef = useRef([]);
  const activeConversationIdRef = useRef(null);

  const isAdmin = user?.role === "ADMIN";
  const searching = Boolean(debouncedSearch.trim());
  const conversations = searching ? searchResults || [] : conversationCatalog;

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then((result) => {
        if (cancelled) return;
        setHealth(result);
        setHealthError("");
      })
      .catch((err) => {
        if (!cancelled) setHealthError(err.message);
      });
    return () => { cancelled = true; };
  }, [boardTick]);

  useEffect(() => {
    let cancelled = false;
    setWatchesLoading(true);
    loadOverviewData({ force: boardTick > 0 || !peekOverviewCache()?.briefing })
      .then((payload) => {
        if (cancelled) return;
        const clock = payload.briefing?.clock_date || payload.briefing?.factory_today;
        if (clock) {
          setFactoryDateState(clock);
          setDateDraft(clock);
        }
        setWatches(payload.watches || { fired: [], active: [], cancelled: [] });
      })
      .catch(() => {
        const cached = peekOverviewCache();
        if (!cancelled && cached) {
          const cachedClock = cached.briefing?.clock_date || cached.briefing?.factory_today;
          if (cachedClock) {
            setFactoryDateState(cachedClock);
            setDateDraft(cachedClock);
          }
          setWatches(cached.watches || { fired: [], active: [], cancelled: [] });
        }
      })
      .finally(() => {
        if (!cancelled && watchSaveHolds.current === 0) setWatchesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [boardTick]);

  useEffect(() => {
    if (!isAdmin) {
      setPendingUsers([]);
      return undefined;
    }
    let cancelled = false;
    listPendingUsers()
      .then((res) => {
        if (!cancelled) setPendingUsers(Array.isArray(res?.items) ? res.items : []);
      })
      .catch(() => {
        if (!cancelled) setPendingUsers([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isAdmin, boardTick]);

  useEffect(() => {
    let cancelled = false;
    detectConversationCapabilities().then((next) => {
      if (!cancelled) {
        setCapabilities(next);
        setCapabilitiesReady(true);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!isAdmin && (activeView === "data" || activeView === "users")) {
      setActiveView("copilot");
    }
  }, [isAdmin, activeView]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedSearch(searchInputRef.current);
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(handle);
  }, [searchInput]);

  function keepIds() {
    return [...new Set(
      [...pinnedIdsRef.current, ...busyIdsRef.current, activeConversationIdRef.current].filter(Boolean),
    )];
  }

  function keepIdsForNewConversation() {
    const leaving = activeConversationIdRef.current;
    return keepIds().filter((id) => id !== leaving);
  }

  function listedConversation(row) {
    return (row.turn_count || 0) > 0 || row.pending || row.in_progress;
  }

  function replaceCatalog(next) {
    conversationCatalogRef.current = next;
    setConversationCatalog(next);
    return next;
  }

  function mergeCatalog(rows) {
    const serverRows = (rows || [])
      .filter((row) => (row.turn_count || 0) > 0 || row.in_progress)
      .map((row) => {
        const pinned = pinnedRowsRef.current.get(row.id);
        const title = row.title === "New conversation" && pinned?.title ? pinned.title : row.title;
        return { ...row, title, pending: false };
      });
    const seen = new Set(serverRows.map((row) => row.id));
    for (const row of serverRows) {
      if ((row.turn_count || 0) > 0) {
        pinnedIdsRef.current.delete(row.id);
        pinnedRowsRef.current.delete(row.id);
      }
    }
    const extras = [];
    for (const [id, row] of pinnedRowsRef.current) {
      if (!seen.has(id)) extras.push(row);
    }
    return [...extras, ...serverRows].sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
  }

  function questionTitle(question) {
    const compact = String(question || "").trim().replace(/\s+/g, " ");
    return compact.slice(0, 80) || "New conversation";
  }

  function noteQuestionSubmitted(conversationId, question) {
    if (!conversationId) return;
    const existing = conversationCatalogRef.current.find((row) => row.id === conversationId);
    const alreadySaved = Boolean(existing && !existing.pending && (existing.turn_count || 0) > 0);
    const row = {
      id: conversationId,
      title: alreadySaved ? existing.title : questionTitle(question),
      created_at: existing?.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
      turn_count: existing?.turn_count || 0,
      pending: !alreadySaved,
      in_progress: true,
    };
    if (!alreadySaved) {
      pinnedIdsRef.current.add(conversationId);
      pinnedRowsRef.current.set(conversationId, row);
    }
    const next = [row, ...conversationCatalogRef.current.filter((item) => item.id !== conversationId)];
    replaceCatalog(next);
    setSearchResults((current) => (
      current ? [row, ...current.filter((item) => item.id !== conversationId)] : current
    ));
  }

  function noteQuestionFailed(conversationId) {
    if (!conversationId) return;
    pinnedIdsRef.current.delete(conversationId);
    pinnedRowsRef.current.delete(conversationId);
    refreshConversationCatalog().catch(() => {
      replaceCatalog(
        conversationCatalogRef.current.filter((row) => row.id !== conversationId || !row.pending),
      );
    });
  }

  async function refreshConversationCatalog() {
    const rows = replaceCatalog(mergeCatalog(await fetchConversations(50, "", keepIds())));
    return rows;
  }

  const openConversation = useCallback(
    async (conversationId) => {
      if (!user?.id || !conversationId) return;
      activeConversationIdRef.current = conversationId;
      const requestId = ++historyRequest.current;
      setConversationLoading(true);
      setConversationError("");
      try {
        const history = await fetchConversationHistory(conversationId);
        if (requestId !== historyRequest.current) return;
        setActiveConversationId(history.conversation.id);
        setMessageSeeds((current) => {
          if (busyIdsRef.current.has(history.conversation.id)) return current;
          return {
            ...current,
            [history.conversation.id]: messagesFromTurns(history.turns),
          };
        });
        localStorage.setItem(storageKey(user.id), history.conversation.id);
        setActiveView("copilot");
        setAskAiNotice("");
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
    pinnedIdsRef.current = new Set();
    pinnedRowsRef.current = new Map();
    conversationCatalogRef.current = [];
    setConversationCatalog([]);
    setSearchResults(null);
    setSearchInput("");
    searchInputRef.current = "";
    setDebouncedSearch("");
    activeConversationIdRef.current = null;
    setActiveConversationId(null);
    setMessageSeeds({});
    setBusyIds(new Set());
    setConversationError("");
    setListError("");
    setConversationLoading(true);
    bootstrappedRef.current = false;

    async function restoreConversations() {
      if (!user?.id) return;
      try {
        let rows = mergeCatalog(await fetchConversations(50, "", keepIds()));
        if (cancelled) return;
        if (rows.length === 0) {
          const created = await createConversation(keepIdsForNewConversation());
          if (cancelled) return;
          activeConversationIdRef.current = created.id;
          replaceCatalog([]);
          await openConversation(created.id);
          bootstrappedRef.current = true;
          return;
        }
        replaceCatalog(rows);
        const remembered = localStorage.getItem(storageKey(user.id));
        const selected = rows.some((item) => item.id === remembered) ? remembered : rows[0].id;
        await openConversation(selected);
        bootstrappedRef.current = true;
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

  useEffect(() => {
    setPinnedConversationIds(readPinnedIds(user?.id));
  }, [user?.id]);

  function togglePinnedConversation(conversationId) {
    if (!user?.id || !conversationId) return;
    setPinnedConversationIds((current) => {
      const next = new Set(current);
      if (next.has(conversationId)) next.delete(conversationId);
      else next.add(conversationId);
      localStorage.setItem(pinStorageKey(user.id), JSON.stringify([...next]));
      return next;
    });
  }

  useEffect(() => {
    if (!capabilities.search) {
      setSearchResults(null);
      setSearchLoading(false);
      return undefined;
    }
    const query = debouncedSearch.trim();
    if (!query) {
      setSearchResults(null);
      setSearchLoading(false);
      setListError("");
      return undefined;
    }

    let cancelled = false;
    const requestId = ++searchRequest.current;
    setSearchLoading(true);
    setListError("");

    fetchConversations(50, query)
      .then((rows) => {
        if (cancelled || requestId !== searchRequest.current) return;
        setSearchResults(rows.filter(listedConversation));
      })
      .catch((err) => {
        if (cancelled || requestId !== searchRequest.current) return;
        setSearchResults([]);
        setListError(err.message || "Search failed.");
      })
      .finally(() => {
        if (!cancelled && requestId === searchRequest.current) {
          setSearchLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [capabilities.search, debouncedSearch]);

  function handleSearchChange(value) {
    searchInputRef.current = value;
    setSearchInput(value);
    if (!value.trim()) {
      setDebouncedSearch("");
      setSearchResults(null);
      setListError("");
    }
  }

  const setConversationBusy = useCallback((conversationId, isBusy) => {
    if (!conversationId) return;
    setBusyIds((current) => {
      if (current.has(conversationId) === isBusy) return current;
      const next = new Set(current);
      if (isBusy) next.add(conversationId);
      else next.delete(conversationId);
      return next;
    });
  }, []);

  async function handleNewConversation({ fromAskAi = false } = {}) {
    if (composerDraft.trim()) {
      if (fromAskAi) {
        setActiveView("copilot");
        setAskAiNotice("Unsent draft kept — clear the composer or send it before starting a new chat.");
      }
      return;
    }
    setConversationError("");
    setAskAiNotice("");
    setHistoryDrawerOpen(false);
    try {
      const created = await createConversation(keepIdsForNewConversation());
      activeConversationIdRef.current = created.id;
      replaceCatalog(conversationCatalogRef.current.filter(listedConversation));
      setDebouncedSearch("");
      setSearchResults(null);
      setComposerDraft("");
      await openConversation(created.id);
    } catch (err) {
      setConversationError(err.message);
    }
  }

  function handleAskAiNav() {
    setActiveView("copilot");
    if (!bootstrappedRef.current || conversationLoading) return;
    handleNewConversation({ fromAskAi: true });
  }

  function beginWatchSave() {
    watchSaveHolds.current += 1;
    setWatchesLoading(true);
  }

  function abandonWatchSave() {
    watchSaveHolds.current = Math.max(0, watchSaveHolds.current - 1);
    if (watchSaveHolds.current === 0) setWatchesLoading(false);
  }

  function finishWatchSave() {
    watchSaveHolds.current = Math.max(0, watchSaveHolds.current - 1);
    invalidateOverviewCache();
    setWatchesLoading(true);
    setBoardTick((n) => n + 1);
  }

  function handleWatchChanged() {
    invalidateOverviewCache();
    setWatchesLoading(true);
    setBoardTick((n) => n + 1);
  }

  async function saveFactoryDate() {
    if (!dateDraft || dateSaving) return;
    setDateSaving(true);
    setDateError("");
    setDateNotice("");
    try {
      const result = await setFactoryDate(dateDraft);
      const next = result?.factory_today || dateDraft;
      setFactoryDateState(next);
      setDateDraft(next);
      setDateNotice("Saved. Every account now treats this date as today.");
      invalidateOverviewCache();
      setBoardTick((n) => n + 1);
    } catch (err) {
      setDateError(err.message || "Could not save the factory date.");
    } finally {
      setDateSaving(false);
    }
  }

  async function handleConversationUpdated(conversationId) {
    try {
      const rows = await fetchConversations(50, "", keepIds());
      if (conversationId) {
        const saved = rows.some((row) => row.id === conversationId && (row.turn_count || 0) > 0);
        if (!saved) {
          pinnedIdsRef.current.delete(conversationId);
          pinnedRowsRef.current.delete(conversationId);
        }
      }
      replaceCatalog(mergeCatalog(rows));
      const query = debouncedSearch.trim();
      if (capabilities.search && query) {
        const requestId = ++searchRequest.current;
        const found = await fetchConversations(50, query, keepIds());
        if (requestId === searchRequest.current) {
          setSearchResults(found.filter(listedConversation));
        }
      }
    } catch (err) {
      setConversationError(err.message);
    }
  }

  async function confirmDeleteConversation() {
    if (!pendingDelete || deletingId) return;
    const target = pendingDelete;
    const wasActive = target.id === activeConversationId;
    setDeletingId(target.id);
    setDeleteError("");
    try {
      await deleteConversation(target.id);
      setPendingDelete(null);
      const catalog = await refreshConversationCatalog();
      const query = debouncedSearch.trim();
      if (capabilities.search && query) {
        const requestId = ++searchRequest.current;
        const filtered = await fetchConversations(50, query);
        if (requestId === searchRequest.current) {
          setSearchResults(filtered.filter(listedConversation));
        }
      } else {
        setSearchResults(null);
      }
      if (wasActive) {
        if (catalog.length > 0) {
          await openConversation(catalog[0].id);
        } else {
          const created = await createConversation(keepIdsForNewConversation());
          activeConversationIdRef.current = created.id;
          replaceCatalog([]);
          setSearchInput("");
          searchInputRef.current = "";
          setDebouncedSearch("");
          setSearchResults(null);
          await openConversation(created.id);
        }
      }
    } catch (err) {
      setDeleteError(err.message || "Could not delete conversation.");
    } finally {
      setDeletingId(null);
    }
  }

  const conversationListProps = {
    conversations,
    activeConversationId,
    loading: conversationLoading && conversationCatalog.length === 0,
    searching: searchLoading,
    searchQuery: searchInput,
    // Hide search/delete until OpenAPI confirms the teammate backend is live.
    searchEnabled: capabilitiesReady && capabilities.search,
    searchUnavailable: false,
    onSearchChange: handleSearchChange,
    disabled: Boolean(deletingId),
    busyIds,
    pinnedIds: pinnedConversationIds,
    onTogglePin: togglePinnedConversation,
    canDelete: capabilitiesReady && capabilities.delete,
    deleteUnavailable: false,
    deletingId,
    onCreate: handleNewConversation,
    onSelect: openConversation,
    onRequestDelete: (conversation) => {
      setDeleteError("");
      setPendingDelete(conversation);
    },
    listError,
  };

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
    if (key === "copilot") {
      handleAskAiNav();
      return;
    }
    setAskAiNotice("");
    setActiveView(key);
  }

  const liveConversationIds = [];
  if (activeConversationId) liveConversationIds.push(activeConversationId);
  busyIds.forEach((conversationId) => {
    if (!liveConversationIds.includes(conversationId)) liveConversationIds.push(conversationId);
  });

  const viewMeta = VIEW_META[activeView] || VIEW_META.copilot;

  function toggleContextPanel() {
    setContextCollapsed((current) => {
      const next = !current;
      try {
        localStorage.setItem("sweaterco:context-collapsed", String(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }

  const hasContext = activeView === "copilot";
  const isLive = liveConversationIds.length > 0;

  return (
    <div
      className="flex h-dvh flex-col overflow-hidden bg-transparent text-foreground"
      style={{ background: "rgb(var(--surface) / 0.96)" }}
    >
      <div className="dp-shell">
        <aside className="dp-rail hidden md:flex" aria-label="Primary navigation">
          <div className="dp-rail-brand">
            <BrandMark size={34} />
          </div>

          <div className="dp-rail-group">
            <RailButton icon="chat" label="Ask AI" active={activeView === "copilot"} onClick={() => handleNav("copilot")} />
            <RailButton icon="grid" label="Overview" active={activeView === "overview"} onClick={() => handleNav("overview")} />
          </div>

          {isAdmin && (
            <>
              <div className="dp-rail-divider" role="presentation" />
              <div className="dp-rail-group">
                <RailButton icon="database" label="Data Management" active={activeView === "data"} onClick={() => handleNav("data")} />
                <RailButton icon="users" label="User Management" active={activeView === "users"} onClick={() => handleNav("users")} />
              </div>
            </>
          )}

          <div className="dp-rail-spacer" />

          <div className="dp-rail-group">
            <RailButton icon="settings" label="Settings" active={activeView === "settings"} onClick={() => handleNav("settings")} />
            <button
              type="button"
              onClick={logout}
              aria-label="Log out"
              className="dp-rail-btn focus-ring"
            >
              <Icon name="logout" size={18} />
              <span className="dp-rail-tip">Log out</span>
            </button>
            <div className="dp-rail-avatar">
              <Avatar initials={(user?.username || "U").slice(0, 2).toUpperCase()} size={32} />
            </div>
          </div>
        </aside>

        {hasContext && (
          <aside
            className={`dp-context hidden md:flex ${contextCollapsed ? "is-collapsed" : ""}`}
            aria-hidden={contextCollapsed}
            aria-label="Context panel"
          >
            <div className="dp-context-inner">
              <div className="dp-context-head">
                <div className="min-w-0">
                  <p className="dp-context-title truncate">Conversations</p>
                  <p className="dp-context-sub truncate">{conversations.length} saved</p>
                </div>
                <button
                  type="button"
                  onClick={toggleContextPanel}
                  className="dp-icon-btn h-8 w-8 focus-ring"
                  aria-label="Collapse context panel"
                  title="Collapse panel"
                >
                  <Icon name="panelLeft" size={14} />
                </button>
              </div>
              <div className="dp-context-scroll">
                <button
                  type="button"
                  disabled={conversationLoading}
                  onClick={() => handleNewConversation()}
                  className="dp-btn dp-btn-primary focus-ring h-9 w-full disabled:opacity-50"
                >
                  <Icon name="plus" size={13} />
                  New conversation
                </button>

                <div id="conversation-history" className="dp-context-section mt-3">
                  <ConversationList {...conversationListProps} scrollable={false} />
                  {conversationError && (
                    <p className="dp-empty mt-2">{conversationError}</p>
                  )}
                </div>
              </div>
            </div>
          </aside>
        )}

        <main className="dp-main min-h-0 min-w-0 flex-1">
          <header className="dp-mobile-top md:hidden">
            <button
              type="button"
              onClick={() => setHistoryDrawerOpen(true)}
              className="dp-icon-btn h-9 w-9 focus-ring justify-self-start"
              aria-label="Open conversation history"
            >
              <Icon name="history" size={16} />
            </button>
            <div className="dp-mobile-brand">
              <BrandMark size={24} />
              <span className="dp-mobile-brand-name">SweaterCo</span>
            </div>
            <div className="justify-self-end">
              <NotificationBell
                pendingUsers={pendingUsers}
                watches={watches}
                onOpenPending={() => {
                  setUsersReopenNonce((n) => n + 1);
                  handleNav("users");
                }}
                onOpenAlerts={() => handleNav("alerts")}
              />
            </div>
          </header>

          <div className="dp-main-topbar hidden md:flex">
            <div className="dp-crumb">
              {hasContext && contextCollapsed && (
                <button
                  type="button"
                  onClick={toggleContextPanel}
                  className="dp-icon-btn h-8 w-8 focus-ring"
                  aria-label="Expand context panel"
                  title="Expand panel"
                >
                  <Icon name="panelRight" size={14} />
                </button>
              )}
              <div className="min-w-0">
                <p className="dp-crumb-title truncate">{viewMeta.title}</p>
                <p className="dp-crumb-sub truncate">{viewMeta.subtitle}</p>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {factoryDate && (
                <span className="dp-chip hidden lg:inline-flex" title={`Factory date ${factoryDate}`}>
                  <Icon name="clock" size={11} />
                  {formatFactoryDateLabel(factoryDate)}
                </span>
              )}
              <span className="dp-status">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    healthError ? "bg-danger" : health?.ok ? "bg-success" : "bg-muted"
                  }`}
                />
                {healthError ? "API offline" : health ? `API ${health.ok ? "ready" : "down"}` : "Checking API…"}
              </span>
              <NotificationBell
                pendingUsers={pendingUsers}
                watches={watches}
                onOpenPending={() => handleNav("users")}
                onOpenAlerts={() => handleNav("alerts")}
              />
            </div>
          </div>

          {activeView === "copilot" && (
            isLive ? (
              <div className="relative min-h-0 flex-1 overflow-hidden">
                {liveConversationIds.map((conversationId) => (
                  <div
                    key={conversationId}
                    className={conversationId === activeConversationId ? "absolute inset-0" : "hidden"}
                  >
                    <ChatPanel
                      conversationId={conversationId}
                      initialMessages={messageSeeds[conversationId] || []}
                      active={conversationId === activeConversationId}
                      llmReady={Boolean(health?.llm_configured)}
                      onBusyChange={setConversationBusy}
                      onConversationUpdated={handleConversationUpdated}
                      onQuestionSubmitted={noteQuestionSubmitted}
                      onQuestionFailed={noteQuestionFailed}
                      onBoardPending={beginWatchSave}
                      onBoardFailed={abandonWatchSave}
                      onBoardSaved={finishWatchSave}
                      onBoardChanged={handleWatchChanged}
                      onOpenConversations={() => setHistoryDrawerOpen(true)}
                      onNewConversation={handleNewConversation}
                      onDraftChange={setComposerDraft}
                      notice={conversationId === activeConversationId ? askAiNotice : ""}
                      onDismissNotice={() => setAskAiNotice("")}
                    />
                  </div>
                ))}
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
            )
          )}

          {activeView === "alerts" && (
            <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
              <div className="mx-auto max-w-3xl space-y-4">
                <div>
                  <p className="type-overline text-accentText">{viewMeta.eyebrow}</p>
                  <h2 className="type-h2 text-foreground">{viewMeta.title}</h2>
                  <p className="type-sm text-muted">{viewMeta.subtitle}</p>
                </div>
                <div className="rounded-card border border-line bg-surface p-3 shadow-xs">
                  <ErrorBoundary>
                    <AlertsPage
                      watches={watches}
                      loading={watchesLoading}
                      onWatchChanged={handleWatchChanged}
                    />
                  </ErrorBoundary>
                </div>
              </div>
            </div>
          )}

          {activeView === "overview" && (
            <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
              <Sidebar
                refreshToken={boardTick}
                onFactoryDate={(value) => {
                  if (!value) return;
                  setFactoryDateState(value);
                  setDateDraft(value);
                }}
              />
            </div>
          )}

          {activeView === "data" && isAdmin && (
            <div className="min-h-0 min-w-0 flex-1 overflow-y-auto p-4 md:p-6">
              <ErrorBoundary>
                <DataManagement />
              </ErrorBoundary>
            </div>
          )}

          {activeView === "users" && isAdmin && (
            <div className="min-h-0 flex-1 overflow-y-auto p-4 md:p-6">
              <ErrorBoundary>
                <UserManagement key={`users-${usersReopenNonce}`} />
              </ErrorBoundary>
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
                  <p className="mt-1 type-sm text-muted">Pick one of seven complete colour themes — Ocean, Lavender, Sage, Rose, Amber, Slate or Black. Settings persist across reloads.</p>
                  <div className="mt-4">
                    <ThemeSwitcher />
                  </div>
                </section>

                {isAdmin && (
                  <section className="rounded-card border border-line bg-surface p-5 shadow-xs">
                    <h3 className="type-h3 text-foreground">Factory date</h3>
                    <p className="mt-1 type-sm text-muted">
                      Choose any day every account treats as today, including dates before 1 April 2026. Other accounts only see the date. A warning that already fired stays fired.
                    </p>
                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <input
                        type="date"
                        value={dateDraft}
                        onChange={(event) => {
                          setDateDraft(event.target.value);
                          setDateNotice("");
                          setDateError("");
                        }}
                        className="focus-ring rounded-control border border-line bg-canvas px-3 py-2 type-sm text-foreground"
                      />
                      <Button size="sm" onClick={saveFactoryDate} disabled={!dateDraft || dateSaving || dateDraft === factoryDate}>
                        {dateSaving ? "Saving…" : "Save"}
                      </Button>
                    </div>
                    {dateNotice && <p className="mt-2 type-caption text-success">{dateNotice}</p>}
                    {dateError && <p className="mt-2 type-caption text-danger">{dateError}</p>}
                  </section>
                )}

                <section className="rounded-card border border-line bg-surface p-5 shadow-xs">
                  <h3 className="type-h3 text-foreground">Security & Session</h3>
                  <p className="mt-1 type-sm text-muted">Sign out ends the current browser session.</p>
                  <button
                    type="button"
                    onClick={logout}
                    className="focus-ring mt-4 inline-flex items-center gap-2 rounded-control border border-line bg-surface px-4 py-2 type-sm font-medium text-foreground transition-colors hover:bg-surfaceMuted"
                  >
                    <Icon name="logout" size={16} />
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

          <nav className="dp-mobile-nav md:hidden" aria-label="Primary navigation">
            <button
              type="button"
              onClick={() => handleNav("overview")}
              className={`dp-mobile-nav-item ${activeView === "overview" ? "is-active" : ""}`}
            >
              <span className="dp-mobile-nav-icon">
                <Icon name="grid" size={18} />
              </span>
              Overview
            </button>
            <div className="dp-mobile-nav-center">
              <button
                type="button"
                onClick={() => handleNav("copilot")}
                className="dp-mobile-fab-btn focus-ring"
                aria-label="Ask AI"
              >
                <Icon name="spark" size={22} />
              </button>
              <span className="dp-mobile-fab-label">Ask AI</span>
            </div>
            <button
              type="button"
              onClick={() => handleNav("settings")}
              className={`dp-mobile-nav-item ${activeView === "settings" ? "is-active" : ""}`}
            >
              <span className="dp-mobile-nav-icon">
                <Icon name="settings" size={18} />
              </span>
              Settings
            </button>
          </nav>
        </main>
      </div>

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
            <button
              type="button"
              disabled={conversationLoading}
              onClick={() => handleNewConversation()}
              className="dp-btn dp-btn-primary focus-ring mb-2 h-9 w-full shrink-0 disabled:opacity-50"
            >
              <Icon name="plus" size={13} />
              New conversation
            </button>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain pb-1">
              <ConversationList {...conversationListProps} scrollable={false} />
              {conversationError && (
                <p className="mt-2 rounded-card border border-danger/30 bg-dangerSoft px-3 py-2 type-sm text-danger">
                  {conversationError}
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {alertsDrawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Alerts and watch history">
          <button
            type="button"
            aria-label="Close alerts"
            className="absolute inset-0 bg-black/40"
            onClick={() => setAlertsDrawerOpen(false)}
          />
          <div
            className="absolute inset-x-0 bottom-0 flex max-h-[70dvh] flex-col rounded-t-2xl border-t border-line bg-surface px-4 pt-3 shadow-float"
            style={{ paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}
          >
            <div className="mb-3 flex shrink-0 items-center justify-between gap-3">
              <div>
                <p className="type-overline text-accentText">Alerts</p>
                <p className="type-caption text-subtle">Active watches and watch history.</p>
              </div>
              <button
                type="button"
                onClick={() => setAlertsDrawerOpen(false)}
                className="focus-ring rounded-control border border-line px-2.5 py-1.5 type-caption font-medium text-muted"
              >
                Close
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain pb-1">
              <AlertsRail
                watches={watches}
                loading={watchesLoading}
                compact
                defaultExpanded
                persistHistory
                onWatchChanged={handleWatchChanged}
              />
            </div>
          </div>
        </div>
      )}

      <Modal
        open={Boolean(pendingDelete)}
        onClose={() => {
          if (deletingId) return;
          setPendingDelete(null);
          setDeleteError("");
        }}
        title="Delete conversation"
        description="This permanently removes the conversation and its saved turns for your account."
        size="sm"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled={Boolean(deletingId)}
              onClick={() => {
                setPendingDelete(null);
                setDeleteError("");
              }}
            >
              Cancel
            </Button>
            <Button
              size="sm"
              variant="danger"
              disabled={Boolean(deletingId)}
              onClick={confirmDeleteConversation}
            >
              {deletingId ? "Deleting…" : "Delete"}
            </Button>
          </div>
        }
      >
        <p className="type-sm text-foreground">
          Delete{" "}
          <span className="font-semibold">
            {pendingDelete?.title || "this conversation"}
          </span>
          ?
        </p>
        {deleteError && (
          <p className="mt-3 type-caption text-danger" role="alert">
            {deleteError}
          </p>
        )}
      </Modal>
    </div>
  );
}
