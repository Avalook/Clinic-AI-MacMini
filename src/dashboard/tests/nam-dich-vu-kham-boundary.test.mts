import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Chỉ năm dịch vụ khám đang bật (migration 20260807000007 + 20260917000006).
// Mọi danh sách CHỌN dịch vụ phải lọc is_active — 17/09 màn đặt lịch CSKH
// hiện đủ 14 dịch vụ cũ vì thiếu đúng dòng này.
const CHON_DICH_VU = [
  "../lib/danh-muc.ts",
  "../app/(dashboard)/patients/new/page.tsx",
  "../app/(dashboard)/patients/[id]/page.tsx",
  "../app/(dashboard)/appointments/page.tsx",
  "../app/(dashboard)/settings/booking-policy/page.tsx",
];

for (const tep of CHON_DICH_VU) {
  test(`danh sách dịch vụ ở ${tep} chỉ lấy dịch vụ đang bật`, () => {
    const src = readFileSync(new URL(tep, import.meta.url), "utf8");
    const i = src.indexOf('from("service_type")');
    assert.ok(i >= 0, "không thấy truy vấn service_type");
    assert.match(src.slice(i, i + 160), /\.eq\("is_active", true\)/);
  });
}
