import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { AntdBridge } from "./theme/AntdBridge.jsx";
import { ThemeProvider } from "./theme/ThemeProvider.jsx";
import "./theme/tokens.css";
import "./pages/design-preview/preview.css";
import "./index.css";

/**
 * Keep a `--app-height` CSS variable in sync with the *visual* viewport.
 *
 * iOS Safari's layout viewport (and `100dvh`) does not always shrink when the
 * on-screen keyboard opens, so a `100dvh` app shell can leave the composer
 * hidden behind the keyboard. `visualViewport.height` does shrink, so binding
 * the shell height to it keeps the composer and bottom nav visible. Desktop
 * and Android behave identically (visual viewport === layout viewport there).
 *
 * We deliberately do NOT touch user zoom; this only reports the size.
 */
function installViewportHeight() {
  if (typeof window === "undefined") return;
  const root = document.documentElement;
  let frame = 0;

  const apply = () => {
    frame = 0;
    const viewport = window.visualViewport;
    const height = Math.round(viewport?.height || window.innerHeight || 0);
    if (height > 0) root.style.setProperty("--app-height", `${height}px`);
  };
  const schedule = () => {
    if (frame) return;
    frame = window.requestAnimationFrame(apply);
  };

  apply();
  window.addEventListener("resize", schedule);
  window.addEventListener("orientationchange", schedule);
  window.visualViewport?.addEventListener("resize", schedule);
  window.visualViewport?.addEventListener("scroll", schedule);
}

installViewportHeight();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <AntdBridge>
        <App />
      </AntdBridge>
    </ThemeProvider>
  </React.StrictMode>,
);
