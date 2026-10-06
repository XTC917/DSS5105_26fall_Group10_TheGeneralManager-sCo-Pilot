import { getFlagCounts, getFlaggedStages, num, overallStatus, STATUS_META } from "./briefingSummary.js";

function Donut({ atRisk, active }) {
  const r = 26;
  const c = 2 * Math.PI * r;
  const frac = active > 0 ? Math.min(atRisk / active, 1) : 0;
  return (
    <svg width="72" height="72" viewBox="0 0 72 72" role="img" aria-label={`${atRisk} of ${active} orders need attention`}>
      <circle cx="36" cy="36" r={r} fill="none" strokeWidth="9" className="stroke-ink/10" />
      <circle
        cx="36" cy="36" r={r} fill="none" strokeWidth="9" strokeLinecap="round"
        strokeDasharray={`${frac * c} ${c}`}
        transform="rotate(-90 36 36)"
        className={atRisk > 0 ? "stroke-red-500" : "stroke-emerald-500"}
      />
      <text x="36" y="34" textAnchor="middle" className="fill-ink text-sm font-bold">{atRisk}</text>
      <text x="36" y="46" textAnchor="middle" className="fill-ink/50" fontSize="9">at risk</text>
    </svg>
  );
}

function Kpi({ label, value, accent }) {
  return (
    <div className="rounded-md bg-paper px-2.5 py-2">
      <p className="text-[10px] font-medium uppercase tracking-wide text-ink/50">{label}</p>
      <p className={`text-xl font-bold leading-tight ${accent || "text-ink"}`}>{value}</p>
    </div>
  );
}

export default function BriefingCard({ briefing, loading, error, onOpen }) {
  return (
    <section className="overflow-hidden rounded-lg border border-ink/10 bg-white shadow-sm">
      <button type="button" onClick={onOpen} disabled={!briefing} className="block w-full p-4 text-left disabled:cursor-default">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-ink/50">Morning briefing</h2>
          {briefing?.factory_today && <span className="text-[11px] text-ink/45">{briefing.factory_today}</span>}
        </div>
        {error && <p className="mt-2 text-sm text-ink/70">API offline — ask in chat once the backend is running.</p>}
        {!error && (loading || !briefing) && <p className="mt-2 text-sm text-ink/70">Loading structured facts…</p>}
        {briefing && <Loaded briefing={briefing} />}
      </button>
      {briefing && (
        <button
          type="button" onClick={onOpen}
          className="flex w-full items-center justify-center gap-1 border-t border-ink/10 bg-paper/60 px-4 py-2 text-xs font-semibold text-ink hover:text-brass"
        >
          View details <span aria-hidden="true">→</span>
        </button>
      )}
    </section>
  );
}

function Loaded({ briefing }) {
  const status = overallStatus(briefing) || "stable";
  const meta = STATUS_META[status];
  const atRisk = num(briefing?.at_risk?.count);
  const active = num(briefing?.in_progress_order_count);
  const { OVERDUE } = getFlagCounts(briefing);
  const prodAlerts = getFlaggedStages(briefing).length;
  const suspended = briefing?.suspended_workshops?.length || 0;

  return (
    <div className="mt-2">
      <p className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${meta.ring} ${meta.text}`}>
        <span className={`h-2 w-2 rounded-full ${meta.dot}`} /> {meta.label}
      </p>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <Kpi label="Active" value={active} />
        <Kpi label="Need attention" value={atRisk} accent={atRisk > 0 ? "text-red-600" : "text-ink"} />
        <Kpi label="Overdue" value={OVERDUE} accent={OVERDUE > 0 ? "text-red-600" : "text-ink"} />
        <Kpi label="Prod. alerts" value={prodAlerts} accent={prodAlerts > 0 ? "text-amber-600" : "text-ink"} />
      </div>
      <div className="mt-2 flex items-center gap-3 rounded-md bg-paper px-3 py-2">
        <Donut atRisk={atRisk} active={active} />
        <div className="text-xs text-ink/65">
          {atRisk > 0 ? (
            <p><span className="font-bold text-ink">{atRisk} of {active}</span> active orders need attention.</p>
          ) : (
            <p>All <span className="font-bold text-ink">{active}</span> active orders look clear.</p>
          )}
          {prodAlerts > 0 && <p className="mt-0.5">{prodAlerts} stage production alert{prodAlerts > 1 ? "s" : ""}.</p>}
          {suspended > 0 && <p className="mt-0.5">{suspended} workshop suspended.</p>}
        </div>
      </div>
    </div>
  );
}
