/**
 * Production theme catalogue — Soft Intelligence (Phase 5B).
 *
 * Seven complete, independent colour themes. There is deliberately no
 * Light / Dark / System mode: each theme (Black included) is a full palette
 * that owns its own base neutrals, accent scale, status colours and gradient
 * background. The concrete colour values live in `tokens.css` under
 * `[data-theme="…"]`; this module only carries metadata, the swatch previews
 * and persistence so the picker and the CSS stay in sync.
 */

export const THEMES = [
  {
    id: "ocean",
    name: "Ocean",
    caption: "Cool blue → pale cyan",
    swatch: "linear-gradient(135deg, #bfdbfe 0%, #3b82f6 100%)",
  },
  {
    id: "lavender",
    name: "Lavender",
    caption: "Soft violet → pale lilac",
    swatch: "linear-gradient(135deg, #ddd6fe 0%, #8b5cf6 100%)",
  },
  {
    id: "sage",
    name: "Sage",
    caption: "Quiet green → mint",
    swatch: "linear-gradient(135deg, #b9dbcc 0%, #2f6b4f 100%)",
  },
  {
    id: "rose",
    name: "Rose",
    caption: "Warm pink → violet",
    swatch: "linear-gradient(135deg, #fbcfe8 0%, #ec4899 100%)",
  },
  {
    id: "amber",
    name: "Amber",
    caption: "Golden → warm orange",
    swatch: "linear-gradient(135deg, #fde68a 0%, #d97706 100%)",
  },
  {
    id: "slate",
    name: "Slate",
    caption: "Neutral grey → sky",
    swatch: "linear-gradient(135deg, #cbd5e1 0%, #334155 100%)",
  },
  {
    id: "black",
    name: "Black",
    caption: "Charcoal · silver · graphite",
    swatch: "linear-gradient(135deg, #3a3f47 0%, #0f1115 100%)",
  },
];

export const THEME_IDS = THEMES.map((theme) => theme.id);
export const DEFAULT_THEME = "ocean";

/** Solid accent fill per theme — used by the Ant Design bridge. */
export const THEME_ACCENT_HEX = {
  ocean: "#1d4ed8",
  lavender: "#6d28d9",
  sage: "#2f6b4f",
  rose: "#be185d",
  amber: "#b45309",
  slate: "#334155",
  black: "#cbd5dd",
};

export function isTheme(value) {
  return THEME_IDS.includes(value);
}

export function isDarkTheme(id) {
  return id === "black";
}

// Persistence. We keep a single key for the theme and a legacy accent key so a
// user who chose an accent under the old Light/Dark/System system is migrated
// transparently instead of landing on a blank or unthemed page.
export const THEME_STORAGE_KEYS = {
  theme: "sweaterco.theme",
  legacyAccent: "sweaterco.theme.accent",
  legacyMode: "sweaterco.theme.mode",
};

/**
 * Resolve the persisted theme, migrating the previous accent-only choice.
 * Returns a valid theme id — never throws, never returns undefined.
 */
export function resolveStoredTheme() {
  if (typeof window === "undefined") return DEFAULT_THEME;
  try {
    const current = window.localStorage.getItem(THEME_STORAGE_KEYS.theme);
    if (isTheme(current)) return current;
    const legacy = window.localStorage.getItem(THEME_STORAGE_KEYS.legacyAccent);
    if (isTheme(legacy)) return legacy;
  } catch {
    /* storage may be unavailable (private mode); fall through to default */
  }
  return DEFAULT_THEME;
}
