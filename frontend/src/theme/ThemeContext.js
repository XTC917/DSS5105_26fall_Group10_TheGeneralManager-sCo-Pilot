import { createContext } from "react";

/**
 * @typedef {Object} ThemeContextValue
 * @property {("light"|"dark"|"system")} mode         User-selected mode.
 * @property {("light"|"dark")} resolvedMode          Effective mode after resolving "system".
 * @property {string} accent                          Selected accent id.
 * @property {(mode: string) => void} setMode
 * @property {(accent: string) => void} setAccent
 */

export const ThemeContext = createContext(null);
