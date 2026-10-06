import ReactECharts from "echarts-for-react";

const PALETTE = ["#1f3a5f", "#b98a2f", "#c0564d", "#5b8c7a", "#7a6a9b", "#4a7fb5"];

function Card({ title, children, provenance }) {
  return (
    <div className="mt-2 rounded-lg border border-ink/10 bg-white p-3 shadow-sm">
      {title && <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink/55">{title}</p>}
      {children}
      {provenance?.source_tool && <p className="mt-1 text-[10px] text-ink/35">Source: {provenance.source_tool}{provenance.source_path ? ` · ${provenance.source_path}` : ""}</p>}
    </div>
  );
}

export default function RichResponseRenderer({ presentations }) {
  if (!presentations?.length) return null;
  return (
    <div className="mt-2 space-y-2">
      {presentations.map((p, i) => <Primitive key={i} p={p} />)}
    </div>
  );
}

function Primitive({ p }) {
  switch (p.kind) {
    case "metric_cards":
      return <Card title={p.title} provenance={p.provenance}>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {(p.data || []).map((c, i) => (
            <div key={i} className="rounded-md bg-paper px-3 py-2"><p className="text-[10px] uppercase text-ink/50">{c.label}</p><p className="text-lg font-semibold">{String(c.value)}</p></div>
          ))}
        </div>
      </Card>;
    case "bar": {
      const d = p.data || [];
      return <Card title={p.title} provenance={p.provenance}>
        <ReactECharts style={{ height: 220 }} option={{ grid: { left: 40, right: 12, top: 24, bottom: 40 }, tooltip: { trigger: "axis" }, xAxis: { type: "category", data: d.map((x) => x.label), axisLabel: { fontSize: 10, rotate: 20 } }, yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.2 } } }, series: [{ type: "bar", data: d.map((x) => x.value), itemStyle: { color: PALETTE[0], borderRadius: [3, 3, 0, 0] }, barMaxWidth: 34 }] }} />
      </Card>;
    }
    case "line": {
      const d = p.data || [];
      return <Card title={p.title} provenance={p.provenance}>
        <ReactECharts style={{ height: 220 }} option={{ grid: { left: 40, right: 12, top: 24, bottom: 40 }, tooltip: { trigger: "axis" }, xAxis: { type: "category", data: d.map((x) => x.x) }, yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.2 } } }, series: [{ type: "line", data: d.map((x) => x.y), smooth: true, lineStyle: { color: PALETTE[0], width: 2 }, symbolSize: 4 }] }} />
      </Card>;
    }
    case "comparison": {
      const d = p.data || [];
      return <Card title={p.title} provenance={p.provenance}>
        <ReactECharts style={{ height: 230 }} option={{ grid: { left: 40, right: 12, top: 28, bottom: 40 }, tooltip: { trigger: "axis" }, legend: { top: 0, textStyle: { fontSize: 10 } }, xAxis: { type: "category", data: d.map((x) => x.label), axisLabel: { fontSize: 10 } }, yAxis: { type: "value", splitLine: { lineStyle: { opacity: 0.2 } } }, series: [{ name: "Current", type: "bar", data: d.map((x) => x.current), itemStyle: { color: PALETTE[0], borderRadius: [3, 3, 0, 0] }, barMaxWidth: 26 }, { name: "Baseline", type: "bar", data: d.map((x) => x.baseline), itemStyle: { color: "#c9c2b4", borderRadius: [3, 3, 0, 0] }, barMaxWidth: 26 }] }} />
      </Card>;
    }
    case "ranked_list":
      return <Card title={p.title} provenance={p.provenance}>
        <ol className="space-y-1">{(p.data || []).map((r, i) => (
          <li key={i} className="flex items-center gap-2 rounded-md bg-paper px-2 py-1.5 text-xs"><span className="flex h-5 w-5 items-center justify-center rounded-full bg-ink text-[10px] text-paper">{i + 1}</span><span className="font-medium">{r.label}</span><span className="text-ink/60">{r.detail || ""}</span></li>
        ))}</ol>
      </Card>;
    case "data_table":
      return <Card title={p.title} provenance={p.provenance}>
        <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr>{(p.columns || []).map((c) => <th key={c} className="border-b px-2 py-1 text-left font-semibold text-ink/60">{c}</th>)}</tr></thead>
        <tbody>{(p.data || []).map((r, i) => <tr key={i} className="odd:bg-paper/60">{(p.columns || []).map((c) => <td key={c} className="border-b border-ink/5 px-2 py-1">{String(r?.[c] ?? "")}</td>)}</tr>)}</tbody></table></div>
      </Card>;
    case "status_card": {
      const d = p.data || {};
      return <Card title={p.title} provenance={p.provenance}>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">{Object.entries(d).slice(0, 10).map(([k, v]) => (
          <div key={k} className="flex justify-between gap-2 border-b border-ink/5 py-1"><dt className="text-ink/55">{k}</dt><dd className="font-medium">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd></div>
        ))}</dl>
      </Card>;
    }
    case "alert_list":
      return <Card title={p.title} provenance={p.provenance}>
        <ul className="space-y-1">{(p.data || []).map((a, i) => (
          <li key={i} className="rounded-md border-l-2 border-amber-500 bg-amber-50 px-2 py-1.5 text-xs"><span className="font-medium">{a.label}</span> <span className="text-ink/65">{a.detail || ""}</span></li>
        ))}</ul>
      </Card>;
    default: return null;
  }
}
