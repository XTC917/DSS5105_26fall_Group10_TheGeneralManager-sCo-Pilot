import { useCallback, useEffect, useState } from "react";
import MorningBriefingModal from "./MorningBriefingModal.jsx";
import { loadOverviewData, peekOverviewCache } from "../services/overviewCache.js";
import { Button, Skeleton } from "./ui/index.js";

function dayGap(later, earlier) {
  const parse = (iso) => Date.parse(`${String(iso).slice(0, 10)}T00:00:00Z`);
  const span = parse(later) - parse(earlier);
  return Number.isNaN(span) ? 0 : Math.round(span / 86400000);
}

function formatFactoryDate(iso) {
  if (!iso) return "";
  const parts = String(iso).slice(0, 10).split("-");
  if (parts.length !== 3) return iso;
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const month = months[Number(parts[1]) - 1];
  return month ? `${Number(parts[2])} ${month} ${parts[0]}` : iso;
}

function Chevron({ dir = "left" }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      {dir === "left" ? (
        <path d="M15 6l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      ) : (
        <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      )}
    </svg>
  );
}

const PRIORITY_STYLE = {
  1: {
    color: "rgb(var(--priority-1))",
    backgroundColor: "rgb(var(--priority-1-soft))",
    borderColor: "rgb(var(--priority-1))",
  },
  2: {
    color: "rgb(var(--priority-2))",
    backgroundColor: "rgb(var(--priority-2-soft))",
    borderColor: "rgb(var(--priority-2))",
  },
  3: {
    color: "rgb(var(--priority-3))",
    backgroundColor: "rgb(var(--priority-3-soft))",
    borderColor: "rgb(var(--priority-3))",
  },
};

