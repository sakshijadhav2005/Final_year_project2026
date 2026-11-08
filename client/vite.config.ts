import path from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  // Dev proxy target. Override per machine with VITE_API_PROXY in client/.env.local
  // (git-ignored) or the environment, e.g. to reach a backend on another port.
  const env = loadEnv(mode, __dirname, "VITE_");
  const apiTarget = process.env.VITE_API_PROXY || env.VITE_API_PROXY || "http://localhost:8000";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
        "/health": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
