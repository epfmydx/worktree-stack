import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 80,
    strictPort: true,
    allowedHosts: (process.env.VITE_ALLOWED_HOSTS || ".worktree.test").split(","),
    hmr: {
      // Browser WebSocket traffic follows the same TLS gateway as the page.
      protocol: "wss",
      clientPort: Number(process.env.VITE_HMR_PORT || 8443),
    },
    // Caddy fronts the app on port 80 inside the container; that's what we listen on.
    // The gateway proxies https://sample-fastapi.<domain>/ -> caddy:80 -> here.
  },
});
