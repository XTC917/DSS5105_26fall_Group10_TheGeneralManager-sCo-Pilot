import { useContext } from "react";
import { ThemeContext } from "./ThemeContext.js";

export function useTheme() {
  const value = useContext(ThemeContext);
  if (!value) {
    throw new Error("useTheme must be used within a <ThemeProvider>");
  }
  return value;
}
