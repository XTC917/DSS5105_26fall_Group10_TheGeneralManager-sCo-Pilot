import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CaretDownOutlined, CaretUpOutlined, MinusOutlined } from "@ant-design/icons";

function numericValue(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

function cellValue(row, key) {
  return row[key] == null ? "" : String(row[key]);
}

function formatSum(value) {
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded)
    ? rounded.toLocaleString()
    : rounded.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function columnTotal(column, rows) {
  const numbers = [];
  for (const row of rows) {
    const raw = row[column.key];
    if (raw == null || raw === "") continue;
    const value = numericValue(raw);
    if (value === null) return null;
    numbers.push(value);
  }
  if (!numbers.length) return null;
  return numbers.reduce((total, value) => total + value, 0);
}

function estimateColumnWidth(column, rows) {
  const values = [column.label, ...rows.map((row) => row[column.key] == null ? "-" : String(row[column.key]))];
  const maxTextWidth = values.reduce((max, value) => {
    const width = Array.from(value).reduce(
      (total, character) => total + (character.codePointAt(0) > 0x2e7f ? 14 : 7),
      0,
    );
    return Math.max(max, width);
  }, 0);
  return Math.min(360, Math.max(120, Math.ceil(maxTextWidth + 52)));
}

const PAGE_SIZE = 50;

export default function TableView({ table }) {
  const [filters, setFilters] = useState({});
  const [sort, setSort] = useState(null);
  const [hiddenColumns, setHiddenColumns] = useState([]);
  const [popup, setPopup] = useState(null);
  const [page, setPage] = useState(0);
  const popupRef = useRef(null);
  const headerRefs = useRef({});

  useEffect(() => {
    setPage(0);
  }, [table, filters, sort]);

  useEffect(() => {
    if (!popup) return undefined;
    function closeOnOutsideClick(event) {
      const filterTrigger = popup.type === "filter" ? headerRefs.current[popup.key] : null;
      if (!popupRef.current?.contains(event.target) && !filterTrigger?.contains(event.target)) {
        setPopup(null);
      }
    }
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, [popup]);

  if (!table || !Array.isArray(table.columns) || !table.columns.length) return null;
  if (!Array.isArray(table.rows) || !table.rows.length) return null;

  const visibleColumns = table.columns.filter((column) => !hiddenColumns.includes(column.key));
  const filterOptions = (column) => [...new Set(table.rows.map((row) => cellValue(row, column.key)))];
  const rows = table.rows.filter((row) =>
    table.columns.every((column) => {
      const filter = filters[column.key];
      if (!filter) return true;
      const value = cellValue(row, column.key);
      const matchesSearch = value.toLocaleLowerCase().includes((filter.query || "").trim().toLocaleLowerCase());
      const matchesSelection = filter.values === undefined || filter.values.includes(value);
      return matchesSearch && matchesSelection;
    }),
  );
  if (sort) {
    const direction = sort.direction === "ascending" ? 1 : -1;
    rows.sort((left, right) => {
      const leftValue = left[sort.key];
      const rightValue = right[sort.key];
      if (leftValue == null || leftValue === "") return rightValue == null || rightValue === "" ? 0 : 1;
      if (rightValue == null || rightValue === "") return -1;
      const leftNumber = numericValue(leftValue);
      const rightNumber = numericValue(rightValue);
      const comparison = leftNumber !== null && rightNumber !== null
        ? leftNumber - rightNumber
        : String(leftValue).localeCompare(String(rightValue), undefined, { numeric: true, sensitivity: "base" });
      return comparison * direction;
    });
  }

  function toggleSort(key) {
    setSort((current) => {
      if (current?.key !== key) return { key, direction: "descending" };
      if (current.direction === "descending") return { key, direction: "ascending" };
      return null;
    });
  }

  function toggleFilter(column) {
    const trigger = headerRefs.current[column.key];
    if (!trigger) return;
    if (popup?.type === "filter" && popup.key === column.key) {
      setPopup(null);
      return;
    }
    const rect = trigger.getBoundingClientRect();
    const width = 288;
    const height = 320;
    const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
    const below = rect.bottom + 4;
    const top = below + height <= window.innerHeight - 8
      ? below
      : Math.max(8, rect.top - height - 4);
    setPopup({ type: "filter", key: column.key, left, top });
  }

  function showContextMenu(event, type, key = null) {
    event.preventDefault();
    event.stopPropagation();
    const width = 240;
    const height = type === "column" ? 72 : Math.min(320, window.innerHeight - 16);
    const left = Math.max(8, Math.min(event.clientX, window.innerWidth - width - 8));
    const top = Math.max(8, Math.min(event.clientY, window.innerHeight - height - 8));
    setPopup({ type, key, left, top });
  }

  function resetFilter(column) {
    setFilters((current) => {
      const updated = { ...current };
      delete updated[column.key];
      return updated;
    });
  }

  function updateFilterQuery(column, query) {
    setFilters((current) => {
      const previous = current[column.key] || {};
      const next = { ...previous };
      if (query) next.query = query;
      else delete next.query;
      const updated = { ...current };
      if (next.query || next.values !== undefined) updated[column.key] = next;
      else delete updated[column.key];
      return updated;
    });
  }

  function toggleFilterValue(column, value) {
    const options = filterOptions(column);
    setFilters((current) => {
      const previous = current[column.key] || {};
      const selected = previous.values ?? options;
      const next = selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value];
      const filter = { ...previous };
      if (next.length === options.length) delete filter.values;
      else filter.values = next;
      const updated = { ...current };
      if (filter.query || filter.values !== undefined) updated[column.key] = filter;
      else delete updated[column.key];
      return updated;
    });
  }

  function selectMatchingValues(column, matchingOptions) {
    const options = filterOptions(column);
    setFilters((current) => {
      const previous = current[column.key] || {};
      const selected = previous.values ?? options;
      const next = [...new Set([...selected, ...matchingOptions])];
      const filter = { ...previous };
      if (next.length === options.length) delete filter.values;
      else filter.values = next;
      const updated = { ...current };
      if (filter.query || filter.values !== undefined) updated[column.key] = filter;
      else delete updated[column.key];
      return updated;
    });
  }

  function hideColumn(key) {
    setHiddenColumns((current) => current.includes(key) ? current : [...current, key]);
    setPopup(null);
  }

  function restoreColumn(key) {
    setHiddenColumns((current) => current.filter((item) => item !== key));
    setPopup(null);
  }

  function filterPopup(column) {
    const filter = filters[column.key] || {};
    const options = filterOptions(column);
    const query = filter.query || "";
    const matchingOptions = options.filter((value) =>
      value.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()),
    );
    const active = Boolean(query) || filter.values !== undefined;
    return (
      <div
        ref={popupRef}
        role="group"
        aria-label={`Filter ${column.label}`}
        className="fixed z-[1000] max-h-[calc(100vh-1rem)] w-72 max-w-[calc(100vw-1rem)] overflow-hidden rounded border border-ink/15 bg-white text-left text-xs text-ink shadow-lg"
        style={{ left: popup.left, top: popup.top }}
      >
        <div className="border-b border-ink/10 p-2">
          <input
            type="search"
            value={query}
            onChange={(event) => updateFilterQuery(column, event.target.value)}
            placeholder={`Search ${column.label}`}
            aria-label={`Search ${column.label} filter values`}
            className="w-full rounded border border-ink/15 px-2.5 py-2 outline-none focus:border-brass"
          />
          <div className="mt-2 flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => selectMatchingValues(column, matchingOptions)}
              className="rounded px-2 py-1 font-medium hover:bg-paper"
            >
              Select shown
            </button>
            <button
              type="button"
              onClick={() => {
                resetFilter(column);
                setPopup(null);
              }}
              className="rounded px-2 py-1 font-medium text-ink/65 hover:bg-paper"
            >
              All values
            </button>
          </div>
        </div>
        <div className="max-h-56 overflow-y-auto p-1.5">
          {matchingOptions.length ? matchingOptions.map((value) => (
            <label key={value} className="flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 hover:bg-paper">
              <input
                type="checkbox"
                checked={filter.values === undefined || filter.values.includes(value)}
                onChange={() => toggleFilterValue(column, value)}
                className="mt-0.5 accent-ink"
              />
              <span className="break-words">{value || "(blank)"}</span>
            </label>
          )) : (
            <p className="px-2 py-3 text-ink/50">No matching values</p>
          )}
        </div>
        {active && (
          <p className="border-t border-ink/10 px-3 py-2 text-ink/55">
            Filter active
          </p>
        )}
      </div>
    );
  }

  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const pageRows = rows.slice(currentPage * PAGE_SIZE, currentPage * PAGE_SIZE + PAGE_SIZE);
  const totals = visibleColumns.map((column) => columnTotal(column, rows));
  const summaryLabelIndex = totals.findIndex((total) => total === null);
  const hiddenColumnItems = table.columns.filter((column) => hiddenColumns.includes(column.key));
  const popupContent = popup?.type === "filter"
    ? filterPopup(table.columns.find((column) => column.key === popup.key))
    : popup?.type === "column"
      ? (
        <div ref={popupRef} role="menu" className="fixed z-[1000] w-60 rounded border border-ink/15 bg-white p-1.5 text-xs text-ink shadow-lg" style={{ left: popup.left, top: popup.top }}>
          <button
            type="button"
            role="menuitem"
            disabled={visibleColumns.length <= 1}
            onClick={() => hideColumn(popup.key)}
            className="w-full rounded px-3 py-2 text-left hover:bg-paper disabled:cursor-not-allowed disabled:opacity-45"
          >
            Hide {table.columns.find((column) => column.key === popup.key)?.label}
          </button>
        </div>
      )
      : popup?.type === "table"
        ? (
          <div ref={popupRef} role="menu" className="fixed z-[1000] max-h-[calc(100vh-1rem)] w-60 overflow-y-auto rounded border border-ink/15 bg-white p-1.5 text-xs text-ink shadow-lg" style={{ left: popup.left, top: popup.top }}>
            {hiddenColumnItems.length ? (
              <>
                <p className="px-3 py-2 font-semibold text-ink/60">Restore column</p>
                {hiddenColumnItems.map((column) => (
                  <button key={column.key} type="button" role="menuitem" onClick={() => restoreColumn(column.key)} className="w-full rounded px-3 py-2 text-left hover:bg-paper">
                    {column.label}
                  </button>
                ))}
                <button type="button" role="menuitem" onClick={() => { setHiddenColumns([]); setPopup(null); }} className="mt-1 w-full rounded border-t border-ink/10 px-3 py-2 text-left font-medium hover:bg-paper">
                  Restore all columns
                </button>
              </>
            ) : (
              <p className="px-3 py-2 text-ink/55">No hidden columns</p>
            )}
          </div>
        )
        : null;

  return (
    <figure className="mt-3 w-full min-w-0 max-w-full border-t border-ink/10 pt-3">
      {table.title && (
        <figcaption className="mb-2 text-xs font-semibold text-ink/80">
          {table.title}
        </figcaption>
      )}
      <div
        className="max-h-72 w-full min-w-0 max-w-full overflow-auto overscroll-contain rounded border border-ink/10 bg-white"
        style={{ scrollbarGutter: "stable" }}
        onContextMenu={(event) => showContextMenu(event, "table")}
      >
        <table className="w-max min-w-full table-fixed border-collapse text-left text-xs">
          <colgroup>
            {visibleColumns.map((column) => (
              <col key={column.key} style={{ width: `${estimateColumnWidth(column, table.rows)}px` }} />
            ))}
          </colgroup>
          <thead className="text-ink/70">
            <tr className="bg-ink/5">
              {visibleColumns.map((column) => (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={sort?.key === column.key ? sort.direction : "none"}
                  onContextMenu={(event) => showContextMenu(event, "column", column.key)}
                  className="sticky top-0 z-10 border-b border-ink/10 bg-paper px-2 py-2 font-semibold"
                >
                  <div className="flex min-w-0 items-center gap-1">
                    <button
                      ref={(element) => { headerRefs.current[column.key] = element; }}
                      type="button"
                      aria-label={`Filter ${column.label}`}
                      aria-expanded={popup?.type === "filter" && popup.key === column.key}
                      onClick={() => toggleFilter(column)}
                      className={`min-w-0 flex-1 break-words text-left whitespace-normal hover:text-ink ${filters[column.key] ? "text-brass" : ""}`}
                      title="Open filter"
                    >
                      {column.label}
                    </button>
                    <button
                      type="button"
                      aria-label={`Sort ${column.label}`}
                      aria-pressed={sort?.key === column.key}
                      title={sort?.key === column.key ? `Sorted ${sort.direction}. Click to change sort.` : "Not sorted. Click to sort descending."}
                      onClick={() => toggleSort(column.key)}
                      className="flex h-6 w-6 shrink-0 items-center justify-center rounded text-ink/55 hover:bg-ink/5 hover:text-ink"
                    >
                      {sort?.key === column.key
                        ? sort.direction === "ascending"
                          ? <CaretUpOutlined aria-label="Sorted ascending" />
                          : <CaretDownOutlined aria-label="Sorted descending" />
                        : <MinusOutlined aria-label="Not sorted" />}
                    </button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-t border-ink/10 odd:bg-white even:bg-ink/[0.025]">
                {visibleColumns.map((column) => (
                  <td key={column.key} className="break-words whitespace-normal px-3 py-2 text-ink/80" title={row[column.key] == null ? "-" : String(row[column.key])}>
                    {row[column.key] == null ? "-" : String(row[column.key])}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={visibleColumns.length} className="px-3 py-5 text-center text-ink/50">
                  No matching rows
                </td>
              </tr>
            )}
          </tbody>
          {rows.length > 1 && totals.some((total) => total !== null) && (
            <tfoot>
              <tr className="border-t border-ink/10 bg-ink/5 font-semibold text-ink">
                {visibleColumns.map((column, index) => {
                  const labelHere = index === (summaryLabelIndex === -1 ? 0 : summaryLabelIndex);
                  const total = totals[index];
                  const sumLabel = pageCount > 1 ? "Sum of all pages" : "Sum";
                  return (
                    <td
                      key={column.key}
                      className="break-words whitespace-normal px-3 py-2"
                      title={pageCount > 1 ? "Total of every filtered row, not only this page" : undefined}
                    >
                      {labelHere && total === null
                        ? sumLabel
                        : labelHere
                          ? `${sumLabel} ${formatSum(total)}`
                          : total === null ? "" : formatSum(total)}
                    </td>
                  );
                })}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {pageCount > 1 && (
        <div className="mt-2 flex items-center justify-between text-xs text-ink/70">
          <span>
            {currentPage * PAGE_SIZE + 1}–{Math.min(rows.length, currentPage * PAGE_SIZE + PAGE_SIZE)} of {rows.length}
          </span>
          <div className="flex gap-1">
            <button
              type="button"
              disabled={currentPage === 0}
              onClick={() => setPage(currentPage - 1)}
              className="rounded border border-ink/15 px-2 py-1 hover:bg-paper disabled:opacity-40"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={currentPage >= pageCount - 1}
              onClick={() => setPage(currentPage + 1)}
              className="rounded border border-ink/15 px-2 py-1 hover:bg-paper disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      )}
      {popupContent && createPortal(
        <div
          onContextMenu={(event) => event.preventDefault()}
          onPointerDown={(event) => event.stopPropagation()}
        >
          {popupContent}
        </div>,
        document.body,
      )}
    </figure>
  );
}