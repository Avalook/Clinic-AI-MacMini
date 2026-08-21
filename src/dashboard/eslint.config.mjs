import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // E2E bot là script Node độc lập (Playwright), không thuộc app Next — bỏ qua lint.
    "e2e/**",
    "e2e-report/**",
  ]),
  {
    // `cluster.cjs` là script khởi động Node CHẠY TRƯỚC mọi thứ của Next —
    // nó không đi qua bundler, nên phải là CommonJS thật. Đuôi `.cjs` bảo đảm
    // điều đó bất kể `type` trong package.json của bản standalone, và trong
    // CommonJS thì `require` là cách viết ĐÚNG, không phải thói quen cũ.
    // Mở đúng một luật cho đúng một dạng file, không nới toàn cục.
    files: ["**/*.cjs"],
    rules: { "@typescript-eslint/no-require-imports": "off" },
  },
]);

export default eslintConfig;
