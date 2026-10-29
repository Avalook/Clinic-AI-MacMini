// Không vẽ thanh cuộn ở đâu cả (Tuyền 29/10/2026: thanh trượt bên phải tốn
// diện tích) — vẫn cuộn được, chỉ không giữ chỗ cho thanh.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");

test("thanh cuộn ẩn toàn trang, không còn giữ chỗ 8px", () => {
  assert.match(css, /\*\s*\{\s*scrollbar-width:\s*none;\s*\}/);
  assert.match(css, /::-webkit-scrollbar\s*\{\s*display:\s*none;\s*width:\s*0;\s*height:\s*0;\s*\}/);
  assert.doesNotMatch(css, /scrollbar-width:\s*thin/);
});
