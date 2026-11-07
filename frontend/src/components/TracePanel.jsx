import katex from "katex";
import "katex/dist/katex.min.css";

const PACE_LATEX = String.raw`\mathrm{days}_{\mathrm{left}}=\max\left(\sum_{\text{remaining stages}}\frac{\text{pieces}}{\mathrm{median}_{30\mathrm{d}}},\ \text{remaining stages}\right)`;

function isPaceFormula(item) {
  return item.includes(String.raw`\mathrm{days}_{\mathrm{left}}`)
    || item.startsWith("days_left = max")
    || item.startsWith("Estimated working days still needed is the larger")
    || item.startsWith("预计仍需工作日取两个数");
}

function Formula({ tex }) {
  const html = katex.renderToString(tex, { throwOnError: false, displayMode: true });
  return (
    <div
      className="pace-formula mt-1 overflow-x-auto text-foreground"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function WhyItem({ item }) {
  if (isPaceFormula(item) && !item.includes(String.raw`\]`)) return <PaceFormula />;
  const parts = item.split(/(\\\[[\s\S]*?\\\])/g);
  if (parts.length === 1) {
    return <p className="mt-1 whitespace-pre-wrap break-words type-caption leading-relaxed text-foreground/75">{item}</p>;
  }
  return parts.map((part, index) => {
    const formula = part.match(/^\\\[([\s\S]*)\\\]$/);
    if (formula) return <Formula key={index} tex={formula[1].trim()} />;
    if (!part.trim()) return null;
    return (
      <p key={index} className="mt-1 whitespace-pre-wrap break-words type-caption leading-relaxed text-foreground/75">
        {part.trim()}
      </p>
    );
  });
}

function PaceFormula() {
  const html = katex.renderToString(PACE_LATEX, { throwOnError: false, displayMode: true });
  return (
    <div
      className="pace-formula mt-1 text-foreground"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

function SourceRows({ source, zh }) {
  const count = source.row_count ?? (source.rows || []).length;
  const label = source.label || `${source.name} · ${count} ${zh ? "条来源记录" : "source records"}`;
  return <p className="rounded-control border border-line bg-surface p-3 type-caption font-medium">{label}</p>;
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
              {step.items.map((item, j) => (
                <WhyItem key={j} item={item} />
              ))}
            </div>
          </li>
        ))}
      </ol> : <p className="type-caption text-foreground/70">This response has source records only. A four-step explanation was not attached.</p>}
      {sources.map((source, i) => <SourceRows key={i} source={source} zh={zh} />)}
    </section>
  );
}