function stageName(stage) {
  return String(stage || "").replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function IssueRow({ item }) {
  const [open, setOpen] = useState(false);
  const order = item.evidence?.order;
  const computed = item.evidence?.computed || {};
  const where = item.order_id || item.stage || "";
  return (
    <li className="rounded-card border border-line bg-surface shadow-xs">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="flex w-full flex-wrap items-start justify-between gap-2 px-3 py-3 text-left"
      >
        <div className="min-w-0">
          <p className="type-sm font-semibold text-foreground">
            <span
              className="mr-1.5 inline-flex rounded-control border px-1.5 py-0.5 type-caption font-semibold"
              style={PRIORITY_STYLE[item.priority] || PRIORITY_STYLE[3]}
            >
              P{item.priority}
            </span>
            {item.title || item.issue_type}
          </p>
          <p className="mt-1 type-caption text-muted">{where}</p>
        </div>
        <span className="shrink-0 type-caption font-medium text-accentText">{open ? "Hide" : "Details"}</span>
      </button>
      {open && order && (
        <div className="border-t border-line px-3 py-3">
          <p className="type-sm text-foreground">
            {order.customer} · {order.product} · {order.pieces} pieces
          </p>
          <p className="mt-1 type-caption text-muted">
            Due {order.due_date || "unknown"} · Stage {stageName(order.current_stage)} · Last activity{" "}
            {order.last_activity_date || "unknown"}
          </p>
          <p className="mt-1 type-caption text-muted">
            {computed.working_days_since_last_activity ?? "?"} working days without activity
            {computed.days_left != null ? ` · about ${computed.days_left} working days of work left` : ""}
          </p>
          {item.evidence?.flags?.includes("STALLED") && (
            <p className="mt-2 type-caption text-subtle">
              Stalled means this order is still in progress and has not moved for at least 3 working days.
            </p>
          )}
        </div>
      )}
      {open && !order && item.stage && (
        <div className="border-t border-line px-3 py-3">
          <p className="type-sm text-foreground">{item.summary}</p>
          <p className="mt-1 type-caption text-muted">
            Last working day {item.evidence?.last_working_date}: {item.evidence?.last_day_pieces} pieces, against a
            30-day median of {item.evidence?.lookback_median}.
          </p>
        </div>
      )}
    </li>
  );
}

/**
 * Overview / Insights — Top Issues + Morning/Weekly briefing carousel.
 * Alerts / watches / audit live in the left rail, not here.
 */
export default function Sidebar({ refreshToken = 0, onFactoryDate }) {
  const cached = peekOverviewCache();
  const [briefing, setBriefing] = useState(cached?.briefing || null);
  const [discovery, setDiscovery] = useState(cached?.discovery || null);
  const [error, setError] = useState(cached?.error || "");
  const [status, setStatus] = useState(cached?.briefing ? "cached" : "idle");
  const [fetchedAt, setFetchedAt] = useState(cached?.fetchedAt || 0);
  const [panel, setPanel] = useState("today");
  const [modalOpen, setModalOpen] = useState(false);
  const [issuesOpen, setIssuesOpen] = useState(true);
  const [priorities, setPriorities] = useState(() => new Set());

  const applyPayload = useCallback(
    (payload, nextStatus) => {
      setBriefing(payload.briefing);
      setDiscovery(payload.discovery);
      setFetchedAt(payload.fetchedAt || Date.now());
      setError(payload.error || "");
      setStatus(nextStatus);
      const clock = payload.briefing?.clock_date || payload.briefing?.factory_today;
      if (clock) onFactoryDate?.(clock);
    },
    [onFactoryDate],
  );

  const refresh = useCallback(
    async ({ force = true, background = false } = {}) => {
      const hasCache = Boolean(peekOverviewCache()?.briefing);
      if (!background || !hasCache) {
        setStatus(hasCache ? "refreshing" : "loading");
      } else {
        setStatus("refreshing");
      }
      try {
        const payload = await loadOverviewData({ force });
        applyPayload(payload, "ready");
      } catch (err) {
        const fallback = peekOverviewCache();
        if (fallback?.briefing) {
          applyPayload(fallback, "stale");
          setError(err.message || "Could not refresh overview.");
        } else {
          setError(err.message || "Could not load overview.");
          setStatus("error");
        }
      }
    },
    [applyPayload],
  );

  useEffect(() => {
    let cancelled = false;
    const existing = peekOverviewCache();
    if (existing?.briefing) {
      applyPayload(existing, "cached");
      refresh({ force: true, background: true }).then(() => {
        if (cancelled) return;
      });
    } else {
      refresh({ force: false, background: false });
    }
    return () => {
      cancelled = true;
    };
  }, [applyPayload, refresh, refreshToken]);

  const issues = discovery?.issues || [];
  const visibleIssues = issues.filter((item) => priorities.has(Number(item.priority)));
  const latestDataDate = briefing?.latest_data_date || "";
  const clockDate = briefing?.clock_date || briefing?.factory_today || "";
  const dataHoldNote = latestDataDate && dayGap(clockDate, latestDataDate) >= 2
    ? `Data is current through ${formatFactoryDate(latestDataDate)}. Records after that date have not been updated.`
    : "";

  function togglePriority(priority) {
    setPriorities((current) => {
      const next = new Set(current);
      if (next.has(priority)) next.delete(priority);
      else next.add(priority);
      return next;
    });
  }
  const hasWeekly = Boolean(briefing?.last_week);
  const showingWeek = panel === "week" && hasWeekly;
  const busy = status === "loading" && !briefing;

  function goPrev() {
    if (showingWeek) setPanel("today");
  }

  function goNext() {
    if (!showingWeek && hasWeekly) setPanel("week");
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 md:space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="type-overline text-accentText">Insights</p>
          <h2 className="type-h2 text-foreground">Overview</h2>
          <p className="type-sm text-muted">Top issues and the factory morning / weekly briefing.</p>
        </div>
        <div className="flex items-center gap-2">
          {status === "refreshing" && (
            <span className="type-caption text-subtle" role="status">
              Refreshing…
            </span>
          )}
          {status === "stale" && (
            <span className="rounded-control border border-warning/30 bg-warningSoft px-2 py-1 type-caption text-warning">
              Showing cached data
            </span>
          )}
          {status === "cached" && fetchedAt > 0 && (
            <span className="type-caption text-subtle">Cached · updating</span>
          )}
          <Button size="sm" variant="secondary" disabled={status === "loading" || status === "refreshing"} onClick={() => refresh({ force: true })}>
            Refresh
          </Button>
        </div>
      </div>

      {error && status === "error" && (
        <div className="rounded-card border border-danger/30 bg-dangerSoft px-4 py-3" role="alert">
          <p className="type-sm text-danger">{error}</p>
          <button type="button" onClick={() => refresh({ force: true })} className="mt-2 type-caption font-medium text-danger underline">
            Try again
          </button>
        </div>
      )}

      {error && status === "stale" && (
        <p className="rounded-control border border-warning/30 bg-warningSoft px-3 py-2 type-caption text-warning" role="status">
          Could not refresh — showing last loaded data. {error}
        </p>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h3 className="type-h3 text-foreground">Top issues</h3>
          <div className="flex items-center gap-1">
            <span className="type-caption text-subtle">{visibleIssues.length} open</span>
            <button
              type="button"
              aria-expanded={issuesOpen}
              aria-label={issuesOpen ? "Hide top issues" : "Show top issues"}
              onClick={() => setIssuesOpen((open) => !open)}
              className="focus-ring inline-flex h-6 w-6 items-center justify-center rounded-control text-subtle transition-colors hover:bg-surfaceMuted hover:text-foreground"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
                className={`transition-transform duration-[var(--dur-fast)] ${issuesOpen ? "rotate-180" : ""}`}
              >
                <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
        </div>
        {issuesOpen && (
          <div className="flex flex-wrap gap-1.5">
            {[1, 2, 3].map((priority) => {
              const selected = priorities.has(priority);
              return (
                <button
                  key={priority}
                  type="button"
                  aria-pressed={selected}
                  onClick={() => togglePriority(priority)}
                  className={`focus-ring rounded-control border px-2 py-0.5 type-caption font-semibold transition-opacity ${
                    selected ? "opacity-100" : "opacity-40 hover:opacity-70"
                  }`}
                  style={PRIORITY_STYLE[priority]}
                >
                  P{priority}
                </button>
              );
            })}
          </div>
        )}
        {issuesOpen && busy && (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full rounded-card" />
            <Skeleton className="h-16 w-full rounded-card" />
          </div>
        )}
        {issuesOpen && !busy && issues.length === 0 && (
          <p className="rounded-card border border-line bg-surface px-4 py-5 type-sm text-muted shadow-xs">
            No discovery issues on the current tables. Ask in chat what to be concerned about.
          </p>
        )}
        {issuesOpen && !busy && issues.length > 0 && priorities.size > 0 && visibleIssues.length === 0 && (
          <p className="rounded-card border border-line bg-surface px-4 py-5 type-sm text-muted shadow-xs">
            No issues in the selected priorities.
          </p>
        )}
        {issuesOpen && !busy && visibleIssues.length > 0 && (
          <ul className="grid gap-2">
            {visibleIssues.map((item) => (
              <IssueRow key={item.issue_id} item={item} />
            ))}
          </ul>
        )}
      </section>

      <section className="overflow-hidden rounded-card border border-line bg-surface shadow-xs">
        <div className="flex items-center gap-2 border-b border-line px-2 py-2 sm:px-3">
          <button
            type="button"
            aria-label="Show morning briefing"
            disabled={!showingWeek}
            onClick={goPrev}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-control text-foreground transition-colors hover:bg-surfaceMuted disabled:cursor-not-allowed disabled:opacity-30"
          >
            <Chevron dir="left" />
          </button>
          <div className="min-w-0 flex-1 text-center">
            <p className="type-overline text-accentText">Factory briefing</p>
            <h3 className="truncate type-h3 text-foreground">
              {showingWeek ? "Weekly briefing" : "Morning briefing"}
            </h3>
            {dataHoldNote && (
              <p className="mt-1 type-caption text-muted">{dataHoldNote}</p>
            )}
            {showingWeek && briefing?.last_week && (
              <p className="truncate type-caption text-subtle">
                {briefing.last_week.start} – {briefing.last_week.end}
              </p>
            )}
          </div>
          <button
            type="button"
            aria-label="Show weekly briefing"
            disabled={showingWeek || !hasWeekly}
            onClick={goNext}
            className="focus-ring inline-flex h-9 w-9 items-center justify-center rounded-control text-foreground transition-colors hover:bg-surfaceMuted disabled:cursor-not-allowed disabled:opacity-30"
          >
            <Chevron dir="right" />
          </button>
        </div>

        <div className="flex items-center justify-center gap-1.5 border-b border-line/70 py-2">
          <button
            type="button"
            aria-label="Morning"
            aria-current={!showingWeek ? "true" : undefined}
            onClick={() => setPanel("today")}
            className={`h-1.5 w-6 rounded-full transition-colors ${!showingWeek ? "bg-accent" : "bg-line hover:bg-muted"}`}
          />
          <button
            type="button"
            aria-label="Weekly"
            disabled={!hasWeekly}
            aria-current={showingWeek ? "true" : undefined}
            onClick={() => hasWeekly && setPanel("week")}
            className={`h-1.5 w-6 rounded-full transition-colors disabled:opacity-30 ${showingWeek ? "bg-accent" : "bg-line hover:bg-muted"}`}
          />
        </div>

        <div className="min-h-[20rem] p-3 sm:p-4 md:p-5">
          {busy && (
            <div className="space-y-3 py-6">
              <Skeleton className="mx-auto h-4 w-48" />
              <Skeleton className="h-40 w-full rounded-card" />
              <Skeleton className="h-24 w-full rounded-card" />
            </div>
          )}
          {!busy && briefing && (
            <MorningBriefingModal
              key={`${showingWeek ? "week" : "today"}-${fetchedAt}`}
              embedded
              initialPanel={showingWeek ? "week" : "today"}
              data={briefing}
              onClose={() => setModalOpen(false)}
              onAlertCreated={() => refresh({ force: true })}
            />
          )}
          {!busy && !briefing && !error && (
            <p className="py-10 text-center type-sm text-muted">Briefing is unavailable.</p>
          )}
        </div>

        {!busy && briefing && (
          <div className="border-t border-line px-4 py-3">
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className="focus-ring type-caption font-medium text-accentText underline underline-offset-2"
            >
              Open fullscreen briefing
            </button>
          </div>
        )}
      </section>

      {modalOpen && (
        <MorningBriefingModal
          key={`modal-${panel}`}
          initialPanel={showingWeek ? "week" : "today"}
          onClose={() => setModalOpen(false)}
          refreshToken={refreshToken}
          onAlertCreated={() => refresh({ force: true })}
        />
      )}
    </div>
  );
}
