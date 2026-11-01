import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import { AntdBridge } from "./theme/AntdBridge.jsx";
import { ThemeProvider } from "./theme/ThemeProvider.jsx";
import "./theme/tokens.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <ThemeProvider>
      <AntdBridge>
        <App />
      </AntdBridge>
    </ThemeProvider>
  </React.StrictMode>,
);
