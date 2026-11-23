import assert from "node:assert/strict";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

// 24/09/2026 có 17 route /api không màn nào gọi → tắt bằng 410 ở proxy.ts, tệp giữ.
// 24/11/2026 xoá hẳn (log Caddy prod 22–24/11: 190.668 lượt gọi, 0 lượt vào các
// đường này). Bài này canh để chúng không mọc lại dưới tên cũ.

const API = fileURLToPath(new URL("../app/api/", import.meta.url));

const DA_XOA = [
  "dispatch/alerts-call",
  "cskh/ket-qua/[tepId]/cho-phep-gui",
  "cskh/zalo",
  "lab-result",
  "sono",
  "service-log",
  "ultrasound/image",
  "visits/[id]/charges",
  "visits/[id]/service-orders",
  "visits/[id]/service-orders/current",
  "visits/[id]/service-orders/draft",
  "visits/[id]/service-orders/draft/approve",
  "visits/[id]/service-orders/draft/discard",
  "visits/[id]/service-orders/duplicates",
  "visits/[id]/service-orders/remove",
  "work-items/[id]/blockers",
  "patients/check-phone",
];

function moiRoute(thuMuc: string): string[] {
  return readdirSync(thuMuc, { withFileTypes: true }).flatMap((m) => {
    const p = path.join(thuMuc, m.name);
    if (m.isDirectory()) return moiRoute(p);
    return m.name === "route.ts" ? [p] : [];
  });
}

test("17 route đã xoá không quay lại", () => {
  for (const duong of DA_XOA) {
    const tep = path.join(API, duong, "route.ts");
    assert.equal(existsSync(tep), false, `route đã xoá mọc lại: /api/${duong}`);
  }
});

// SO-LUAT luật 3.2 + 4.1: route Next chỉ chuyển tiếp sang FastAPI. Con số "route
// chạm thẳng database" đi 42 (13/08) → 2 (27/09) → 1 (06/10, check-phone) → 0
// (24/11). Chỉ được giảm — giờ là 0 thì không cho lên lại.
test("không route Next nào truy vấn thẳng database (.from/.rpc của Supabase)", () => {
  const cham = moiRoute(API).filter((tep) =>
    /\.(from|rpc)\(\s*["'`]/.test(readFileSync(tep, "utf8")),
  );
  assert.deepEqual(
    cham.map((t) => path.relative(API, t)),
    [],
    "route Next phải chuyển tiếp sang FastAPI, không tự đọc/ghi bảng",
  );
});
