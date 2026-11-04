import { useEffect, useState } from "react";
import { advanceFactoryDate, fetchAudit, fetchBriefing, fetchDiscovery, fetchWatches } from "../services/api.js";

function Card({ title, children }) {
  return (
    <section className="rounded-lg border border-ink/10 bg-white p-4 shadow-sm">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-ink/50">{title}</h2>
      <div className="mt-2 text-sm text-ink/70">{children}</div>
    </section>
  );
}

function formatFactoryDate(iso) {
  if (!iso) return "";
  const parts = String(iso).slice(0, 10).split("-");
  if (parts.length !== 3) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const month = months[Number(parts[1]) - 1];
  return month ? `${month} ${Number(parts[2])}` : iso;
}

function FiredAlert({ item }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded border border-ink/10 bg-paper px-2 py-2">
      <p className="text-xs font-semibold text-ink">Standing watch triggered</p>
      <p className="mt-1 text-sm text-ink">
        {item.order_id} has not moved by {formatFactoryDate(item.check_date)}
      </p>
      <ul className="mt-1 space-y-0.5 text-xs">
        <li>Last activity: {item.last_activity_date || "—"}</li>
        <li>Triggered as of: {item.fired_as_of || item.as_of || "—"}</li>
        <li>Status then: {item.order_status || "—"}</li>
        <li>Watch id: {item.watch_id}</li>
      </ul>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="mt-1 text-xs font-medium text-ink underline decoration-brass underline-offset-2"
      >
        {open ? "Hide evidence" : "Why?"}
      </button>
      {open && (
        <p className="mt-2 text-xs text-ink/70">
          On {item.fired_as_of || item.as_of}, the order was still in progress.
          Its last recorded activity was {item.last_activity_date}, before the
          check date of {item.check_date}.
        </p>
      )}
    </li>
  );
}

function IssueRow({ item }) {
  const [open, setOpen] = useState(false);
  const where = item.order_id || item.stage || "";
  return (
    <li className="rounded border border-ink/10 bg-paper px-2 py-2">
      <p className="text-xs font-semibold text-ink">
        P{item.priority} · {item.title || item.issue_type}
      </p>
      <p className="mt-0.5 text-xs text-ink/70">
        {where}
        {item.evidence?.flags?.length ? ` · ${item.evidence.flags.join(", ")}` : ""}
      </p>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="mt-1 text-xs font-medium text-ink underline decoration-brass underline-offset-2"
      >
        {open ? "Hide evidence" : "Why?"}
      </button>
      {open && (
        <pre className="trace-pre mt-1 max-h-40 overflow-auto text-[11px] text-ink/80">
          {JSON.stringify(
            {
              issue_id: item.issue_id,
              issue_type: item.issue_type,
              priority: item.priority,
              rule: item.rule,
              inputs: item.inputs,
              result: item.result,
              source_file: item.source_file,
              evidence: item.evidence,
            },
            null,
            2,
          )}
        </pre>
      )}
    </li>
  );
}

