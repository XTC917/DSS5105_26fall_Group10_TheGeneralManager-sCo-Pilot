import { createContext } from "react";

/**
 * @typedef {Object} ThemeContextValue
 * @property {string} theme          Active colour theme id (one of THEME_IDS).
 * @property {boolean} isDark        True for the Black theme only.
 * @property {(theme: string) => void} setTheme
 */

export const ThemeContext = createContext(null);
