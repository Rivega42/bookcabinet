import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import runtimeErrorOverlay from "@replit/vite-plugin-runtime-error-modal";

export default defineConfig({
  plugins: [
    react(),
    runtimeErrorOverlay(),
    ...(process.env.NODE_ENV !== "production" &&
    process.env.REPL_ID !== undefined
      ? [
          await import("@replit/vite-plugin-cartographer").then((m) =>
            m.cartographer(),
          ),
          await import("@replit/vite-plugin-dev-banner").then((m) =>
            m.devBanner(),
          ),
        ]
      : []),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "client", "src"),
      "@shared": path.resolve(import.meta.dirname, "shared"),
    },
  },
  root: path.resolve(import.meta.dirname, "client"),
  build: {
    outDir: path.resolve(import.meta.dirname, "dist/public"),
    emptyOutDir: true,
    // RPi3 optimization: split vendor bundles so we don't ship one huge JS blob
    // on a slow SD card / weak CPU. Keeps react core separate from UI primitives
    // and data fetching library so browser cache and parser can handle them in pieces.
    rollupOptions: {
      output: {
        manualChunks: {
          "react-core": ["react", "react-dom"],
          "radix-ui": [
            "@radix-ui/react-dialog",
            "@radix-ui/react-toast",
            "@radix-ui/react-tabs",
            "@radix-ui/react-progress",
            "@radix-ui/react-tooltip",
            "@radix-ui/react-label",
            "@radix-ui/react-slot",
            "@radix-ui/react-scroll-area",
          ],
          tanstack: ["@tanstack/react-query"],
        },
      },
    },
    chunkSizeWarningLimit: 800,
  },
  server: {
    fs: {
      strict: true,
      deny: ["**/.*"],
    },
    // Дев-режим против python-бэкенда: `vite` (порт 5173) проксирует
    // API и WebSocket на aiohttp (порт из VITE_API_TARGET или 5000).
    proxy: {
      "/api": {
        target: process.env.VITE_API_TARGET || "http://localhost:5000",
        changeOrigin: true,
      },
      "/ws": {
        target: process.env.VITE_API_TARGET || "http://localhost:5000",
        ws: true,
      },
    },
  },
});
