// SĐT cạnh tên khách: đậm, có nền — dễ chú ý khi dò khách (Tuyền 29/10/2026).
// Một component cho mọi màn, nên chỉ cần chốt ở đây.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const src = readFileSync(new URL("../components/ui/TenKhachSdt.tsx", import.meta.url), "utf8");

test("SĐT cạnh tên khách đậm trên nền nhạt", () => {
  assert.match(src, /rounded-chip bg-brand-50 px-1\.5 text-body font-semibold tabular-nums text-brand-700/);
  assert.doesNotMatch(src, /font-medium tabular-nums text-ink-muted/);
});
