import tailwindcss from "@tailwindcss/vite";
import solid from "@solidjs/vite-plugin";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [solid(), tailwindcss()],
  // ../events.json is shared with the engine
  server: { port: 5173, fs: { allow: [".."] } },
});
