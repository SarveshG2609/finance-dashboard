import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/health": "http://localhost:8000",
      "/imports": "http://localhost:8000",
      "/dashboard": "http://localhost:8000",
      "/manual-assets": "http://localhost:8000",
      "/accounts": "http://localhost:8000",
    },
  },
});