export default function Sidebar({ refreshToken = 0, onOpenBriefing, onDateChanged }) {
  const [briefing, setBriefing] = useState(null);
  const [audit, setAudit] = useState([]);
  const [watches, setWatches] = useState({ fired: [], active: [], cancelled: [] });
  const [discovery, setDiscovery] = useState({ issues: [] });
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(true);
  const [advancing, setAdvancing] = useState(false);
  const [advanceError, setAdvanceError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setRefreshing(true);
    setError("");
    // The watch check records the alert before the audit feed is fetched.
    fetchWatches()
      .then(async (board) => {
        const [brief, log, issues] = await Promise.all([fetchBriefing(), fetchAudit(6), fetchDiscovery(5)]);
        if (cancelled) return;
        setBriefing(brief);
        setAudit(log.items || []);
        setWatches({
          fired: board.fired || [],
          active: board.active || [],
          cancelled: board.cancelled || [],
        });
        setDiscovery(issues);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setRefreshing(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  async function advanceDate() {
    setAdvancing(true);
    setAdvanceError("");
    try {
      await advanceFactoryDate(briefing.factory_today);
    } catch (err) {
      setAdvanceError(err.message);
    } finally {
      setRefreshing(true);
      onDateChanged();
      setAdvancing(false);
    }
  }

  const metrics = briefing?.dashboard?.metrics || {};
  const fired = watches.fired || [];
  const active = watches.active || [];
  const cancelledWatches = watches.cancelled || [];

  return (
    <aside className="space-y-3">
      <Card title="Morning briefing">
        <button type="button" onClick={onOpenBriefing} className="mb-3 w-full rounded-md bg-ink px-3 py-2 text-sm font-semibold text-paper hover:bg-ink/90">Open morning briefing ↗</button>
        {error && <p role="alert">{error}</p>}
        {!error && !briefing && <p>Loading structured facts…</p>}
        {briefing && (
          <ul className="space-y-1">
            <li>Factory date {briefing.factory_today}</li>
            <li>
              {metrics.attention ?? 0} orders need attention (overdue {metrics.overdue ?? 0},
              stalled {metrics.stalled ?? 0})
            </li>
            <li>IN_PROGRESS: {briefing.in_progress_order_count}</li>
            {briefing.suspended_workshops?.length > 0 && (
              <li>
                Suspended: {briefing.suspended_workshops.map((w) => w.name).join(", ")}
              </li>
            )}
          </ul>
        )}
        {briefing && (
          <button
            type="button"
            className="mt-2 rounded border border-ink/20 px-2 py-1 text-xs font-semibold disabled:opacity-50"
            disabled={refreshing || advancing}
            onClick={advanceDate}
          >
            {advancing ? "Advancing…" : "Advance one day"}
          </button>
        )}
        {advanceError && <p className="mt-1 text-xs text-red-700" role="alert">{advanceError}</p>}
      </Card>
      <Card title="Top issues">
        {(discovery.issues || []).length === 0 && (
          <p>
            No V1 discovery issues on the current tables, or the API is still loading.
            Ask in chat what to be concerned about.
          </p>
        )}
        {(discovery.issues || []).length > 0 && (
          <ul className="space-y-2">
            {discovery.issues.map((item) => (
              <IssueRow key={item.issue_id} item={item} />
            ))}
          </ul>
        )}
      </Card>
      <Card title="Triggered alerts">
        {fired.length === 0 && (
          <p>
            No standing watches have fired. Local alerts only. Ask in chat to cancel
            one after it appears.
          </p>
        )}
        {fired.length > 0 && (
          <ul className="space-y-2">
            {fired.map((item) => (
              <FiredAlert key={item.watch_id} item={item} />
            ))}
          </ul>
        )}
      </Card>
      <Card title="Active watches">
        {active.length === 0 && (
          <p>
            No active watches. Ask in chat to watch an in-progress order. This is not a
            calendar reminder.
          </p>
        )}
        {active.length > 0 && (
          <ul className="space-y-1 text-xs">
            {active.map((item) => (
              <li key={item.watch_id}>
                {item.order_id} · inactive by {formatFactoryDate(item.check_date)} ·{" "}
                {item.status}
                <span className="block text-ink/45">
                  Ask in chat to cancel watch {item.watch_id}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Watch history">
        {cancelledWatches.length === 0 && (
          <p>Cancelled watches stay here for audit. They are not deleted.</p>
        )}
        {cancelledWatches.length > 0 && (
          <ul className="space-y-1 text-xs">
            {cancelledWatches.map((item) => (
              <li key={item.watch_id}>
                {item.order_id} · inactive by {formatFactoryDate(item.check_date)} ·
                cancelled
                {item.watch_id ? ` · id ${item.watch_id}` : ""}
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Card title="Recent actions">
        {audit.length === 0 && (
          <p>No local audit rows yet. Drafts, notes, reminders, and watches will appear here.</p>
        )}
        {audit.length > 0 && (
          <ul className="space-y-1 text-xs">
            {audit.slice(0, 5).map((row) => (
              <li key={row.id}>
                {row.tool || row.event_type}
                {row.target ? ` · ${row.target}` : ""} · {row.execution_status || row.confirmation_status}
                {row.event_type === "watch_fired" && ` · ${row.factory_today}`}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs">Email is never actually sent (no SMTP).</p>
      </Card>
    </aside>
  );
}
