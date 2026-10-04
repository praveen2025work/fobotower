import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Helix API (uvicorn helix.web.main:app --port 8300) serves /api.
// `vite build --mode snapshot` builds the read-only snapshot (snapshot.html +
// recorded data, relative paths) into dist-snapshot/ — see src/snapshot/.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  ...(mode === "snapshot" && {
    base: "./",
    build: { outDir: "dist-snapshot", rollupOptions: { input: "snapshot.html" } },
  }),
  server: {
    port: 5180,
    proxy: {
      "/api": {
        target: process.env.HELIX_API_URL ?? "http://localhost:8300",
        changeOrigin: true,
      },
    },
  },
}));
