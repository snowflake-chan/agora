import type { APIRoute } from "astro";
import { BUILD_VERSION } from "../lib/version";

export const GET: APIRoute = () => new Response(
  JSON.stringify({ version: BUILD_VERSION }),
  {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  },
);
