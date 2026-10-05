import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Helix API (uvicorn helix.web.main:app --port 8300) serves /api.
// `vite build --mode snapshot` builds the read-only snapshot (snapshot.html +
// recorded data, relative paths) into dist-snapshot/ — see src/snapshot/.
// It is one script and one stylesheet (no lazy chunks), so
// scripts/inline-snapshot.mjs can fold them into a single HTML file that opens
// straight from disk or an email attachment.
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  ...(mode === "snapshot" && {
    base: "./",
    build: {
      outDir: "dist-snapshot",
      cssCodeSplit: false,
      assetsInlineLimit: 100_000_000,
      rollupOptions: { input: "snapshot.html", output: { inlineDynamicImports: true } },
    },
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
