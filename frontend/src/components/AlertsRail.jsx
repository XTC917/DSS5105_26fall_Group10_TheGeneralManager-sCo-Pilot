import { useEffect, useId, useRef, useState } from "react";
import { confirmAction } from "../services/api.js";
import { partitionWatches } from "../services/watchDisplay.js";
import { Badge, Button, Modal } from "./ui/index.js";

function formatFactoryDate(iso) {
  if (!iso) return "";
  const parts = String(iso).slice(0, 10).split("-");
  if (parts.length !== 3) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const month = months[Number(parts[1]) - 1];
  return month ? `${month} ${Number(parts[2])}` : iso;
}

function HistoryIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M4 12a8 8 0 1 0 2.3-5.7L4 8.6M4 4v4.6h4.6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M12 8v4.4l3 1.8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MoreIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="5" cy="12" r="1.6" fill="currentColor" />
      <circle cx="12" cy="12" r="1.6" fill="currentColor" />
      <circle cx="19" cy="12" r="1.6" fill="currentColor" />
    </svg>
  );
}

function BellIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  );
}

function WatchActions({ item, disabled, menuOpen, onToggleMenu, onRequestCancel }) {
  const menuId = useId();
  return (
    <div className="relative shrink-0">
      <button
        type="button"
        aria-label={`Actions for ${item.order_id}`}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        aria-controls={menuOpen ? menuId : undefined}
        disabled={disabled}
        onClick={(event) => {
          event.stopPropagation();
          onToggleMenu();
        }}
        className="focus-ring inline-flex h-7 w-7 items-center justify-center rounded-control text-muted transition-colors hover:bg-surfaceMuted hover:text-foreground disabled:opacity-50"
      >
        <MoreIcon />
      </button>
      {menuOpen && (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 top-[calc(100%+0.25rem)] z-40 min-w-[9.5rem] rounded-control border border-line bg-surface p-1 shadow-float"
        >
          <button
            type="button"
            role="menuitem"
            disabled={disabled}
            onClick={(event) => {
              event.stopPropagation();
              onRequestCancel();
            }}
            className="focus-ring block w-full rounded-control px-2.5 py-1.5 text-left type-caption font-medium text-danger hover:bg-dangerSoft disabled:opacity-50"
          >
            Cancel watch
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Compact watch and alerts strip above Conversations.
 * Cancel uses POST /api/actions/confirm { type: cancel_watch } — not chat.
 */
export default function AlertsRail({
  watches = { fired: [], active: [], cancelled: [] },
  loading = false,
  compact = false,
  variant = "inline",
  defaultExpanded = false,
  onWatchChanged,
}) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [menuWatchId, setMenuWatchId] = useState(null);
  const [pendingCancel, setPendingCancel] = useState(null);
  const [cancellingId, setCancellingId] = useState(null);
  const [cancelError, setCancelError] = useState("");
  const panelId = useId();
  const rootRef = useRef(null);

  const { triggered: fired, watching: active, done, cancelled } = partitionWatches(watches);
  const hasAlerts = fired.length > 0 || active.length > 0;
  const total = fired.length + active.length;

  useEffect(() => {
    if (!expanded && menuWatchId == null) return undefined;
    function onPointerDown(event) {
      if (!rootRef.current?.contains(event.target)) {
        setExpanded(false);
        setMenuWatchId(null);
      }
    }
    function onKeyDown(event) {
      if (event.key === "Escape") {
        setMenuWatchId(null);
        if (!pendingCancel) setExpanded(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [expanded, menuWatchId, pendingCancel]);

  async function confirmCancelWatch() {
    if (!pendingCancel || cancellingId) return;
    const target = pendingCancel;
    const watchId = Number(target.watch_id);
    if (!Number.isFinite(watchId)) {
      setCancelError("This watch is missing a valid id.");
      return;
    }
    setCancellingId(watchId);
    setCancelError("");
    try {
      const result = await confirmAction({
        type: "cancel_watch",
        watch_id: watchId,
        order_id: target.order_id,
      });
      if (!result?.ok) {
        const detail = result?.error?.message || result?.summary || "Could not cancel the watch.";
        throw new Error(detail);
      }
      setPendingCancel(null);
      setMenuWatchId(null);
      onWatchChanged?.();
    } catch (err) {
      setCancelError(err.message || "Could not cancel the watch.");
    } finally {
      setCancellingId(null);
    }
  }

  function renderWatchRow(item, { triggered = false } = {}) {
    const busy = cancellingId === Number(item.watch_id);
    return (
      <div
        key={item.watch_id}
        className={`flex items-start gap-2 rounded-control border px-2.5 py-2 ${
          triggered ? "border-danger/25 bg-dangerSoft/60" : "border-line bg-surface"
        }`}
      >
        <div className="min-w-0 flex-1">
          <p className={`type-caption font-semibold ${triggered ? "text-danger" : "text-foreground"}`}>
            {triggered ? "Triggered" : "Watching"} · {item.order_id}
          </p>
          <p className={`mt-0.5 type-caption ${triggered ? "text-foreground" : "text-muted"}`}>
            {triggered
              ? `Not moved by ${formatFactoryDate(item.check_date)}`
              : `Inactive by ${formatFactoryDate(item.check_date)} · ${item.status}`}
          </p>
          {triggered && (
            <p className="mt-0.5 type-caption text-subtle">
              Last activity {item.last_activity_date || "—"} · {item.order_status || "—"}
            </p>
          )}
        </div>
        <WatchActions
          item={item}
          disabled={Boolean(cancellingId)}
          menuOpen={menuWatchId === item.watch_id}
          onToggleMenu={() =>
            setMenuWatchId((current) => (current === item.watch_id ? null : item.watch_id))
          }
          onRequestCancel={() => {
            setMenuWatchId(null);
            setCancelError("");
            setPendingCancel(item);
          }}
        />
        {busy && <span className="sr-only">Cancelling…</span>}
      </div>
    );
  }

  function renderSections() {
    return (
      <div className="space-y-3">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <span className="type-overline text-danger">Triggered</span>
            <span className="type-caption text-subtle">{fired.length}</span>
          </div>
          {fired.length === 0 ? (
            <p className="mt-1 type-caption text-subtle">No triggered alerts.</p>
          ) : (
            <div className="space-y-1">{fired.map((item) => renderWatchRow(item, { triggered: true }))}</div>
          )}
        </div>
        <div>
          <div className="mb-1 flex items-center gap-2">
            <span className="type-overline text-warning">Watching</span>
            <span className="type-caption text-subtle">{active.length}</span>
          </div>
          {active.length === 0 ? (
            <p className="mt-1 type-caption text-subtle">No active watches.</p>
          ) : (
            <div className="space-y-1">{active.map((item) => renderWatchRow(item))}</div>
          )}
        </div>
      </div>
    );
  }

  const bellBadge = total > 0 ? (
    <span className="absolute right-0 top-0 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-danger px-0.5 text-[8px] font-bold text-white">{total}</span>
  ) : null;

  if (variant === "bell") {
    return (
      <div ref={rootRef} className="relative">
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          aria-controls={panelId}
          aria-label={`Alerts${total ? ` · ${total}` : ""}`}
          title="Alerts & watches"
          className="focus-ring relative inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-control border border-line bg-surface text-muted transition-colors hover:bg-surfaceMuted hover:text-accentText"
        >
          <BellIcon />
          {bellBadge}
        </button>
        {expanded && (
          <div
            id={panelId}
            className="absolute right-0 top-[calc(100%+0.6rem)] z-40 w-[22rem] max-w-[calc(100vw-1.5rem)] rounded-card border border-line bg-surface p-3 shadow-float"
          >
            <div className="mb-2 flex items-center justify-between">
              <div className="min-w-0">
                <p className="type-overline text-foreground">Alerts & watches</p>
                {total > 0 && (
                  <p className="mt-0.5 type-caption text-muted">
                    {total} active {total === 1 ? "watch" : "watches"}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => setHistoryOpen(true)}
                className="focus-ring rounded-control border border-line px-2 py-1 type-caption font-medium text-muted transition-colors hover:bg-surfaceMuted"
                title="Watch history"
              >
                <HistoryIcon className="mr-1" />
                History
              </button>
            </div>
            {loading ? (
              <p className="mt-2 type-caption text-muted">Loading…</p>
            ) : total === 0 ? (
              <p className="mt-2 type-caption text-subtle">No alerts or active watches.</p>
            ) : (
              <div className="mt-2 max-h-[56vh] overflow-y-auto pr-1">{renderSections()}</div>
            )}
          </div>
        )}
        <Modal
          open={historyOpen}
          onClose={() => setHistoryOpen(false)}
          title="Watch history"
          description="Done and cancelled watches stay here. They are not in Active Watches."
          size="md"
        >
          {done.length === 0 && cancelled.length === 0 ? (
            <p className="type-sm text-muted">No watch history yet.</p>
          ) : (
            <ul className="max-h-72 space-y-2 overflow-y-auto">
              {done.map((item) => (
                <li key={`done-${item.watch_id}`} className="rounded-control border border-line bg-surfaceMuted/50 px-3 py-2 type-sm">
                  <p className="font-medium text-foreground">{item.order_id}</p>
                  <p className="type-caption text-muted">Not moved by {formatFactoryDate(item.check_date)} · done</p>
                </li>
              ))}
              {cancelled.map((item) => (
                <li key={item.watch_id} className="rounded-control border border-line bg-surfaceMuted/50 px-3 py-2 type-sm">
                  <p className="font-medium text-foreground">{item.order_id}</p>
                  <p className="type-caption text-muted">Inactive by {formatFactoryDate(item.check_date)} · cancelled</p>
                </li>
              ))}
            </ul>
          )}
        </Modal>
        <Modal
          open={Boolean(pendingCancel)}
          onClose={() => {
            if (cancellingId) return;
            setPendingCancel(null);
            setCancelError("");
          }}
          title="Cancel watch"
          description="The watch stays in history as CANCELLED. It will not evaluate again."
          size="sm"
          footer={
            <div className="flex flex-wrap justify-end gap-2">
              <Button size="sm" variant="ghost" disabled={Boolean(cancellingId)} onClick={() => { setPendingCancel(null); setCancelError(""); }}>
                Keep watching
              </Button>
              <Button size="sm" variant="danger" disabled={Boolean(cancellingId)} onClick={confirmCancelWatch}>
                {cancellingId ? "Cancelling…" : "Cancel watch"}
              </Button>
            </div>
          }
        >
          <p className="type-sm text-foreground">
            Cancel the watch on{" "}
            <span className="font-semibold">{pendingCancel?.order_id}</span>
            {pendingCancel?.check_date ? ` (inactive by ${formatFactoryDate(pendingCancel.check_date)})` : ""}
            ?
          </p>
          <p className="mt-2 type-caption text-subtle">Watch id {pendingCancel?.watch_id}</p>
          {cancelError && (
            <p className="mt-3 type-caption text-danger" role="alert">{cancelError}</p>
          )}
        </Modal>
      </div>
    );
  }

  return (
    <div ref={rootRef} className={`relative ${compact ? "" : "border-b border-line"}`}>
      <div className={`flex items-start gap-2 ${compact ? "px-0 py-1" : "px-3 py-2"}`}>
        <div className="min-w-0 flex-1">
          {loading ? (
            <div aria-busy="true">
              <p className="type-overline text-foreground">Active Watches</p>
              <p className="mt-1 type-caption text-muted" role="status">Loading…</p>
            </div>
          ) : !hasAlerts ? (
            <div>
              <p className="type-overline text-foreground">Active Watches</p>
              <p className="mt-1 type-caption text-subtle">No active watches</p>
              <p className="mt-0.5 type-caption text-subtle">New watches will appear here.</p>
            </div>
          ) : (
            <button
              type="button"
              aria-expanded={expanded}
              aria-controls={panelId}
              onClick={() => setExpanded((value) => !value)}
              className="focus-ring w-full rounded-control text-left"
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="type-overline text-foreground">Active Watches</span>
                {fired.length > 0 && <span className="type-overline text-danger">Alerts</span>}
                {fired.length > 0 && (
                  <Badge variant="danger" size="sm" dot>
                    {fired.length} triggered
                  </Badge>
                )}
                {active.length > 0 && (
                  <Badge variant="warning" size="sm">
                    {active.length} watching
                  </Badge>
                )}
              </div>
              <p className="mt-1 truncate type-caption text-muted">
                {fired[0]
                  ? `${fired[0].order_id} triggered`
                  : `${active[0]?.order_id} · by ${formatFactoryDate(active[0]?.check_date)}`}
                {fired.length + active.length > 1 ? ` · +${fired.length + active.length - 1}` : ""}
              </p>
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={() => setHistoryOpen(true)}
          className="focus-ring inline-flex h-8 shrink-0 items-center gap-1 rounded-control border border-line bg-surface px-2 type-caption font-medium text-muted transition-colors hover:border-accentText hover:text-accentText"
          aria-label="Watch history"
          title="Watch history"
        >
          <HistoryIcon />
          <span className="hidden sm:inline">History</span>
        </button>
      </div>

      {expanded && hasAlerts && !loading && (
        <div
          id={panelId}
          className={`space-y-3 border-t border-line/70 bg-surfaceMuted/40 ${compact ? "px-0 py-2" : "px-3 py-2"}`}
        >
          {renderSections()}
        </div>
      )}

      <Modal
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        title="Watch history"
        description="Done and cancelled watches stay here. They are not in Active Watches."
        size="md"
      >
        {done.length === 0 && cancelled.length === 0 ? (
          <p className="type-sm text-muted">No watch history yet.</p>
        ) : (
          <ul className="max-h-72 space-y-2 overflow-y-auto">
            {done.map((item) => (
              <li
                key={`done-${item.watch_id}`}
                className="rounded-control border border-line bg-surfaceMuted/50 px-3 py-2 type-sm"
              >
                <p className="font-medium text-foreground">{item.order_id}</p>
                <p className="type-caption text-muted">
                  Not moved by {formatFactoryDate(item.check_date)} · done
                </p>
              </li>
            ))}
            {cancelled.map((item) => (
              <li
                key={item.watch_id}
                className="rounded-control border border-line bg-surfaceMuted/50 px-3 py-2 type-sm"
              >
                <p className="font-medium text-foreground">{item.order_id}</p>
                <p className="type-caption text-muted">
                  Inactive by {formatFactoryDate(item.check_date)} · cancelled
                </p>
              </li>
            ))}
          </ul>
        )}
      </Modal>

      <Modal
        open={Boolean(pendingCancel)}
        onClose={() => {
          if (cancellingId) return;
          setPendingCancel(null);
          setCancelError("");
        }}
        title="Cancel watch"
        description="The watch stays in history as CANCELLED. It will not evaluate again."
        size="sm"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled={Boolean(cancellingId)}
              onClick={() => {
                setPendingCancel(null);
                setCancelError("");
              }}
            >
              Keep watching
            </Button>
            <Button size="sm" variant="danger" disabled={Boolean(cancellingId)} onClick={confirmCancelWatch}>
              {cancellingId ? "Cancelling…" : "Cancel watch"}
            </Button>
          </div>
        }
      >
        <p className="type-sm text-foreground">
          Cancel the watch on{" "}
          <span className="font-semibold">{pendingCancel?.order_id}</span>
          {pendingCancel?.check_date ? ` (inactive by ${formatFactoryDate(pendingCancel.check_date)})` : ""}
          ?
        </p>
        <p className="mt-2 type-caption text-subtle">Watch id {pendingCancel?.watch_id}</p>
        {cancelError && (
          <p className="mt-3 type-caption text-danger" role="alert">
            {cancelError}
          </p>
        )}
      </Modal>
    </div>
  );
}
