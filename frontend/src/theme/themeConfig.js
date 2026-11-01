/**
 * Theme catalogue and persistence keys.
 * Accent `swatch` values are the deep "fill" colours used for previews and
 * are kept in sync with the `--a-fill` values in tokens.css.
 */

export const THEME_MODES = [
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
  { id: "system", label: "System" },
];

export const ACCENTS = [
  { id: "ocean", name: "Ocean Blue", swatch: "#1d4ed8" },
  { id: "lavender", name: "Lavender Purple", swatch: "#6d28d9" },
  { id: "sage", name: "Sage Green", swatch: "#2f6b4f" },
  { id: "rose", name: "Rose Pink", swatch: "#be185d" },
  { id: "amber", name: "Warm Amber", swatch: "#b45309" },
  { id: "slate", name: "Slate Gray", swatch: "#334155" },
];

export const DEFAULT_MODE = "system";
export const DEFAULT_ACCENT = "ocean";

export const THEME_STORAGE_KEYS = {
  mode: "sweaterco.theme.mode",
  accent: "sweaterco.theme.accent",
};

export const MODE_IDS = THEME_MODES.map((mode) => mode.id);
export const ACCENT_IDS = ACCENTS.map((accent) => accent.id);

export function isMode(value) {
  return MODE_IDS.includes(value);
}

export function isAccent(value) {
  return ACCENT_IDS.includes(value);
}

export function resolveMode(mode, prefersDark) {
  if (mode === "system") return prefersDark ? "dark" : "light";
  return mode === "dark" ? "dark" : "light";
}
