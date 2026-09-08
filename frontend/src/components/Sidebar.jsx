import { useEffect, useState } from "react";
import { fetchAudit, fetchBriefing, fetchDiscovery, fetchWatches } from "../services/api.js";

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
  const snapshot = item.snapshot || {};
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
        <pre className="trace-pre mt-1 max-h-40 overflow-auto text-[11px] text-ink/80">
          {JSON.stringify(
            {
              order_id: item.order_id,
              condition_type: item.condition_type,
              check_date: item.check_date,
              as_of: snapshot.as_of || item.as_of,
              last_activity_date: item.last_activity_date,
              order_status: item.order_status,
              current_stage: item.current_stage,
              fired_at: item.fired_at,
              formula: snapshot.formula,
            },
            null,
            2,
          )}
        </pre>
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

export default function Sidebar({ refreshToken = 0 }) {
  const [briefing, setBriefing] = useState(null);
  const [audit, setAudit] = useState([]);
  const [watches, setWatches] = useState({ fired: [], active: [], cancelled: [] });
  const [discovery, setDiscovery] = useState({ issues: [] });
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchBriefing(), fetchAudit(6), fetchWatches(), fetchDiscovery(5)])
      .then(([brief, log, board, issues]) => {
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
      });
    return () => {
      cancelled = true;
    };
  }, [refreshToken]);

  const flags = briefing?.at_risk?.flag_counts || {};
  const fired = watches.fired || [];
  const active = watches.active || [];
  const cancelledWatches = watches.cancelled || [];

  return (
    <aside className="space-y-3">
      <Card title="Morning briefing">
        {error && <p>API offline — ask in chat once the backend is running.</p>}
        {!error && !briefing && <p>Loading structured facts…</p>}
        {briefing && (
          <ul className="space-y-1">
            <li>Factory date {briefing.factory_today}</li>
            <li>
              {briefing.at_risk?.count} orders need attention (overdue {flags.OVERDUE || 0},
              stalled {flags.STALLED || 0}, tight {flags.TIGHT_DEADLINE || 0})
            </li>
            <li>IN_PROGRESS: {briefing.in_progress_order_count}</li>
            {briefing.suspended_workshops?.length > 0 && (
              <li>
                Suspended: {briefing.suspended_workshops.map((w) => w.name).join(", ")}
              </li>
            )}
          </ul>
        )}
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
              </li>
            ))}
          </ul>
        )}
        <p className="mt-2 text-xs">Email is never actually sent (no SMTP).</p>
      </Card>
    </aside>
  );
}
