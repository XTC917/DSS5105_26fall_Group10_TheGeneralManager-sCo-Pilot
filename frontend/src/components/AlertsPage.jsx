import { useState } from "react";
import { confirmAction, finishWatch } from "../services/api.js";
import { partitionWatches } from "../services/watchDisplay.js";

function formatFactoryDate(iso) {
  if (!iso) return "";
  const parts = String(iso).slice(0, 10).split("-");
  if (parts.length !== 3) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const month = months[Number(parts[1]) - 1];
  return month ? `${month} ${Number(parts[2])}` : iso;
}

function Chevron({ open }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true"
      className={`transition-transform ${open ? "rotate-90" : ""}`}>
      <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/**
 * Full Alerts page: a stack of three collapsible groups.
 *   1) Triggered (newest first, expanded by default) — Finish or Cancel
 *   2) Watching  — Cancel
 *   3) Closed    — Cancelled + Finished/handled (tagged)
 * Triggered can be collapsed by the user; Watching and Closed stay available.
 */
export default function AlertsPage({ watches, loading = false, onWatchChanged }) {
  const { triggered, watching, done, cancelled, finished } = partitionWatches(watches);
  const [open, setOpen] = useState({ triggered: true, watching: true, closed: true });
  const [busyKey, setBusyKey] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const closed = [
    ...cancelled.map((item) => ({ ...item, _kind: "cancelled" })),
    ...finished.map((item) => ({ ...item, _kind: "finished" })),
    ...done.map((item) => ({ ...item, _kind: "finished" })),
  ];

  const toggle = (key) => setOpen((prev) => ({ ...prev, [key]: !prev[key] }));

  async function runCancel(item) {
    const key = `cancel-${item.watch_id}`;
    setBusyKey(key);
    setError("");
    setNotice("");
    try {
      const result = await confirmAction({
        type: "cancel_watch",
        watch_id: Number(item.watch_id),
        order_id: item.order_id,
      });
      if (!result?.ok) {
        throw new Error(result?.error?.message || result?.summary || "Could not cancel the watch.");
      }
      setNotice(`Watch on ${item.order_id} cancelled.`);
      onWatchChanged?.();
    } catch (err) {
      setError(err.message || "Could not cancel the watch.");
    } finally {
      setBusyKey(null);
    }
  }

  async function runFinish(item) {
    const key = `finish-${item.watch_id}`;
    setBusyKey(key);
    setError("");
    setNotice("");
    try {
      const result = await finishWatch(item.watch_id);
      if (!result?.ok) {
        throw new Error(result?.detail || "Could not finish the watch.");
      }
      setNotice(`Watch on ${item.order_id} marked finished.`);
      onWatchChanged?.();
    } catch (err) {
      setError(err.message || "Could not finish the watch.");
    } finally {
      setBusyKey(null);
    }
  }

  function renderActions(item, kind) {
    const cancelKey = `cancel-${item.watch_id}`;
    const finishKey = `finish-${item.watch_id}`;
    const busy = busyKey === cancelKey || busyKey === finishKey;
    return (
      <div className="flex shrink-0 items-center gap-1.5">
        {kind === "triggered" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => runFinish(item)}
            className="focus-ring rounded-control bg-ink px-2.5 py-1 type-caption font-medium text-paper disabled:opacity-50"
          >
            {busyKey === finishKey ? "Finishing…" : "Finish"}
          </button>
        )}
        {kind !== "closed" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => runCancel(item)}
            className="focus-ring rounded-control border border-line px-2.5 py-1 type-caption font-medium text-danger hover:bg-dangerSoft disabled:opacity-50"
          >
            {busyKey === cancelKey ? "Cancelling…" : "Cancel"}
          </button>
        )}
      </div>
    );
  }

  function renderRow(item, kind) {
    const triggered = kind === "triggered";
    const closedRow = kind === "closed";
    return (
      <div
        key={item.watch_id}
        className={`flex items-start gap-2 rounded-control border px-3 py-2 ${
          triggered ? "border-danger/25 bg-dangerSoft/50" : "border-line bg-surface"
        }`}
      >
        <div className="min-w-0 flex-1">
          <p className={`type-sm font-semibold ${triggered ? "text-danger" : "text-foreground"}`}>{item.order_id}</p>
          <p className="mt-0.5 type-caption text-muted">
            {triggered
              ? `Triggered · not moved by ${formatFactoryDate(item.check_date)}`
              : kind === "watching"
                ? `Watching · inactive by ${formatFactoryDate(item.check_date)}${item.status ? ` · ${item.status}` : ""}`
                : `${item._kind === "cancelled" ? "Cancelled" : "Finished"}${item.check_date ? ` · ${formatFactoryDate(item.check_date)}` : ""}`}
          </p>
        </div>
        {closedRow ? (
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 type-caption font-medium ${
              item._kind === "cancelled" ? "bg-dangerSoft text-danger" : "bg-surfaceMuted text-muted"
            }`}
          >
            {item._kind === "cancelled" ? "Cancelled" : "Finished"}
          </span>
        ) : (
          renderActions(item, kind)
        )}
      </div>
    );
  }

  function Section({ title, count, name, kind, items, dangerAccent }) {
    const isOpen = open[name];
    return (
      <section className="rounded-card border border-line bg-surface">
        <button
          type="button"
          onClick={() => toggle(name)}
          aria-expanded={isOpen}
          className="focus-ring flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left"
        >
          <span className="flex items-center gap-2">
            <Chevron open={isOpen} />
            <span className={`type-overline ${dangerAccent ? "text-danger" : "text-foreground"}`}>{title}</span>
            <span className="rounded-full bg-surfaceMuted px-2 py-0.5 type-caption text-muted">{count}</span>
          </span>
        </button>
        {isOpen && (
          <div className="space-y-1.5 border-t border-line/70 px-3 py-2">
            {items.length === 0 ? (
              <p className="type-caption text-subtle">Nothing here.</p>
            ) : (
              items.map((item) => renderRow(item, kind))
            )}
          </div>
        )}
      </section>
    );
  }

  if (loading) {
    return <p className="type-sm text-muted">Loading watches…</p>;
  }

  return (
    <div className="space-y-3">
      {error && (
        <p className="rounded-control border border-danger/30 bg-dangerSoft px-3 py-2 type-caption text-danger" role="alert">{error}</p>
      )}
      {notice && (
        <p className="rounded-control border border-line bg-surfaceMuted px-3 py-2 type-caption text-foreground" role="status">{notice}</p>
      )}

      <Section title="Triggered" name="triggered" kind="triggered" items={triggered} count={triggered.length} dangerAccent />
      <Section title="Watching" name="watching" kind="watching" items={watching} count={watching.length} />
      <Section title="Cancelled / Finished" name="closed" kind="closed" items={closed} count={closed.length} />
    </div>
  );
}
