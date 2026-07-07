import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Proxies /api/* to the Django dev server during development, per design
// doc Part A (tech stack) and the project structure doc's
// frontend/vite.config.js entry -- React runs on its own dev server,
// Django is API-only.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
