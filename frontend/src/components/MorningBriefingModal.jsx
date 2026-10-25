import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, LabelList, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { confirmAction, fetchBriefing } from "../services/api.js";
import { filterOrders, deadlineText } from "./briefingFilters.mjs";

const BUCKETS = [
  ["OVERDUE", "Overdue", "#bf5145"], ["TODAY", "Due today", "#d68836"],
  ["TWO_DAYS", "In 1–2 days", "#d6ac50"], ["WEEK", "In 3–7 days", "#568398"],
  ["LATER", "Later", "#368578"], ["UNKNOWN", "No due date", "#89939c"],
];
const number = (value) => Number(value || 0).toLocaleString();
const label = (value) => String(value || "Unknown").replaceAll("_", " ").toLowerCase();

const BUCKET_COLOR = Object.fromEntries(BUCKETS.map(([key, , color]) => [key, color]));
const ORDER_COLUMNS = [
  ["order_id", "Order / Customer"],
  ["product", "Product"],
  ["pieces", "Pieces"],
  ["current_stage", "Stage"],
  ["due_date", "Due date"],
  ["flags", "Flags"],
];

function pieceColor(row) {
  return BUCKET_COLOR[row.bucket] || BUCKET_COLOR.UNKNOWN;
}

const STAGE_LINE = [
  ["ASSEMBLY", "#4c78a8"],
  ["KNITTING", "#f28e2b"],
  ["PACKING", "#8d8d8d"],
  ["WASHING", "#e6b325"],
];
const CUSTOMER_COLOR = ["#4c78a8", "#59a14f", "#f2c14e", "#9c9c9c", "#e15759", "#76b7b2", "#b07aa1", "#ff9da7"];
const percentLabel = (value) => (Number(value) > 0 ? `${value}%` : "");

