import { useCallback, useEffect, useMemo, useState } from "react";
import { ThemeContext } from "./ThemeContext.js";
import {
  DEFAULT_ACCENT,
  DEFAULT_MODE,
  THEME_STORAGE_KEYS,
  isAccent,
  isMode,
  resolveMode,
} from "./themeConfig.js";

const DARK_QUERY = "(prefers-color-scheme: dark)";

function readStored(key, fallback, validate) {
  if (typeof window === "undefined") return fallback;
  try {
    const value = window.localStorage.getItem(key);
    return validate(value) ? value : fallback;
  } catch {
    return fallback;
  }
}

function systemPrefersDark() {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(DARK_QUERY).matches;
}

function applyToDocument(resolvedMode, accent) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset.theme = resolvedMode;
  root.dataset.accent = accent;
}

export function ThemeProvider({ children }) {
  const [mode, setModeState] = useState(() =>
    readStored(THEME_STORAGE_KEYS.mode, DEFAULT_MODE, isMode),
  );
  const [accent, setAccentState] = useState(() =>
    readStored(THEME_STORAGE_KEYS.accent, DEFAULT_ACCENT, isAccent),
  );
  const [prefersDark, setPrefersDark] = useState(systemPrefersDark);

  const resolvedMode = resolveMode(mode, prefersDark);

  // Keep the DOM attributes in sync with the resolved theme.
  useEffect(() => {
    applyToDocument(resolvedMode, accent);
  }, [resolvedMode, accent]);

  // Follow the OS appearance while in "system" mode.
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return undefined;
    const media = window.matchMedia(DARK_QUERY);
    const onChange = (event) => setPrefersDark(event.matches);
    setPrefersDark(media.matches);
    if (media.addEventListener) {
      media.addEventListener("change", onChange);
      return () => media.removeEventListener("change", onChange);
    }
    // Safari < 14 fallback
    media.addListener(onChange);
    return () => media.removeListener(onChange);
  }, []);

  const setMode = useCallback((next) => {
    if (!isMode(next)) return;
    setModeState(next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEYS.mode, next);
    } catch {
      /* storage may be unavailable (private mode); ignore */
    }
  }, []);

  const setAccent = useCallback((next) => {
    if (!isAccent(next)) return;
    setAccentState(next);
    try {
      window.localStorage.setItem(THEME_STORAGE_KEYS.accent, next);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({ mode, resolvedMode, accent, setMode, setAccent }),
    [mode, resolvedMode, accent, setMode, setAccent],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
