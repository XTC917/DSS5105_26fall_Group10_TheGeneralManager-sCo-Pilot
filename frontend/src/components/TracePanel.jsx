import katex from "katex";
import "katex/dist/katex.min.css";

const PACE_LATEX = String.raw`\mathrm{days}_{\mathrm{left}}=\max\left(\sum_{\text{remaining stages}}\frac{\text{pieces}}{\mathrm{median}_{30\mathrm{d}}},\ \text{remaining stages}\right)`;

function isPaceFormula(item) {
  return item.includes(String.raw`\mathrm{days}_{\mathrm{left}}`)
    || item.startsWith("days_left = max")
    || item.startsWith("Estimated working days still needed is the larger")
    || item.startsWith("预计仍需工作日取两个数");
}

function PaceFormula() {
  const html = katex.renderToString(PACE_LATEX, { throwOnError: false, displayMode: true });
  return (
    <div
      className="pace-formula mt-1 text-ink"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function SourceRows({ source, zh }) {
  const rows = (source.rows || []).filter((row) => Object.keys(row).length);
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  const label = `${source.name} · ${source.row_count ?? rows.length} ${zh ? "条来源记录" : "source records"}`;
  if (source.summary_only) {
    return <p className="rounded border border-ink/10 bg-white p-3 text-xs font-medium">{label}</p>;
  }
  return (
    <details className="rounded border border-ink/10 bg-white p-3">
      <summary className="cursor-pointer text-xs font-medium">
        {source.name} · {source.row_count ?? rows.length} {zh ? "条来源记录" : "source records"}
      </summary>
      {rows.length > 0 ? (
        <div className="mt-2 max-h-64 overflow-auto" tabIndex={0} role="region" aria-label={source.name}>
          <table className="w-full border-collapse text-left text-xs">
            <thead><tr>{columns.map((key) => <th className="whitespace-nowrap border-b p-2" key={key}>{key}</th>)}</tr></thead>
            <tbody>{rows.map((row, i) => <tr key={i}>{columns.map((key) => <td className="whitespace-nowrap border-b border-ink/5 p-2" key={key}>{String(row[key] ?? "—")}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ) : <p className="mt-2 text-xs text-ink/60">{zh ? "没有可展示的来源行。" : "No displayable source rows attached."}</p>}
    </details>
  );
}

export default function TracePanel({ traces = [], why }) {
  const zh = why?.language === "zh";
  // Older API responses can have traces without a structured explanation.
  // Do not invent a retrospective narrative or display internal JSON.
  const sources = why?.sources || traces.filter((t) => t.source_file).map((t) => ({
    name: t.source_file, row_count: t.rows?.length || 0,
    rows: (t.rows || []).map((row) => Object.fromEntries(
      ["order_id", "customer", "product", "pieces", "status", "current_stage", "due_date", "date", "stage", "pieces_completed"]
        .filter((key) => row[key] != null).map((key) => [key.replaceAll("_", " "), row[key]]),
    )),
  }));
  return (
    <section className="mt-3 space-y-3 rounded-lg border border-brass/30 bg-white p-4" aria-label={zh ? "结论依据" : "Explanation"}>
      <p className="text-[11px] font-semibold uppercase tracking-widest text-ink/50">{zh ? "结论的依据" : "The path to this answer"}</p>
      {why?.source_context && <p className="rounded bg-paper p-2 text-xs text-ink/70">{why.source_context}</p>}
      {why?.steps ? <ol className="space-y-4">
        {why.steps.map((step, i) => (
          <li key={i} className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-ink text-xs text-paper">{i + 1}</span>
            <div className="min-w-0"><h3 className="text-sm font-semibold">{step.title}</h3>
              {step.items.map((item, j) => (
                isPaceFormula(item) ? <PaceFormula key={j} /> : <p key={j} className="mt-1 whitespace-pre-wrap break-words text-xs leading-relaxed text-ink/75">{item}</p>
              ))}
            </div>
          </li>
        ))}
      </ol> : <p className="text-xs text-ink/70">This response has source records only. A four-step explanation was not attached.</p>}
      {sources.map((source, i) => <SourceRows key={i} source={source} zh={zh} />)}
    </section>
  );
}
