import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Helix API (uvicorn helix.web.main:app --port 8300) serves /api.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/api": {
        target: process.env.HELIX_API_URL ?? "http://localhost:8300",
        changeOrigin: true,
      },
    },
  },
});
