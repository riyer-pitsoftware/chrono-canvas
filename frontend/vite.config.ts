import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import path from "path";

const apiTarget = process.env.VITE_API_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": apiTarget,
      "/ws": {
        target: apiTarget.replace(/^http/, "ws"),
        ws: true,
      },
    },
  },
});
