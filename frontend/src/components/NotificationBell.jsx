import { useEffect, useId, useRef, useState } from "react";
import { partitionWatches } from "../services/watchDisplay.js";

const SEEN_PENDING_KEY = "sweaterco:seen-pending-users";
const SEEN_ALERTS_KEY = "sweaterco:seen-alert-watches";

function readIds(key) {
  try {
    const parsed = JSON.parse(localStorage.getItem(key) || "[]");
    return new Set(Array.isArray(parsed) ? parsed.map(String) : []);
  } catch {
    return new Set();
  }
}

function writeIds(key, set) {
  try {
    localStorage.setItem(key, JSON.stringify(Array.from(set)));
  } catch {
    /* ignore quota / private mode */
  }
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

/**
 * Top-right notification bell.
 *
 * A single bell opens a small menu with two destinations:
 *   - User requests  -> User Management (pending approvals)
 *   - Alerts & watches -> Alerts page
 *
 * The red badge counts *unseen* items and shrinks as soon as the user opens a
 * category (the currently-visible ids are remembered in localStorage).
 */
export default function NotificationBell({
  pendingUsers = [],
  watches,
  onOpenPending,
  onOpenAlerts,
  className = "",
}) {
  const [open, setOpen] = useState(false);
  const [seenPending, setSeenPending] = useState(() => readIds(SEEN_PENDING_KEY));
  const [seenAlerts, setSeenAlerts] = useState(() => readIds(SEEN_ALERTS_KEY));
  const rootRef = useRef(null);
  const panelId = useId();

  const { triggered } = partitionWatches(watches);
  const pendingIds = pendingUsers.map((u) => String(u.id));
  const alertIds = triggered.map((w) => String(w.watch_id));
  const pendingUnread = pendingIds.filter((id) => !seenPending.has(id)).length;
  const alertUnread = alertIds.filter((id) => !seenAlerts.has(id)).length;
  const totalUnread = pendingUnread + alertUnread;

  useEffect(() => {
    if (!open) return undefined;
    function onDown(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    }
    function onKey(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function markPendingSeen() {
    const next = new Set(seenPending);
    pendingIds.forEach((id) => next.add(id));
    setSeenPending(next);
    writeIds(SEEN_PENDING_KEY, next);
  }

  function markAlertsSeen() {
    const next = new Set(seenAlerts);
    alertIds.forEach((id) => next.add(id));
    setSeenAlerts(next);
    writeIds(SEEN_ALERTS_KEY, next);
  }

  function openPending() {
    markPendingSeen();
    setOpen(false);
    onOpenPending?.();
  }

  function openAlerts() {
    markAlertsSeen();
    setOpen(false);
    onOpenAlerts?.();
  }

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`Notifications${totalUnread ? ` · ${totalUnread} new` : ""}`}
        title="Notifications"
        className="focus-ring relative inline-flex h-9 w-9 items-center justify-center rounded-control border border-line bg-surface text-muted transition-colors hover:bg-surfaceMuted hover:text-accentText"
      >
        <BellIcon />
        {totalUnread > 0 && (
          <span className="absolute right-0 top-0 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-danger px-0.5 text-[8px] font-bold text-white">
            {totalUnread > 99 ? "99+" : totalUnread}
          </span>
        )}
      </button>

      {open && (
        <div
          id={panelId}
          className="absolute right-0 top-[calc(100%+0.5rem)] z-50 w-72 max-w-[calc(100vw-1.5rem)] rounded-card border border-line bg-surface p-2 shadow-float"
        >
          <p className="px-2 py-1 type-overline text-subtle">Notifications</p>

          <button
            type="button"
            onClick={openPending}
            className="focus-ring flex w-full items-start gap-2 rounded-control px-2 py-2 text-left transition-colors hover:bg-surfaceMuted"
          >
            <span className="mt-0.5 text-accentText" aria-hidden="true"><BellIcon /></span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center justify-between gap-2">
                <span className="type-sm font-medium text-foreground">User requests</span>
                {pendingUnread > 0 ? (
                  <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">{pendingUnread}</span>
                ) : (
                  <span className="type-caption text-subtle">0</span>
                )}
              </span>
              <span className="mt-0.5 block type-caption text-muted">
                {pendingIds.length === 0 ? "No pending registrations" : `${pendingIds.length} pending approval${pendingIds.length === 1 ? "" : "s"}`}
              </span>
            </span>
          </button>

          <button
            type="button"
            onClick={openAlerts}
            className="focus-ring mt-1 flex w-full items-start gap-2 rounded-control px-2 py-2 text-left transition-colors hover:bg-surfaceMuted"
          >
            <span className="mt-0.5 text-accentText" aria-hidden="true"><BellIcon /></span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center justify-between gap-2">
                <span className="type-sm font-medium text-foreground">Alerts & watches</span>
                {alertUnread > 0 ? (
                  <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">{alertUnread}</span>
                ) : (
                  <span className="type-caption text-subtle">0</span>
                )}
              </span>
              <span className="mt-0.5 block type-caption text-muted">
                {triggered.length === 0 ? "Nothing triggered" : `${triggered.length} triggered watch${triggered.length === 1 ? "" : "es"}`}
              </span>
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
