// Một bệnh nhân, nhiều số điện thoại (15/08/2026) — các luật lớp hiển thị.
//
// Luật xương sống: MỌI đường tìm theo số phải đi qua CỘT GỘP `sdt_tim_kiem`
// (migration 20260815000002 nuôi bằng trigger). Tra bằng cột lẻ là màn ấy mù
// số thêm — "tra số nào cũng ra" đúng chỗ này sai chỗ kia, đúng loại lệch
// từng-màn-một mà Luật 12.2 cấm.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) =>
  readFileSync(new URL(p, import.meta.url), "utf8")
    .replace(/\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");

test("danh sách khách tìm bằng cột gộp, và tải kèm số thêm để vẽ", () => {
  const page = doc("../app/(dashboard)/customers/page.tsx");
  assert.match(page, /sdt_tim_kiem\.ilike/, "tìm phải qua cột gộp mọi số");
  assert.doesNotMatch(
    page,
    /phone_primary\.ilike/,
    "tìm bằng cột lẻ là mù số thêm — đường cũ không được quay lại",
  );
  assert.match(
    page,
    /patient_sdt_them\s*\(\s*so_dien_thoai,\s*loai\s*\)/,
    "SELECT phải embed bảng số thêm — không có dữ liệu thì hồ sơ không vẽ được dòng số phụ",
  );
});

test("màn đặt lịch: ô tìm khách nhìn thấy số thêm", () => {
  const page = doc("../app/(dashboard)/appointments/page.tsx");
  assert.match(page, /sdt_tim_kiem/, "query nạp khách phải mang cột gộp");
  const hub = doc("../app/(dashboard)/appointments/BookingHub.tsx");
  assert.match(
    hub,
    /p\.sdt_tim_kiem \?\? p\.phone_primary/,
    "bộ lọc client phải ưu tiên cột gộp, rơi về số chính khi dữ liệu cũ",
  );
});

test("cảnh báo trùng SĐT tra cột gộp và trả khoá hồ sơ", () => {
  const route = doc("../app/api/patients/check-phone/route.ts");
  assert.match(route, /ilike\("sdt_tim_kiem"/, "check-phone phải tra cột gộp");
  assert.match(
    route,
    /clinic_patient_id/,
    "thiếu khoá hồ sơ thì nút 'thêm số cho khách này' không biết gắn vào ai",
  );
});

test("nút thêm số đứng trong CẢ HAI ô cảnh báo — trùng số lẫn trùng tên", () => {
  const form = doc("../app/(dashboard)/patients/new/NewPatientForm.tsx");
  const soNut = (form.match(/<ThemSdtChoKhach /g) ?? []).length;
  assert.equal(
    soNut,
    2,
    "một ô có nút một ô không là vá-một-trong-hai — đúng lỗi ba lưới đặt chỗ",
  );
  // Ô trùng TÊN gợi ý số đang gõ (số ấy chưa của ai); ô trùng SỐ thì không
  // (số đang gõ đã là của hồ sơ khớp — thứ cần nhập là một số KHÁC).
  assert.equal((form.match(/<ThemSdtChoKhach khach=\{m\} goiY=\{phone\}/g) ?? []).length, 1);
  assert.equal((form.match(/<ThemSdtChoKhach khach=\{m\} \/>/g) ?? []).length, 1);
});

test("hồ sơ khách vẽ số thêm ở CẢ hai khu, đúng loại dưới đúng dòng", () => {
  const view = doc("../app/(dashboard)/customers/CustomersView.tsx");
  // Hai khu hiển thị (đầu thẻ + bảng chi tiết) đều lọc CHINH; khu chi tiết
  // thêm cả NGUOI_NHA dưới dòng "SĐT người nhà".
  const locChinh = (view.match(/loai === "CHINH"/g) ?? []).length;
  const locNguoiNha = (view.match(/loai === "NGUOI_NHA"/g) ?? []).length;
  assert.ok(
    locChinh >= 2,
    `số thêm loại CHINH phải vẽ ở cả đầu thẻ lẫn bảng chi tiết (thấy ${locChinh})`,
  );
  assert.ok(locNguoiNha >= 1, "số người nhà thêm phải có chỗ vẽ");
});
