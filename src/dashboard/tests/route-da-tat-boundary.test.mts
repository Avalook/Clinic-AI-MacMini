import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { laRouteDaTat } from "../lib/route-da-tat.ts";

// 24/09/2026: 17 route không màn nào gọi → 410 ở proxy (cũ thì OFF, không xoá).
test("route cũ đã tắt trả 410, route đang dùng đi tiếp", () => {
  for (const p of [
    "/api/dispatch/alerts-call",
    "/api/cskh/zalo",
    "/api/cskh/ket-qua/abc/cho-phep-gui",
    "/api/lab-result",
    "/api/sono",
    "/api/service-log",
    "/api/ultrasound/image",
    "/api/visits/v1/charges",
    "/api/visits/v1/service-orders",
    "/api/visits/v1/service-orders/draft/approve",
    "/api/work-items/w1/blockers",
    "/api/patients/check-phone",
  ]) {
    assert.equal(laRouteDaTat(p), true, p);
  }
  for (const p of [
    "/api/lab-result/abc/review",
    "/api/lab-result/abc/triage",
    "/api/dispatch/move",
    "/api/cskh/ket-qua",
    "/api/patients/check-duplicate",
    "/api/work-items",
    "/api/luot-kham",
  ]) {
    assert.equal(laRouteDaTat(p), false, p);
  }
});

test("proxy chặn route đã tắt trước khi đụng phiên", () => {
  const src = readFileSync(new URL("../proxy.ts", import.meta.url), "utf8");
  const chan = src.indexOf("laRouteDaTat(request.nextUrl.pathname)");
  assert.ok(chan > 0);
  assert.ok(chan < src.indexOf("createServerClient("));
});
