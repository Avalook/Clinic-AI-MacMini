import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Màn Nhà thuốc sau contract tiền–thuốc CP4 (19/09/2026). Bốn điều dễ hỏng
// nhất khi ai đó "sửa nhanh" màn này.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const page = doc("app/(dashboard)/pharmacy/page.tsx");
const board = doc("app/(dashboard)/pharmacy/PharmacyBoard.tsx");
const dong = doc("app/(dashboard)/pharmacy/DongThuoc.tsx");
const kieu = doc("app/(dashboard)/pharmacy/ban-thuoc.ts");
const proxy = doc("app/api/pharmacy/[action]/route.ts");

test("màn đọc qua máy chủ, không đọc thẳng Supabase", () => {
  // Giai đoạn tiền thuốc và các nút được phép là luật nghiệp vụ (FastAPI).
  // Bản trước đọc thẳng `prescription` + `drug_batch` rồi tự so tên thuốc.
  assert.match(page, /fetchFromBackend<ManNhaThuoc>\("\/api\/v1\/pharmacy\/ban-thuoc"\)/);
  assert.doesNotMatch(page, /getSupabaseServer|\.from\(/);
});

test("nút hiện theo lời máy chủ, không tự suy từ giai đoạn", () => {
  // Mã giai đoạn chỉ được dùng để tra NHÃN (ban-thuoc.ts). Component nào so
  // `giai_doan === "..."` để quyết nút là đang chép lại luật của máy chủ.
  for (const src of [board, dong]) {
    assert.doesNotMatch(src, /===\s*"(CHUA_SAN_SANG|SAN_SANG|CHO_XAC_MINH|DA_THU|CAN_DOI_SOAT|DA_THU_CU)"/);
  }
  for (const nut of ["chon_lo", "xac_dinh_thuoc", "khai_so_mua", "tu_choi", "chot", "giao_luong_cu"]) {
    assert.match(dong, new RegExp(`tt\\.${nut}`), `thiếu cổng tt.${nut}`);
  }
  for (const nut of ["bo", "doi", "giao"]) {
    assert.match(dong, new RegExp(`p\\.thao_tac\\.${nut}`), `thiếu cổng p.thao_tac.${nut}`);
  }
});

test("không gọi số hệ thống là 'tồn khả dụng' (HOLD J6)", () => {
  // Tên chính thức của con số chống bán trùng chưa chốt với kho.
  for (const src of [board, dong, kieu]) {
    assert.doesNotMatch(src, /tồn khả dụng/i);
  }
  assert.match(dong, /Tồn vật lý/);
  assert.match(dong, /Có thể phân lô lúc này/);
});

test("proxy mở đủ và chỉ đúng các thao tác phân lô của máy chủ", () => {
  for (const [a, p] of [
    ["xac-dinh-thuoc", "xac-dinh-thuoc"],
    ["so-luong-mua", "so-luong-mua"],
    ["phan-lo", "phan-lo"],
    ["bo-phan-lo", "bo-phan-lo"],
    ["doi-lo", "doi-lo"],
  ]) {
    assert.match(proxy, new RegExp(`"${a}":\\s*"/api/v1/pharmacy/${p}"`));
  }
  assert.doesNotMatch(dong, /window\.confirm/);
});

// ── CP5: hoàn tiền / huỷ phần chưa giao / khách trả thuốc ─────────────────
const hoan = doc("app/(dashboard)/thu-ngan/HoanTien.tsx");
const payProxy = doc("app/api/payment/route.ts");

test("CP5: màn hoàn tiền không tự tính tiền và chỉ hiện nút khi máy chủ cho", () => {
  // Số tiền hoàn do máy chủ tính theo đơn giá ảnh chụp — màn không nhân.
  assert.doesNotMatch(hoan, /don_gia/);
  assert.doesNotMatch(hoan, /\*\s*Number|Number\([^)]*\)\s*\*/);
  // Nút ghi chỉ khi máy chủ báo có quyền hoàn (tạm thời chỉ Quản lý, HOLD J4).
  assert.match(hoan, /coQuyenHoan && k\.status === "PENDING"/);
  assert.match(hoan, /coQuyenHoan && conHoan\.length > 0/);
  assert.doesNotMatch(hoan, /window\.confirm/);
  for (const a of ["hoan-tien", "hoan-tien-xac-nhan", "hoan-tien-dong"]) {
    assert.match(payProxy, new RegExp(`p\\.action === "${a}"`));
  }
});

test("CP5: khách trả / huỷ phần chưa giao theo cờ máy chủ, đủ proxy", () => {
  assert.match(dong, /x\.thao_tac\.tra/);
  assert.match(dong, /tt\.huy_chua_giao/);
  for (const [a, p] of [
    ["huy-phan-chua-giao", "huy-phan-chua-giao"],
    ["khach-tra", "khach-tra"],
  ]) {
    assert.match(proxy, new RegExp(`"${a}":\\s*"/api/v1/pharmacy/${p}"`));
  }
  // Khách trả KHÔNG có nút "đưa lại bán / huỷ / cách ly" (HOLD J1/J2).
  assert.doesNotMatch(dong, /disposition|Đưa lại bán|Nhập lại kho/);
});
