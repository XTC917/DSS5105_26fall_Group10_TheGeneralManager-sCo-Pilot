import { useCallback, useEffect, useState } from "react";
import MorningBriefingModal from "./MorningBriefingModal.jsx";
import { loadOverviewData, peekOverviewCache } from "../services/overviewCache.js";
import { Button, Skeleton } from "./ui/index.js";

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

function IssueRow({ item }) {
  const [open, setOpen] = useState(false);
  const where = item.order_id || item.stage || "";
  return (
    <li className="rounded-card border border-line bg-surface px-3 py-3 shadow-xs">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="type-sm font-semibold text-foreground">
            <span className="mr-1.5 inline-flex rounded-control bg-dangerSoft px-1.5 py-0.5 type-caption font-semibold text-danger">
              P{item.priority}
            </span>
            {item.title || item.issue_type}
          </p>
          <p className="mt-1 type-caption text-muted">
            {where}
            {item.evidence?.flags?.length ? ` · ${item.evidence.flags.join(", ")}` : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="focus-ring shrink-0 rounded-control px-2 py-1 type-caption font-medium text-accentText hover:bg-accentSoft/50"
        >
          {open ? "Hide" : "Why?"}
        </button>
      </div>
      {open && (
        <pre className="trace-pre mt-2 max-h-40 overflow-auto rounded-control bg-surfaceMuted p-2 type-caption text-muted">
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

  const applyPayload = useCallback(
    (payload, nextStatus) => {
      setBriefing(payload.briefing);
      setDiscovery(payload.discovery);
      setFetchedAt(payload.fetchedAt || Date.now());
      setError(payload.error || "");
      setStatus(nextStatus);
      if (payload.briefing?.factory_today) {
        onFactoryDate?.(payload.briefing.factory_today);
      }
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
          <span className="type-caption text-subtle">{issues.length} open</span>
        </div>
        {busy && (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full rounded-card" />
            <Skeleton className="h-16 w-full rounded-card" />
          </div>
        )}
        {!busy && issues.length === 0 && (
          <p className="rounded-card border border-line bg-surface px-4 py-5 type-sm text-muted shadow-xs">
            No discovery issues on the current tables. Ask in chat what to be concerned about.
          </p>
        )}
        {!busy && issues.length > 0 && (
          <ul className="grid gap-2 md:grid-cols-2">
            {issues.map((item) => (
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
            <p className="truncate type-caption text-subtle">
              {showingWeek && briefing?.last_week
                ? `${briefing.last_week.start} – ${briefing.last_week.end}`
                : briefing?.factory_today
                  ? `Factory date ${formatFactoryDate(briefing.factory_today)}`
                  : "Loading…"}
            </p>
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
