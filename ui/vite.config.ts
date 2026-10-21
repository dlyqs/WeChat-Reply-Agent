import { defineConfig } from "vite";
import { readFileSync } from "node:fs";

export default defineConfig({
  build: { outDir: "../src/wechat_reply_agent/web", emptyOutDir: true },
  server: { proxy: { "/api": "http://127.0.0.1:8765" } },
  plugins: [
    {
      name: "dependency-licenses",
      generateBundle() {
        this.emitFile({
          type: "asset",
          fileName: "THIRD_PARTY_LICENSES.txt",
          source: [
            "../docs/frontend-licenses.md",
            "../docs/backend-api-licenses.md",
          ]
            .map((path) => readFileSync(new URL(path, import.meta.url), "utf8"))
            .join("\n\n"),
        });
      },
    },
  ],
});
