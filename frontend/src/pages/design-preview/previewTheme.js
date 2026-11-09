/**
 * Phase 5A round 2 — preview-only theme catalogue.
 *
 * This is intentionally separate from the production theme system. It only
 * exists inside the design preview so the preview can show seven complete,
 * independent colour themes (including a bespoke Black theme) without touching
 * ThemeProvider, ThemeSwitcher or the production `data-theme` / `data-accent`
 * attributes. There is deliberately no light / dark / system mode: the user
 * only chooses a colour theme.
 *
 * The actual colour values live in preview.css under `.design-preview
 * [data-dp-theme="…"]`. This module only carries metadata + persistence so the
 * swatches and labels stay in one place, and so a future migration can lift the
 * catalogue into the real theme config.
 */

import { useCallback, useState } from "react";

export const PREVIEW_THEMES = [
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

export const PREVIEW_THEME_IDS = PREVIEW_THEMES.map((theme) => theme.id);
export const DEFAULT_PREVIEW_THEME = "ocean";
export const PREVIEW_THEME_STORAGE_KEY = "sweaterco.designPreview.theme";

function readStoredTheme() {
  if (typeof window === "undefined") return DEFAULT_PREVIEW_THEME;
  try {
    const value = window.localStorage.getItem(PREVIEW_THEME_STORAGE_KEY);
    return PREVIEW_THEME_IDS.includes(value) ? value : DEFAULT_PREVIEW_THEME;
  } catch {
    return DEFAULT_PREVIEW_THEME;
  }
}

export function usePreviewTheme() {
  const [theme, setThemeState] = useState(readStoredTheme);

  const setTheme = useCallback((next) => {
    if (!PREVIEW_THEME_IDS.includes(next)) return;
    setThemeState(next);
    try {
      window.localStorage.setItem(PREVIEW_THEME_STORAGE_KEY, next);
    } catch {
      /* storage may be unavailable (private mode); ignore */
    }
  }, []);

  return { theme, setTheme };
}
