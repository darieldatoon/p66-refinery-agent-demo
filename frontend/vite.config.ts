import react from "@vitejs/plugin-react";
import { defineConfig, lazyPlugins } from "vite-plus";

export default defineConfig({
  base: process.env.PAGES_BASE_PATH || "/p66-refinery-agent-demo/",
  plugins: lazyPlugins(() => [react()]),
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["src/test-setup.ts"],
  },
});
