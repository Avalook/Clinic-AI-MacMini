import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Chỉ năm dịch vụ khám đang bật (migration 20260807000007 + 20260917000006).
// Mọi danh sách CHỌN dịch vụ phải lọc is_active — 17/09 màn đặt lịch CSKH
// hiện đủ 14 dịch vụ cũ vì thiếu đúng dòng này.
//
// 07/10/2026: ô chọn lúc đặt / sửa lịch là bộ chọn 4 nhóm dùng chung
// (`_lam-viec/ChonDichVuDatLich.tsx` → `/api/catalog/dich-vu-dat-lich` →
// `services/dich_vu_dat_lich.py`) — luật lọc (đang bật, ẩn nhóm Thuốc) nằm ở câu
// SQL của service ấy.
const CHON_DICH_VU = [
  "../lib/danh-muc.ts",
  "../app/(dashboard)/_lam-viec/ChonDichVuDatLich.tsx",
  "../app/(dashboard)/appointments/page.tsx",
  "../app/(dashboard)/settings/booking-policy/page.tsx",
];

const py = (f: string) =>
  readFileSync(new URL(`../../clinicai/${f}`, import.meta.url), "utf8");

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
    if (src.includes("/api/catalog/dich-vu-dat-lich")) {
      assert.match(
        py("services/dich_vu_dat_lich.py"),
        /WHERE clinic_id = \$1::uuid AND is_active AND nhom <> 'THUOC'/,
      );
    } else if (src.includes("layDichVu(") && !tep.endsWith("danh-muc.ts")) {
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

// Bốn lối đặt / sửa / đổi dịch vụ dùng CÙNG một bộ chọn — không lối nào tự
// viết lại danh sách hay dò dịch vụ theo TÊN (bản cũ `findServiceIdByLinhVuc`).
const LOI_CHON = [
  "../app/(dashboard)/patients/new/NewPatientForm.tsx",
  "../app/(dashboard)/patients/AppointmentBooking.tsx",
  "../app/(dashboard)/appointments/BookingHub.tsx",
  "../app/(dashboard)/_lam-viec/ThaoTacLichTaiCho.tsx",
];

for (const tep of LOI_CHON) {
  test(`${tep} dùng bộ chọn dịch vụ 4 nhóm dùng chung`, () => {
    const src = readFileSync(new URL(tep, import.meta.url), "utf8");
    assert.match(src, /from "(\.\.\/)+_lam-viec\/ChonDichVuDatLich"|from "\.\/ChonDichVuDatLich"/);
    assert.doesNotMatch(src, /findServiceIdByLinhVuc|LOAI_KHAM_DAT_LICH/);
  });
}

test("bộ chọn không có luật nhóm — chỉ vẽ nhóm máy chủ trả", () => {
  const src = readFileSync(
    new URL("../app/(dashboard)/_lam-viec/ChonDichVuDatLich.tsx", import.meta.url),
    "utf8",
  );
  // Không so tên nhóm / mã nhóm trong TSX.
  assert.doesNotMatch(src, /["'](KHAM|DIEU_TRI|THUOC|KHAC)["']/);
  assert.match(src, /goi_y_ghi_chu/);
});

test("ghi chú lịch gửi đủ ở hai biểu mẫu đặt lịch + lễ tân thấy", () => {
  const doc = (f: string) => readFileSync(new URL(f, import.meta.url), "utf8");
  assert.match(doc("../app/(dashboard)/patients/new/NewPatientForm.tsx"), /notes: ghiChu\.trim\(\)/);
  assert.match(doc("../app/(dashboard)/patients/AppointmentBooking.tsx"), /notes: ghiChu\.trim\(\)/);
  assert.match(doc("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx"), /a\.notes/);
  assert.match(doc("../app/(dashboard)/reception/queue/QueueBoard.tsx"), /d\.ghi_chu/);
  assert.match(py("services/week_appointments_service.py"), /"notes": r\.get\("notes"\)/);
  assert.match(py("services/tiep_don_service.py"), /"ghi_chu": r\.get\("notes"\)/);
});
