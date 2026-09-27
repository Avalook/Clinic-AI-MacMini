import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Chỉ năm dịch vụ khám đang bật (migration 20260807000007 + 20260917000006).
// Mọi danh sách CHỌN dịch vụ phải lọc is_active — 17/09 màn đặt lịch CSKH
// hiện đủ 14 dịch vụ cũ vì thiếu đúng dòng này.
const CHON_DICH_VU = [
  "../lib/danh-muc.ts",
  "../app/(dashboard)/patients/new/page.tsx",
  "../app/(dashboard)/appointments/page.tsx",
  "../app/(dashboard)/settings/booking-policy/page.tsx",
];

for (const tep of CHON_DICH_VU) {
  test(`danh sách dịch vụ ở ${tep} chỉ lấy dịch vụ đang bật`, () => {
    const src = readFileSync(new URL(tep, import.meta.url), "utf8");
    const i = src.indexOf('from("service_type")');
    if (i >= 0) {
      assert.match(src.slice(i, i + 160), /\.eq\("is_active", true\)/);
      return;
    }
    // 24/09/2026: trang chuyển sang đọc qua backend — luật lọc nằm ở câu SQL
    // của endpoint ấy, kiểm ở đó.
    const py = (f: string) =>
      readFileSync(new URL(`../../clinicai/${f}`, import.meta.url), "utf8");
    if (src.includes("layDichVu(") && !tep.endsWith("danh-muc.ts")) {
      // Dùng chung lib/danh-muc.ts — file ấy có mục kiểm riêng ngay trong vòng này.
      assert.match(src, /from "[./]*lib\/danh-muc"/);
    } else if (src.includes("/api/v1/appointments/hub-dat-lich")) {
      assert.match(
        py("services/man_dat_lich_doc.py"),
        /FROM service_type"\s*"\s*WHERE clinic_id = \$1::uuid AND is_active/,
      );
    } else {
      assert.match(src, /\/api\/v1\/catalog\/service-types/, "không thấy nguồn dịch vụ");
      assert.match(py("api/v1/routers/catalog.py"), /WHERE is_active IS NOT FALSE AND clinic_id/);
      assert.match(src, /is_active !== false/);
    }
  });
}
