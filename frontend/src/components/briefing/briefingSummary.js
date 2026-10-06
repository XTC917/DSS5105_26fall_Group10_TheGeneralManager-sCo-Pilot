/** Deterministic Morning Briefing helpers. No LLM, no fetch, pure data in. */

export function num(v, fallback = 0) {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

export function getFlagCounts(briefing) {
  const fc = briefing?.at_risk?.flag_counts || {};
  return {
    OVERDUE: num(fc.OVERDUE),
    STALLED: num(fc.STALLED),
    TIGHT_DEADLINE: num(fc.TIGHT_DEADLINE),
  };
}

export function getFlaggedStages(briefing) {
  return (briefing?.unusual_stage_output || []).filter((s) => s?.flagged);
}

export function getWipEntries(briefing) {
  const byStage = briefing?.in_progress_by_stage || {};
  return Object.entries(byStage)
    .filter(([, v]) => typeof v === "number")
    .map(([stage, count]) => ({ stage, count }));
}

export function getProductionRows(briefing) {
  return (briefing?.unusual_stage_output || [])
    .filter((s) => s && typeof s.last_day_pieces === "number" && typeof s.lookback_median === "number")
    .map((s) => ({
      stage: s.stage,
      current: s.last_day_pieces,
      baseline: s.lookback_median,
      ratio: typeof s.ratio_to_median === "number" ? s.ratio_to_median : null,
      flagged: Boolean(s.flagged),
    }));
}

/** Overall status: stable | watch | elevated. Rules only. */
export function overallStatus(briefing) {
  if (!briefing) return null;
  const atRisk = num(briefing?.at_risk?.count);
  const { OVERDUE } = getFlagCounts(briefing);
  const flaggedStages = getFlaggedStages(briefing).length;
  if (OVERDUE > 0 || flaggedStages > 0) return "elevated";
  if (atRisk > 0) return "watch";
  return "stable";
}

export const STATUS_META = {
  stable: { label: "Operations stable", dot: "bg-emerald-500", text: "text-emerald-700", ring: "border-emerald-200 bg-emerald-50" },
  watch: { label: "Needs attention", dot: "bg-amber-500", text: "text-amber-700", ring: "border-amber-200 bg-amber-50" },
  elevated: { label: "Risk elevated", dot: "bg-red-500", text: "text-red-700", ring: "border-red-200 bg-red-50" },
};

/** Short deterministic summary lines for the detailed view. */
export function summaryLines(briefing) {
  if (!briefing) return [];
  const lines = [];
  const atRisk = num(briefing?.at_risk?.count);
  const active = num(briefing?.in_progress_order_count);
  const { OVERDUE, STALLED, TIGHT_DEADLINE } = getFlagCounts(briefing);
  const flagged = getFlaggedStages(briefing);
  const suspended = briefing?.suspended_workshops || [];

  if (atRisk === 0 && flagged.length === 0) {
    lines.push(`Operations stable: ${active} active orders, nothing flagged this morning.`);
    return lines;
  }
  if (OVERDUE > 0) lines.push(`Delivery risk elevated: ${OVERDUE} overdue order${OVERDUE > 1 ? "s" : ""} out of ${atRisk} at risk.`);
  else if (atRisk > 0) lines.push(`${atRisk} order${atRisk > 1 ? "s" : ""} need attention out of ${active} active.`);
  if (STALLED > 0) lines.push(`${STALLED} stalled order${STALLED > 1 ? "s" : ""} have not moved recently.`);
  if (TIGHT_DEADLINE > 0) lines.push(`${TIGHT_DEADLINE} order${TIGHT_DEADLINE > 1 ? "s" : ""} face tight deadlines.`);
  flagged.forEach((s) => {
    const pct = s.ratio_to_median != null ? Math.round(s.ratio_to_median * 100) : null;
    lines.push(`${s.stage} output ${pct != null ? `at ${pct}% of` : "below"} its 30-day median — clearest production concern.`);
  });
  suspended.forEach((w) => lines.push(`${w.name || w.workshop_id} remains suspended.`));
  return lines;
}

/** Priority attention list: critical / warning / normal, all from real data. */
export function priorityItems(briefing) {
  if (!briefing) return [];
  const items = [];
  const orders = briefing?.at_risk?.orders || [];
  const multiFlag = orders.filter((o) => (o.flags || []).length > 1);
  const overdue = orders.filter((o) => (o.flags || []).includes("OVERDUE"));
  multiFlag.slice(0, 3).forEach((o) =>
    items.push({
      level: "critical",
      title: `${o.order_id} · ${(o.flags || []).join(" + ")}`,
      detail: `${o.customer} ${o.product} × ${o.pieces}, stage ${o.current_stage}, due ${o.due_date}. Combined flags mean both delivery and flow risk.`,
    }),
  );
  overdue
    .filter((o) => !(o.flags || []).some((f) => f !== "OVERDUE" ))
    .slice(0, 5 - Math.min(multiFlag.length, 3))
    .forEach((o) =>
      items.push({
        level: "critical",
        title: `${o.order_id} · overdue`,
        detail: `${o.customer} ${o.product} × ${o.pieces}, stage ${o.current_stage}, due ${o.due_date}.`,
      }),
    );
  getFlaggedStages(briefing).forEach((s) =>
    items.push({
      level: "critical",
      title: `${s.stage} production drop`,
      detail: `Last working day ${s.last_day_pieces} pcs vs 30-day median ${s.lookback_median} pcs. Stage-level throughput risk.`,
    }),
  );
  (briefing?.suspended_workshops || []).forEach((w) =>
    items.push({
      level: "warning",
      title: `${w.name || w.workshop_id} suspended`,
      detail: w.notes || "Outside workshop unavailable; overflow capacity reduced.",
    }),
  );
  orders
    .filter((o) => !(o.flags || []).includes("OVERDUE") && (o.flags || []).length <= 1)
    .slice(0, 4)
    .forEach((o) =>
      items.push({
        level: "warning",
        title: `${o.order_id} · ${(o.flags || []).join(", ")}`,
        detail: `${o.customer} ${o.product}, stage ${o.current_stage}, due ${o.due_date}.`,
      }),
    );
  if (items.length === 0) {
    items.push({ level: "normal", title: "Nothing requires action", detail: "No flagged orders, stages, or workshops this morning." });
  }
  return items;
}
