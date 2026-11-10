// Pure helpers for Data Sources row editing.
//
// Kept framework-free (no React / antd imports) so the staging/diff logic can
// be unit-tested deterministically without a browser. These MUST mirror
// backend/services/data_admin_updates.py; the backend is the source of truth
// and will reject anything outside its whitelist.

export const PRIMARY_KEYS = {
  orders: ["order_id"],
  production_log: ["production_date", "stage"],
  workshops: ["workshop_id", "makes"],
};

export const NULLABLE_COLUMNS = {
  orders: ["completed_date", "days_late"],
  production_log: [],
  workshops: ["max_batch_pieces"],
};

export const MAX_BATCH = 50;

export function rowKeyObject(primaryKeys, row) {
  return Object.fromEntries(primaryKeys.map((column) => [column, row[column]]));
}

export function rowKeyText(object) {
  return JSON.stringify(object);
}

/**
 * Turn a raw form input value into the value we would submit.
 * - An emptied nullable column becomes null.
 * - A numeric column keeps numeric type when the user typed a valid number,
 *   so the backend receives `1028`, not `"1028"`.
 */
export function coerceValue(original, raw, isNullable) {
  if (isNullable && (raw === "" || raw === null || raw === undefined)) return null;
  if (typeof original === "number") {
    if (raw === "" || raw === null || raw === undefined) return raw;
    const numeric = Number(raw);
    return Number.isFinite(numeric) ? numeric : raw;
  }
  return raw;
}

/** Type-aware equality: 1028 (number) and "1028" (string) count as equal. */
export function sameValue(left, right) {
  if (left === null && right === null) return true;
  if (left === null || right === null) return false;
  if (typeof left === "number" || typeof right === "number") {
    const a = Number(left);
    const b = Number(right);
    if (Number.isFinite(a) && Number.isFinite(b)) return a === b;
  }
  return String(left) === String(right);
}

/**
 * Diff the edited form values against the original row.
 * Only changed, non-primary-key columns are returned.
 */
export function buildChanges(editRow, values, primaryKeys, nullable = []) {
  const changes = {};
  Object.entries(values || {}).forEach(([column, raw]) => {
    if (primaryKeys.includes(column)) return;
    const original = editRow?.[column];
    const normalized = coerceValue(original, raw, nullable.includes(column));
    if (!sameValue(original, normalized)) {
      changes[column] = normalized;
    }
  });
  return changes;
}

export function summarizeChanges(pendingUpdates) {
  const columns = new Set();
  pendingUpdates.forEach((item) => Object.keys(item.changes).forEach((c) => columns.add(c)));
  return { rows: pendingUpdates.length, columns: [...columns] };
}
