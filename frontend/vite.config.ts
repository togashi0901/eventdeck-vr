import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    // nginx (localhost) 経由の HMR を許可
    allowedHosts: ["localhost", "front"],
    hmr: { clientPort: 80 },
  },
});
