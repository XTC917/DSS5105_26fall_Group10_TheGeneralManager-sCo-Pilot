export default function TableView({ table }) {
  if (!table || !Array.isArray(table.columns) || !table.columns.length) return null;
  if (!Array.isArray(table.rows) || !table.rows.length) return null;

  return (
    <figure className="mt-3 border-t border-ink/10 pt-3">
      {table.title && (
        <figcaption className="mb-2 text-xs font-semibold text-ink/80">
          {table.title}
        </figcaption>
      )}
      <div className="max-w-full overflow-x-auto rounded border border-ink/10 bg-white">
        <table className="w-full min-w-max border-collapse text-left text-xs">
          <thead className="bg-ink/5 text-ink/70">
            <tr>
              {table.columns.map((column) => (
                <th key={column.key} scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-t border-ink/10">
                {table.columns.map((column) => (
                  <td key={column.key} className="whitespace-nowrap px-3 py-2 text-ink/80">
                    {row[column.key] == null ? "-" : String(row[column.key])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}