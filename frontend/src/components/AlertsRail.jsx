import { useEffect, useId, useRef, useState } from "react";
import { Badge, Modal } from "./ui/index.js";

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

/**
 * Compact alerts strip above Conversations.
 * Hidden (no layout cost) when there are no active watches or fired alerts.
 */
export default function AlertsRail({
  watches = { fired: [], active: [], cancelled: [] },
  loading = false,
  compact = false,
  /** When true, keep a minimal History affordance even with zero alerts (mobile drawer). */
  persistHistory = false,
}) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  const rootRef = useRef(null);

  const fired = watches.fired || [];
  const active = watches.active || [];
  const cancelled = watches.cancelled || [];
  const hasAlerts = fired.length > 0 || active.length > 0;
  const hasHistory = cancelled.length > 0;

  useEffect(() => {
    if (!expanded) return undefined;
    function onPointerDown(event) {
      if (!rootRef.current?.contains(event.target)) setExpanded(false);
    }
    function onKeyDown(event) {
      if (event.key === "Escape") setExpanded(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [expanded]);

  if (loading && !hasAlerts && !hasHistory && !persistHistory) {
    return null;
  }

  if (!hasAlerts && !hasHistory && !persistHistory) {
    return null;
  }

  return (
    <div ref={rootRef} className={`relative ${compact ? "" : "border-b border-line"}`}>
      <div className={`flex items-start gap-2 ${compact ? "px-0 py-1" : "px-3 py-2"}`}>
        <div className="min-w-0 flex-1">
          {!hasAlerts ? (
            <p className="type-caption text-subtle">{hasHistory || persistHistory ? "No active alerts" : "No alerts"}</p>
          ) : (
            <button
              type="button"
              aria-expanded={expanded}
              aria-controls={panelId}
              onClick={() => setExpanded((value) => !value)}
              className="focus-ring w-full rounded-control text-left"
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="type-overline text-danger">Alerts</span>
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
                {(fired.length + active.length) > 1 ? " · +" + (fired.length + active.length - 1) : ""}
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

      {expanded && hasAlerts && (
        <div
          id={panelId}
          className={`space-y-2 border-t border-line/70 bg-surfaceMuted/40 ${compact ? "px-0 py-2" : "px-3 py-2"}`}
        >
          {fired.map((item) => (
            <div key={item.watch_id} className="rounded-control border border-danger/25 bg-dangerSoft/60 px-2.5 py-2">
              <p className="type-caption font-semibold text-danger">Triggered · {item.order_id}</p>
              <p className="mt-0.5 type-caption text-foreground">
                Not moved by {formatFactoryDate(item.check_date)}
              </p>
              <p className="mt-0.5 type-caption text-subtle">
                Last activity {item.last_activity_date || "—"} · {item.order_status || "—"}
              </p>
            </div>
          ))}
          {active.map((item) => (
            <div key={item.watch_id} className="rounded-control border border-line bg-surface px-2.5 py-2">
              <p className="type-caption font-semibold text-foreground">Watching · {item.order_id}</p>
              <p className="mt-0.5 type-caption text-muted">
                Inactive by {formatFactoryDate(item.check_date)} · {item.status}
              </p>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        title="Watch history"
        description="Cancelled watches stay here for audit. They are not deleted."
        size="md"
      >
        {cancelled.length === 0 ? (
          <p className="type-sm text-muted">No cancelled watches yet.</p>
        ) : (
          <ul className="max-h-72 space-y-2 overflow-y-auto">
            {cancelled.map((item) => (
              <li
                key={item.watch_id}
                className="rounded-control border border-line bg-surfaceMuted/50 px-3 py-2 type-sm"
              >
                <p className="font-medium text-foreground">{item.order_id}</p>
                <p className="type-caption text-muted">
                  Inactive by {formatFactoryDate(item.check_date)} · cancelled
                  {item.watch_id ? ` · id ${item.watch_id}` : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Modal>
    </div>
  );
}