function LastWeekBriefing({ week }) {
  const weeks = week.weeks || [];
  const customers = week.customers || [];
  const productChart = [];
  for (const row of week.products || []) {
    let column = productChart.find((item) => item.product === row.product);
    if (!column) {
      column = { product: row.product };
      productChart.push(column);
    }
    column[row.customer] = row.pieces;
  }
  return (
    <>
      <p className="mb-3 text-[11px] font-bold uppercase tracking-[0.16em] text-teal-700">Last week's sum-up</p>
      <section className="rounded-xl border border-ink/10 bg-white p-5">
        <h3 className="text-center font-semibold">Number of orders completed weekly</h3>
        <p className="mb-2 text-center text-xs text-ink/50">Green is finished on time. Red is finished after the due date. The line is the weekly count.</p>
        {weeks.length ? (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={weeks} margin={{ top: 28, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6e8e5" />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="count" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis yAxisId="share" orientation="right" domain={[0, 100]} tickFormatter={(value) => `${value}%`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value, name) => [typeof value === "number" && name.includes("%") ? `${value}%` : number(value), name]} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar yAxisId="count" dataKey="on_time" name="Done on time" stackId="done" fill="#9ccc7c" isAnimationActive={false}>
                  <LabelList dataKey="on_time_percent" position="center" formatter={percentLabel} style={{ fontSize: 10, fill: "#245c32" }} />
                </Bar>
                <Bar yAxisId="count" dataKey="overdue" name="Done overdue" stackId="done" fill="#e48b8b" isAnimationActive={false}>
                  <LabelList dataKey="overdue_percent" position="center" formatter={percentLabel} style={{ fontSize: 10, fill: "#7a2e2e" }} />
                </Bar>
                <Line yAxisId="count" dataKey="completed" name="Orders completed" stroke="#e6b325" strokeWidth={2} dot={{ r: 4, fill: "#ffe14a", stroke: "#c89612" }} isAnimationActive={false}>
                  <LabelList dataKey="completed" position="top" style={{ fontSize: 11, fontWeight: 700, fill: "#8a6a00" }} />
                </Line>
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : <p className="py-6 text-sm text-ink/60">No completed orders are recorded.</p>}
      </section>
      <section className="mt-4 rounded-xl border border-ink/10 bg-white p-5">
        <h3 className="text-center font-semibold">4-stage complete pieces</h3>
        <p className="mb-2 text-center text-xs text-ink/50">Factory-wide pieces completed at each stage, totaled by week.</p>
        {weeks.length ? (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={weeks} margin={{ top: 12, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6e8e5" />
                <XAxis dataKey="week" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value) => number(value)} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {STAGE_LINE.map(([stage, color]) => (
                  <Line key={stage} dataKey={stage} name={stage} stroke={color} strokeWidth={2} dot={{ r: 3 }} isAnimationActive={false} />
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        ) : <p className="py-6 text-sm text-ink/60">No stage output is recorded.</p>}
      </section>
      <section className="mt-4 rounded-xl border border-ink/10 bg-white p-5">
        <h3 className="text-center font-semibold">Products completed last week</h3>
        <p className="mb-2 text-center text-xs text-ink/50">{week.start} – {week.end} · each stack is a brand, and brand is the customer</p>
        {productChart.length ? (
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={productChart} margin={{ top: 12, right: 8, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6e8e5" />
                <XAxis dataKey="product" interval={0} angle={-25} textAnchor="end" height={70} tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip formatter={(value) => number(value)} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {customers.map((customer, index) => (
                  <Bar key={customer} dataKey={customer} name={customer} stackId="pieces" fill={CUSTOMER_COLOR[index % CUSTOMER_COLOR.length]} isAnimationActive={false}>
                    <LabelList dataKey={customer} position="center" formatter={(value) => (Number(value) > 0 ? number(value) : "")} style={{ fontSize: 10, fill: "#1c2430" }} />
                  </Bar>
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : <p className="py-6 text-sm text-ink/60">No products were completed in the previous full week.</p>}
      </section>
      <footer className="mt-4 text-xs text-ink/50">{week.basis}</footer>
    </>
  );
}

function sortValue(row, key) {
  if (key === "flags") return (row.flags || []).join(", ");
  if (key === "pieces") return Number(row.pieces);
  return row[key] == null ? "" : String(row[key]);
}

export default function MorningBriefingModal({ onClose, refreshToken, onAlertCreated }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [filter, setFilter] = useState("ALL");
  const [stage, setStage] = useState(null);
  const [selected, setSelected] = useState(null);
  const [ordersView, setOrdersView] = useState("table");
  const [panel, setPanel] = useState("today");
  const [sort, setSort] = useState(null);
  const [alertState, setAlertState] = useState({ busy: false, note: "", error: "" });
  const dialog = useRef(null);
  const details = useRef(null);
  const ordersSection = useRef(null);
  useEffect(() => { if (selected) details.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [selected]);

  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialog.current?.focus();
    function keydown(event) {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const nodes = [...dialog.current.querySelectorAll('button:not(:disabled), [href], input, select, [tabindex="0"]')].filter((node) => node.getClientRects().length);
      const first = nodes[0]; const last = nodes[nodes.length - 1];
      if (!nodes.length) { event.preventDefault(); return; }
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === dialog.current)) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", keydown);
    return () => { document.body.style.overflow = overflow; document.removeEventListener("keydown", keydown); previous?.focus(); };
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError("");
    fetchBriefing().then((result) => {
      if (!result.dashboard) throw new Error("Briefing data is unavailable. Restart the updated backend.");
      if (!cancelled) { setData(result); setSelected(null); }
    }).catch((err) => { if (!cancelled) { setError(err.message); setData(null); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [revision, refreshToken]);

  const board = data?.dashboard;
  const rows = useMemo(() => filterOrders(board?.orders || [], filter, stage), [board, filter, stage]);
  const tableRows = useMemo(() => {
    if (!sort) return rows;
    const direction = sort.direction === "ascending" ? 1 : -1;
    return [...rows].sort((left, right) => {
      const leftValue = sortValue(left, sort.key);
      const rightValue = sortValue(right, sort.key);
      const leftEmpty = leftValue === "" || leftValue == null || Number.isNaN(leftValue);
      const rightEmpty = rightValue === "" || rightValue == null || Number.isNaN(rightValue);
      if (leftEmpty && rightEmpty) return 0;
      if (leftEmpty) return 1;
      if (rightEmpty) return -1;
      const comparison = typeof leftValue === "number" && typeof rightValue === "number"
        ? leftValue - rightValue
        : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: "base" });
      return comparison * direction;
    });
  }, [rows, sort]);
  const output = (data?.unusual_stage_output || []).map((row) => ({ ...row, name: label(row.stage) }));
  function chooseFilter(next) {
    setFilter(next); setStage(null); setSelected(null); setAlertState({ busy: false, note: "", error: "" });
    requestAnimationFrame(() => ordersSection.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  async function addAlert(row) {
    const factoryToday = data?.factory_today || "2026-04-01";
    const due = row.due_date || factoryToday;
    const checkDate = due >= factoryToday ? due : factoryToday;
    setAlertState({ busy: true, note: "", error: "" });
    try {
      const result = await confirmAction({
        type: "create_watch",
        order_id: row.order_id,
        condition_type: "ORDER_INACTIVE_BY_DATE",
        check_date: checkDate,
        message: `Tell me if ${row.order_id} hasn't moved by ${checkDate}.`,
      });
      setAlertState({ busy: false, note: result.summary || `Alert saved for ${row.order_id}.`, error: "" });
      onAlertCreated?.();
    } catch (err) {
      setAlertState({ busy: false, note: "", error: err.message || "Could not save the alert." });
    }
  }
  function chooseStage(next) {
    setStage(next); setFilter("ALL"); setSelected(null);
    requestAnimationFrame(() => ordersSection.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/60 p-2 backdrop-blur-sm sm:p-6" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section ref={dialog} tabIndex={-1} role="dialog" aria-modal="true" aria-labelledby="briefing-title" className="flex max-h-[94dvh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl bg-[#f6f5f0] text-ink shadow-2xl outline-none">
        <header className="flex shrink-0 items-center justify-between gap-3 border-b border-ink/10 bg-white px-5 py-4 sm:px-7">
          <div><p className="text-[10px] font-bold uppercase tracking-[0.2em] text-teal-700">SweaterCo / Factory overview</p><h2 id="briefing-title" className="mt-1 text-2xl font-semibold">{panel === "week" ? "Last week's briefing" : "Morning briefing"}</h2><p className="mt-1 text-xs text-ink/60">{panel === "week" && data?.last_week ? `Weekly trend through the factory date · products ${data.last_week.start} – ${data.last_week.end}` : `Factory date: ${data?.factory_today || "Loading…"}`} · Sundays closed</p></div>
          <div className="flex gap-2"><button type="button" aria-pressed={panel === "week"} onClick={() => setPanel((current) => current === "week" ? "today" : "week")} className={`rounded-lg px-3 py-2 text-xs font-semibold ${panel === "week" ? "border border-ink/20 bg-white text-ink" : "bg-ink text-paper"}`}>{panel === "week" ? "Morning briefing" : "Last week's briefing"}</button><button type="button" disabled={loading} onClick={() => setRevision((v) => v + 1)} className="rounded-lg border border-ink/20 px-3 py-2 text-xs disabled:opacity-50">{loading ? "Loading…" : "Refresh"}</button><button type="button" onClick={onClose} aria-label="Close morning briefing" className="rounded-lg border border-ink/20 px-3 py-2 text-sm">&times;</button></div>
        </header>
        <div className="overflow-y-auto p-4 sm:p-7" aria-busy={loading}>
          {error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-5"><p>{error}</p><button type="button" onClick={() => setRevision((v) => v + 1)} className="mt-3 underline">Try again</button></div>}
          {loading && <p role="status" className="py-10 text-center text-ink/60">Preparing factory snapshot…</p>}
          {!loading && panel === "week" && data?.last_week && <LastWeekBriefing week={data.last_week} />}
          {!loading && panel === "today" && board && <>
            <div className="mb-3 rounded-xl bg-ink px-5 py-4 text-paper"><p className="text-lg font-medium">{board.metrics.attention ? `${board.metrics.attention} orders need your attention.` : "No active orders are flagged."}</p><p className="mt-1 text-sm text-paper/70">{board.metrics.overdue} overdue · {board.metrics.due_soon} due today or in the next two days · {board.completed_orders.length} completed on {board.completion_date}.</p></div>
            {output.filter((row) => row.flagged).map((row) => <button type="button" key={row.stage} onClick={() => chooseStage(row.stage)} className="mb-3 block w-full rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-left text-sm text-amber-950 hover:bg-amber-100"><strong className="capitalize">{row.name} output needs attention</strong><span className="mt-1 block text-xs">{number(row.last_day_pieces)} pieces on {row.last_working_date}: {Math.round(row.ratio_to_median * 100)}% of the historical median, below the 70% threshold. View stage orders →</span></button>)}
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {[["ALL", "Orders in progress", board.metrics.active, "text-ink"], ["OVERDUE", "Overdue", board.metrics.overdue, "text-red-700"], ["SOON", "Due within 2 days", board.metrics.due_soon, "text-amber-700"], ["STALLED", "Stalled", board.metrics.stalled, "text-orange-700"]].map(([key, title, value, color]) => <button type="button" key={key} aria-pressed={filter === key} onClick={() => chooseFilter(key)} className={`rounded-xl border bg-white p-4 text-left transition hover:shadow-md ${filter === key ? "border-teal-700 ring-1 ring-teal-700" : "border-ink/10"}`}><span className="text-xs text-ink/60">{title}</span><strong className={`mt-1 block text-3xl ${color}`}>{number(value)}</strong><span className="mt-2 block text-[11px] text-ink/50">View orders →</span></button>)}
            </div>
            <p className="mb-3 mt-2 text-[11px] text-ink/50">Due within 2 days includes today. Stalled means ≥3 working days without activity. Indicators can overlap.</p>
            <div className="grid gap-3 lg:grid-cols-[0.85fr_1.15fr]">
              <section className="rounded-xl border border-ink/10 bg-white p-5"><h3 className="font-semibold">Completed orders</h3><p className="mb-4 text-xs text-ink/50">Previous working day · {board.completion_date}</p>
                {board.completed_orders.length === 0 ? <p className="rounded-lg bg-paper p-4 text-sm text-ink/60">No orders completed on this date.</p> : <div className="max-h-40 space-y-2 overflow-auto">{board.completed_orders.map((row) => <button type="button" key={row.order_id} onClick={() => setSelected({ ...row, completed: true })} className="block w-full rounded-lg border border-ink/10 p-3 text-left hover:bg-paper"><strong className="text-sm">{row.order_id}</strong><span className={`float-right text-xs ${row.days_late > 0 ? "text-red-700" : "text-teal-700"}`}>{row.days_late == null ? "Timing unknown" : row.days_late > 0 ? `${row.days_late} days late` : "On time"}</span><p className="mt-1 text-xs text-ink/60">{row.product} · {row.customer} · {number(row.pieces)} pieces</p></button>)}</div>}
              </section>
              <section className="rounded-xl border border-ink/10 bg-white p-5"><h3 className="font-semibold">Delivery outlook</h3><p className="mb-4 text-xs text-ink/50">All active orders · select a deadline group</p><div className="space-y-2">{BUCKETS.filter(([key]) => key !== "UNKNOWN" || board.deadline_buckets.UNKNOWN).map(([key, title, color]) => { const count = board.deadline_buckets[key] || 0; return <button type="button" aria-pressed={filter === key} key={key} onClick={() => chooseFilter(key)} className={`grid w-full grid-cols-[92px_1fr_24px] items-center gap-3 rounded-md p-1 text-left text-xs hover:bg-paper ${filter === key ? "bg-paper ring-1 ring-teal-600" : ""}`}><span>{title}</span><span className="h-4 overflow-hidden rounded bg-paper"><span className="block h-full rounded transition-all" style={{ background: color, width: `${board.metrics.active ? count / board.metrics.active * 100 : 0}%` }} /></span><strong className="text-right">{count}</strong></button>; })}</div></section>
            </div>
            <section ref={ordersSection} className="mt-4 scroll-mt-4 rounded-xl border border-ink/10 bg-white p-5"><div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Orders in progress <span className="text-sm font-normal text-ink/50">({rows.length})</span></h3><div className="flex items-center gap-2"><div className="flex rounded-lg border border-ink/15 p-0.5 text-xs"><button type="button" aria-pressed={ordersView === "table"} onClick={() => setOrdersView("table")} className={`rounded-md px-3 py-1 ${ordersView === "table" ? "bg-ink text-paper" : "text-ink/70"}`}>Table</button><button type="button" aria-pressed={ordersView === "chart"} onClick={() => setOrdersView("chart")} className={`rounded-md px-3 py-1 ${ordersView === "chart" ? "bg-ink text-paper" : "text-ink/70"}`}>Chart</button></div><button type="button" onClick={() => chooseFilter("ALL")} className="text-xs text-teal-700 underline">Clear filters</button></div></div><p className="mb-3 text-xs text-ink/50">Filter: {filter === "ALL" ? "All deadlines" : filter === "SOON" ? "Due today through +2 days" : label(filter)}{stage ? ` · ${label(stage)}` : ""}. Ordered by due date. Selecting a metric or stage starts a new filter. Select an order for details.</p>
              {ordersView === "chart" ? (
                rows.length ? <div className="h-80 w-full bg-white"><p className="mb-1 text-center text-xs text-ink/70">Orders In-Progress</p><ResponsiveContainer width="100%" height="92%"><BarChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 48 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6e8e5" /><XAxis dataKey="order_id" interval={0} angle={-40} textAnchor="end" height={56} tick={{ fontSize: 10 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip formatter={(value) => [number(value), "Pieces"]} /><Bar dataKey="pieces" name="Pieces" radius={[3, 3, 0, 0]} isAnimationActive={false} onClick={(bar) => { const row = bar?.payload; if (row?.order_id) { setSelected(row); setAlertState({ busy: false, note: "", error: "" }); } }}>{rows.map((row) => <Cell key={row.order_id} fill={pieceColor(row)} cursor="pointer" />)}</Bar></BarChart></ResponsiveContainer></div> : <p className="p-6 text-center text-sm text-ink/60">No orders match these filters.</p>
              ) : (
              <div className="max-h-80 overflow-auto"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-paper text-ink/60"><tr>{ORDER_COLUMNS.map(([key, title]) => <th key={key} className="whitespace-nowrap px-3 py-2 font-medium"><button type="button" onClick={() => setSort((current) => current?.key === key && current.direction === "ascending" ? { key, direction: "descending" } : { key, direction: "ascending" })} className="inline-flex items-center gap-1">{title}<span className="text-ink/40">{sort?.key === key ? (sort.direction === "ascending" ? " ↑" : " ↓") : " -"}</span></button></th>)}</tr></thead><tbody>{tableRows.map((row) => <tr key={row.order_id} className={`border-b border-ink/5 ${selected?.order_id === row.order_id ? "bg-teal-50" : "hover:bg-paper"}`}><td className="px-3 py-3"><button type="button" onClick={() => { setSelected(row); setAlertState({ busy: false, note: "", error: "" }); }} className="font-semibold text-teal-800 underline underline-offset-2">{row.order_id}</button><span className="mt-1 block text-ink/50">{row.customer}</span></td><td className="px-3 py-3">{row.product}</td><td className="px-3 py-3">{number(row.pieces)}</td><td className="px-3 py-3 capitalize">{label(row.current_stage)}</td><td className="whitespace-nowrap px-3 py-3">{row.due_date || "Unknown"}</td><td className="px-3 py-3"><div className="flex flex-wrap gap-1">{row.flags.length ? row.flags.map((flag) => <span key={flag} className={`whitespace-nowrap rounded px-2 py-1 text-[10px] ${flag === "OVERDUE" ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-800"}`}>{label(flag)}</span>) : "No flags"}</div></td></tr>)}</tbody></table>{!tableRows.length && <p className="p-6 text-center text-sm text-ink/60">No orders match these filters.</p>}</div>
              )}
            </section>
            {selected && <section ref={details} aria-live="polite" className="mt-5 rounded-xl border border-teal-700/30 bg-teal-50 p-5"><div className="flex justify-between"><h3 className="font-semibold">{selected.order_id} · Order details</h3><button type="button" aria-label="Close order details" onClick={() => setSelected(null)}>&times;</button></div><p className="mt-2 text-sm">{selected.customer} · {selected.product} · {number(selected.pieces)} pieces</p><p className="mt-2 text-xs">Due: {selected.due_date || "Unknown"} · {selected.completed ? `Completed: ${selected.completed_date}` : `Current stage: ${label(selected.current_stage)}`}</p>{!selected.completed && <><p className="mt-2 text-xs">Last activity: {selected.last_activity_date || "Unknown"} · Working days without activity: {selected.computed.working_days_since_last_activity ?? "Unknown"}</p><p className="mt-2 text-xs">{deadlineText(selected.computed.calendar_days_until_due)} · Estimated remaining working days: {selected.estimated_remaining_working_days ?? "Unavailable"}</p><p className="mt-2 text-xs text-ink/60">Estimate uses 30-working-day stage medians; it does not allocate capacity among competing orders.</p><button type="button" disabled={alertState.busy} onClick={() => addAlert(selected)} className="mt-3 rounded-lg bg-ink px-3 py-2 text-xs font-semibold text-paper disabled:opacity-50">{alertState.busy ? "Saving alert…" : "Add alert"}</button>{alertState.note && <p className="mt-2 text-xs text-teal-800">{alertState.note}</p>}{alertState.error && <p className="mt-2 text-xs text-red-700">{alertState.error}</p>}</>}</section>}
            <section className="mt-5 rounded-xl border border-ink/10 bg-white p-5"><div className="flex flex-wrap items-center justify-between gap-2"><div><h3 className="font-semibold">Production by stage</h3><p className="text-xs text-ink/50">{data.yesterday_output.date || "No recent production data"} · pieces processed at each stage</p></div><p className="text-xs text-ink/50">Select a stage to filter active orders</p></div>
              {output.length ? <div className="mt-3 h-52"><ResponsiveContainer width="100%" height="100%"><BarChart data={output} margin={{ left: 0, right: 12 }}><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e6e8e5" /><XAxis dataKey="name" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 11 }} /><Tooltip /><Legend wrapperStyle={{ fontSize: 11 }} /><Bar name="Last working day" dataKey="last_day_pieces" fill="#267d72" radius={[4, 4, 0, 0]} onClick={(row) => { chooseStage(row.stage || row.payload?.stage); }} cursor="pointer" /><Bar name="30-working-day median" dataKey="lookback_median" fill="#647a9e" radius={[4, 4, 0, 0]} onClick={(row) => { chooseStage(row.stage || row.payload?.stage); }} cursor="pointer" /></BarChart></ResponsiveContainer></div> : <p className="py-6 text-sm text-ink/60">No stage comparison available.</p>}
              <div className="mt-2 flex flex-wrap gap-2">{Object.entries(data.in_progress_by_stage).map(([key, count]) => <button type="button" key={key} aria-pressed={stage === key} onClick={() => { chooseStage(stage === key ? null : key); }} className={`rounded-full border px-3 py-1 text-xs capitalize ${stage === key ? "border-teal-700 bg-teal-50" : "border-ink/15"}`}>{label(key)} · {count} orders</button>)}</div>
              {output.filter((row) => row.flagged).map((row) => <p key={row.stage} className="mt-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-900"><strong className="capitalize">{row.name}</strong>: {number(row.last_day_pieces)} pieces, {Math.round(row.ratio_to_median * 100)}% of the historical median. Below the 70% threshold.</p>)}
              <p className="mt-3 text-[11px] text-ink/50">Stage output is factory-wide. Pieces processed across stages are not a count of finished garments.</p>
            </section>
            <footer className="mt-4 text-xs text-ink/50">Based on factory records as of {data.factory_today}. {data.suspended_workshops.length > 0 && `Suspended workshops: ${[...new Set(data.suspended_workshops.map((w) => w.name))].join(", ")}.`}</footer>
          </>}
        </div>
      </section>
    </div>, document.body,
  );
}
