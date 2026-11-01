function SourceRows({ source, zh }) {
  const rows = (source.rows || []).filter((row) => Object.keys(row).length);
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))];
  return (
    <details className="rounded-control border border-line bg-surface p-3">
      <summary className="cursor-pointer type-caption font-medium">
        {source.name} · {source.row_count ?? rows.length} {zh ? "条来源记录" : "source records"}
      </summary>
      {rows.length > 0 ? (
        <div className="mt-2 max-h-64 overflow-auto" tabIndex={0} role="region" aria-label={source.name}>
          <table className="w-full border-collapse text-left type-caption">
            <thead><tr>{columns.map((key) => <th className="whitespace-nowrap border-b p-2" key={key}>{key}</th>)}</tr></thead>
            <tbody>{rows.map((row, i) => <tr key={i}>{columns.map((key) => <td className="whitespace-nowrap border-b border-line p-2" key={key}>{String(row[key] ?? "—")}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ) : <p className="mt-2 type-caption text-muted">{zh ? "没有可展示的来源行。" : "No displayable source rows attached."}</p>}
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
    <section className="mt-3 space-y-3 rounded-card border border-accent/30 bg-surface p-4" aria-label={zh ? "结论依据" : "Explanation"}>
      <p className="text-[11px] font-semibold uppercase tracking-widest text-subtle">{zh ? "结论的依据" : "The path to this answer"}</p>
      {why?.source_context && <p className="rounded bg-surfaceMuted p-2 type-caption text-muted">{why.source_context}</p>}
      {why?.steps ? <ol className="space-y-4">
        {why.steps.map((step, i) => (
          <li key={i} className="flex gap-3">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent type-caption text-accentContrast">{i + 1}</span>
            <div className="min-w-0"><h3 className="type-sm font-semibold">{step.title}</h3>
              {step.items.map((item, j) => <p key={j} className="mt-1 whitespace-pre-wrap break-words type-caption leading-relaxed text-foreground/75">{item}</p>)}
            </div>
          </li>
        ))}
      </ol> : <p className="type-caption text-foreground/70">This response has source records only. A four-step explanation was not attached.</p>}
      {why?.limitations?.length > 0 && <div className="rounded bg-warningSoft p-3 type-caption text-warning">
        <h3 className="font-semibold">{zh ? "适用范围与限制" : "Scope and limitations"}</h3>
        {why.limitations.map((item, i) => <p className="mt-1" key={i}>{item}</p>)}
      </div>}
      {sources.map((source, i) => <SourceRows key={i} source={source} zh={zh} />)}
    </section>
  );
}
