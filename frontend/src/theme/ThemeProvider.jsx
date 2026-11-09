import { useCallback, useEffect, useMemo, useState } from "react";
import { ThemeContext } from "./ThemeContext.js";
import {
  DEFAULT_THEME,
  THEME_STORAGE_KEYS,
  isDarkTheme,
  isTheme,
  resolveStoredTheme,
} from "./themeConfig.js";

function applyToDocument(theme) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  // `data-theme` selects the full palette in tokens.css. `data-accent` is kept
  // in sync so any legacy `[data-accent]` styling and the chart observer that
  // listens on it keep working without a second source of truth.
  root.dataset.theme = theme;
  root.dataset.accent = theme;
  root.dataset.appearance = isDarkTheme(theme) ? "dark" : "light";
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(resolveStoredTheme);

  useEffect(() => {
    applyToDocument(theme);
  }, [theme]);

  const setTheme = useCallback((next) => {
    if (!isTheme(next)) return;
    setThemeState(next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEYS.theme, next);
    } catch {
      /* storage may be unavailable (private mode); ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ theme, isDark: isDarkTheme(theme), setTheme }),
    [theme, setTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
