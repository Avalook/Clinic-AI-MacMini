import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Popup "Lịch sử khám" (T7) + `/patient-list` mở đúng khung (T8) — Tuyền chốt
// 07/10/2026. Khung đọc theo `loai_du_lieu` MÁY CHỦ trả; khung đọc cũ GIỮ.
const doc = (f: string) => readFileSync(new URL(f, import.meta.url), "utf8");
const POPUP = doc("../app/(dashboard)/_lam-viec/LichSuKham.tsx");
const LUOT = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
const DS = doc("../app/(dashboard)/patient-list/PatientListView.tsx");
const KH = doc("../app/(dashboard)/customers/ThanhLuotKham.tsx");
const LICH = doc("../components/ui/LichKhoangNgay.tsx");

test("popup đọc mọi lượt qua máy chủ, chọn khung theo loại dữ liệu", () => {
  assert.match(POPUP, /xem: "lich-su"/);
  assert.match(POPUP, /xem\.loai_du_lieu === "v5"/);
  assert.match(POPUP, /<XemLuot/, "lượt không phiếu v5 vẫn mở được");
  assert.match(POPUP, /ngayCham=\{ngayCham\}/);
  assert.match(LICH, /ngayCham\?\.has\(ngay\)/);
});

test("một component dùng chung ở Bàn khám, /patient-list, /customers", () => {
  assert.match(LUOT, /<LichSuKham clinicPatientId=\{clinicPatientId\}/);
  assert.match(DS, /<LichSuKham/);
  assert.match(KH, /<LichSuKham/);
});

test("/patient-list: lượt bấm được, v5 → hồ sơ mới, còn lại → khung cũ", () => {
  assert.match(DS, /onClick=\{\(\) => moLuot\(v\)\}/);
  assert.match(DS, /v\.loai_du_lieu === "v5" && v\.visit_id/);
  assert.match(DS, /<PhieuKhamLuot[\s\S]*?xemLai/);
  // Khung đọc cũ còn nguyên (không xoá ClinicalRecordForm — Bàn khám còn dùng).
  assert.match(DS, /<ClinicalRecordForm[\s\S]*?readOnly[\s\S]*?enableVisitPager=\{enableVisitPager\}/);
});

test("chip \"Lần n\" ở Bàn khám giữ lại", () => {
  const bk = doc("../app/(dashboard)/ban-kham/BanKham.tsx");
  assert.match(bk, /<LuotKhamTruoc/);
});
