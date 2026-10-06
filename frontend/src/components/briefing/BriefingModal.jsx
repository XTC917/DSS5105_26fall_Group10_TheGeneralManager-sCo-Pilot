import { useEffect } from "react";
import ReactECharts from "echarts-for-react";
import {
  getFlagCounts, getProductionRows, getWipEntries, num,
  overallStatus, priorityItems, STATUS_META, summaryLines,
} from "./briefingSummary.js";

const INK = "#1f3a5f";
const RED = "#c0564d";
const AMBER = "#b98a2f";
const GRID = { left: 44, right: 12, top: 12, bottom: 34 };

function Section({ title, children }) {
  return (
    <section className="mt-4">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-ink/50">{title}</h3>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function KpiCard({ label, value, sub, tone }) {
  return (
    <div className="rounded-lg border border-ink/10 bg-paper px-3 py-2.5">
      <p className="text-[10px] font-medium uppercase tracking-wide text-ink/50">{label}</p>
      <p className={`text-2xl font-bold ${tone || "text-ink"}`}>{value}</p>
      {sub && <p className="text-[11px] text-ink/55">{sub}</p>}
    </div>
  );
}

const LEVEL_STYLE = {
  critical: "border-red-400 bg-red-50",
  warning: "border-amber-400 bg-amber-50",
  normal: "border-emerald-300 bg-emerald-50",
};
const LEVEL_DOT = { critical: "bg-red-500", warning: "bg-amber-500", normal: "bg-emerald-500" };

export default function BriefingModal({ briefing, discovery, audit, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose?.(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [onClose]);

  const status = overallStatus(briefing) || "stable";
  const meta = STATUS_META[status];
  const atRisk = num(briefing?.at_risk?.count);
  const active = num(briefing?.in_progress_order_count);
  const flags = getFlagCounts(briefing);
  const wip = getWipEntries(briefing).filter((e) => e.stage !== "ORDERED");
  const prod = getProductionRows(briefing);
  const suspended = briefing?.suspended_workshops || [];
  const lines = summaryLines(briefing);
  const priorities = priorityItems(briefing);
  const issues = discovery?.issues || [];
  const counts = discovery?.counts_by_type || null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/50 p-4" onClick={onClose} role="dialog" aria-modal="true" aria-label="Detailed morning briefing">
      <div className="my-6 w-full max-w-3xl rounded-xl bg-white p-5 shadow-xl sm:p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-brass">Morning briefing · {briefing?.factory_today}</p>
            <h2 className="text-lg font-bold text-ink">Operations overview</h2>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-md border border-ink/15 px-2.5 py-1 text-sm text-ink/70 hover:border-ink/40">✕</button>
        </div>

        <p className={`mt-3 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm font-semibold ${meta.ring} ${meta.text}`}>
          <span className={`h-2 w-2 rounded-full ${meta.dot}`} /> {meta.label}
        </p>
        <ul className="mt-2 space-y-1 text-sm text-ink/80">
          {lines.map((l, i) => <li key={i}>• {l}</li>)}
        </ul>

        <Section title="KPI overview">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <KpiCard label="Active orders" value={active} />
            <KpiCard label="Need attention" value={atRisk} tone={atRisk > 0 ? "text-red-600" : undefined} sub={active > 0 ? `${Math.round((atRisk / active) * 100)}% of active` : undefined} />
            <KpiCard label="Overdue" value={flags.OVERDUE} tone={flags.OVERDUE > 0 ? "text-red-600" : undefined} />
            <KpiCard label="Yesterday output" value={(briefing?.yesterday_output?.by_stage ? Object.values(briefing.yesterday_output.by_stage).reduce((a, b) => a + num(b), 0) : 0).toLocaleString()} sub={`${briefing?.yesterday_output?.date || ""} · pcs`} />
          </div>
        </Section>

        {wip.length > 0 && (
          <Section title="WIP by stage">
            <ReactECharts
              style={{ height: 210 }}
              option={{
                grid: GRID, tooltip: { trigger: "axis" },
                xAxis: { type: "category", data: wip.map((e) => e.stage), axisLabel: { fontSize: 10 } },
                yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.2 } } },
                series: [{ type: "bar", data: wip.map((e) => e.count), itemStyle: { color: INK, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 44 }],
              }}
            />
          </Section>
        )}

        {prod.length > 0 && (
          <Section title="Production vs 30-day median">
            <ReactECharts
              style={{ height: 230 }}
              option={{
                grid: { ...GRID, bottom: 40 }, tooltip: { trigger: "axis" },
                legend: { top: 0, textStyle: { fontSize: 10 } },
                xAxis: { type: "category", data: prod.map((r) => r.stage), axisLabel: { fontSize: 10 } },
                yAxis: { type: "value", name: "pcs", nameTextStyle: { fontSize: 9 }, splitLine: { lineStyle: { opacity: 0.2 } } },
                series: [
                  { name: "Last working day", type: "bar", data: prod.map((r) => r.current), itemStyle: { color: INK, borderRadius: [3, 3, 0, 0] }, barMaxWidth: 26 },
                  { name: "30-day median", type: "bar", data: prod.map((r) => r.baseline), itemStyle: { color: "#c9c2b4", borderRadius: [3, 3, 0, 0] }, barMaxWidth: 26 },
                ],
              }}
            />
            <p className="mt-1 text-[11px] text-ink/50">Last working day {briefing?.yesterday_output?.date || ""} in production_log vs stage 30-day median. Factory-wide by stage, not per order.</p>
          </Section>
        )}

        {(counts || atRisk > 0) && (
          <Section title="Delivery risk by flag">
            <ReactECharts
              style={{ height: 170 }}
              option={{
                grid: GRID, tooltip: { trigger: "axis" },
                xAxis: { type: "category", data: ["Overdue", "Stalled", "Tight deadline"], axisLabel: { fontSize: 10 } },
                yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.2 } } },
                series: [{ type: "bar", data: [flags.OVERDUE, flags.STALLED, flags.TIGHT_DEADLINE], itemStyle: { color: (p) => (p.dataIndex === 0 ? RED : AMBER), borderRadius: [3, 3, 0, 0] }, barMaxWidth: 44 }],
              }}
            />
          </Section>
        )}

        <Section title="Priority attention">
          <ul className="space-y-1.5">
            {priorities.map((p, i) => (
              <li key={i} className={`rounded-md border-l-4 px-3 py-2 text-sm ${LEVEL_STYLE[p.level]}`}>
                <p className="flex items-center gap-2 font-semibold text-ink"><span className={`h-2 w-2 rounded-full ${LEVEL_DOT[p.level]}`} />{p.title}</p>
                <p className="mt-0.5 text-xs text-ink/70">{p.detail}</p>
              </li>
            ))}
          </ul>
        </Section>

        {issues.length > 0 && (
          <Section title="Top discovery issues">
            <ol className="space-y-1">
              {issues.slice(0, 5).map((it, i) => (
                <li key={it.issue_id || i} className="flex items-center gap-2 rounded-md bg-paper px-2.5 py-1.5 text-xs">
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-ink text-[10px] text-paper">{i + 1}</span>
                  <span className="font-semibold">{it.issue_id || it.stage}</span>
                  <span className="text-ink/60">{it.issue_type}{it.evidence?.flags?.length ? ` · ${it.evidence.flags.join(", ")}` : ""}</span>
                </li>
              ))}
            </ol>
          </Section>
        )}

        {suspended.length > 0 && (
          <Section title="Suspended workshops">
            <ul className="space-y-1 text-sm text-ink/80">
              {suspended.map((w) => <li key={w.workshop_id}>• <span className="font-semibold">{w.name}</span>{w.notes ? ` — ${w.notes}` : ""}</li>)}
            </ul>
          </Section>
        )}

        <Section title="Recent activity">
          {(!audit || audit.length === 0) && <p className="text-sm text-ink/60">No local audit rows yet.</p>}
          {(audit || []).slice(0, 5).map((row) => (
            <p key={row.id} className="text-xs text-ink/70">• {row.tool || row.event_type}{row.target ? ` → ${row.target}` : ""} · {row.execution_status || row.confirmation_status}</p>
          ))}
        </Section>
      </div>
    </div>
  );
}
