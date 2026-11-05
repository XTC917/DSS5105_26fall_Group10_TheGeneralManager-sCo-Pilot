import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Single backend: everything under /api goes to :8000.
      "/api": "http://127.0.0.1:8000",
      // The conversation list checks this file before showing search and delete.
      "/openapi.json": "http://127.0.0.1:8000",
    },
  },
});
