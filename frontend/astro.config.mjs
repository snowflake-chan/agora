// @ts-check
import { defineConfig } from "astro/config";

import svelte from "@astrojs/svelte";
import node from "@astrojs/node";

import tailwindcss from "@tailwindcss/vite";

const buildVersion = process.env.PUBLIC_APP_VERSION?.trim() || new Date().toISOString();

// https://astro.build/config
export default defineConfig({
  devToolbar: { enabled: false },

  integrations: [svelte()],

  adapter: node({ mode: "standalone" }),

  vite: {
    define: { __AGORA_BUILD_VERSION__: JSON.stringify(buildVersion) },
    plugins: [tailwindcss()],
    server: {
      proxy: {
        "/api": "http://localhost:8000",
      },
    },
  },

  output: "server"
});
