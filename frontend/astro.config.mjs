// @ts-check
import { defineConfig } from "astro/config";

import svelte from "@astrojs/svelte";
import node from "@astrojs/node";

import tailwindcss from "@tailwindcss/vite";

// https://astro.build/config
export default defineConfig({
  integrations: [svelte()],

  adapter: node({ mode: "standalone" }),

  vite: {
    plugins: [tailwindcss()],
    server: {
      proxy: {
        "/api": "http://localhost:8000",
      },
    },
  },

  output: "server"
});
