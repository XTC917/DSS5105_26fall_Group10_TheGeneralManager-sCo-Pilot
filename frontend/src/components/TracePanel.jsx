function Block({ title, children }) {
  return (
    <div className="mt-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink/50">{title}</p>
      {children}
    </div>
  );
}

export default function TracePanel({ traces }) {
  return (
    <div className="mt-2 space-y-3 rounded border border-ink/10 bg-white p-2">
      {traces.map((trace, idx) => (
        <section key={`${trace.tool}-${idx}`}>
          <p className="text-xs font-medium">
            {trace.tool || "tool"} · {trace.source_file || "source"}
          </p>
          {trace.basis && <p className="mt-1 text-xs text-ink/70">{trace.basis}</p>}
          {trace.filter && (
            <Block title="Filter">
              <pre className="trace-pre overflow-x-auto text-ink/80">
                {JSON.stringify(trace.filter, null, 2)}
              </pre>
            </Block>
          )}
          {trace.rows?.length > 0 && (
            <Block title={`Rows (${trace.rows.length})`}>
              <pre className="trace-pre max-h-48 overflow-auto text-ink/80">
                {JSON.stringify(trace.rows, null, 2)}
              </pre>
            </Block>
          )}
          {trace.calculations?.length > 0 && (
            <Block title="Calculations">
              <pre className="trace-pre max-h-48 overflow-auto text-ink/80">
                {JSON.stringify(trace.calculations, null, 2)}
              </pre>
            </Block>
          )}
        </section>
      ))}
    </div>
  );
}
