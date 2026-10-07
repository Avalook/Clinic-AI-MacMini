import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Khối 4 "Điều trị" của hồ sơ khám (Tuyền chốt 07/10/2026 chiều): danh sách
// CHỈ ĐỊNH ĐIỀU TRỊ — mỗi thẻ là phiếu KẾT QUẢ của chính chỉ định (cùng
// `PhieuKetQua` với phòng dịch vụ) + trạng thái + [Làm tại bàn khám] → [Xong].
// Không còn bảng ghi chung theo lượt; máy chủ quyết nút + câu chặn.
const doc = (f: string) => readFileSync(new URL(f, import.meta.url), "utf8");
const LIB = doc("../lib/phieu-kham.ts");
const PHIEU = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKham.tsx");
const LUOT = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
const KHOI = doc("../app/(dashboard)/_lam-viec/phieu-kham/KhoiDieuTri.tsx");
const DV = doc("../app/(dashboard)/_lam-viec/phieu-kham/KhoiDichVuHoSo.tsx");
const ROUTE = doc("../app/api/ho-so-kham/route.ts");
const IN = doc("../app/print/phieu-kham/[visitId]/InPhieuKham.tsx");

test("bốn khối, khối 4 không có mục của mẫu phiếu", () => {
  assert.match(LIB, /\{ so: 4, ten: "Điều trị", muc: \[\] \}/);
  assert.match(LIB, /\{ so: 1, ten: "Thông tin cơ bản", muc: \["A", "B"\] \}/);
  assert.match(LIB, /\{ so: 3, ten: "Chỉ định điều trị", muc: \["D", "E", "F", "G"\] \}/);
});

test("phiếu vẽ khối 4 qua shell, cả hồ sơ tối giản", () => {
  assert.match(PHIEU, /\{khoi === 4 \? oDieuTri : null\}/);
  assert.match(LUOT, /oDieuTri=\{chiMuc \? undefined : <KhoiDieuTri/);
  assert.match(LUOT.slice(LUOT.indexOf("if (chonDuoc) {")), /<KhoiDieuTri/);
});

test("thẻ = phiếu kết quả của chỉ định (cùng engine phòng), không bảng riêng theo lượt", () => {
  assert.match(KHOI, /import PhieuKetQua/);
  assert.match(KHOI, /<PhieuKetQua serviceOrderId=\{t\.order_id\}/);
  assert.match(KHOI, /xem=dieu-tri/);
  assert.doesNotMatch(KHOI, /cam_nhan|van_de_sau|phien_ban/, "không còn hai ô theo lượt");
  assert.doesNotMatch(ROUTE, /export async function PUT/);
  assert.doesNotMatch(IN, /xem=dieu-tri/);
  assert.match(KHOI, /Chưa có chỉ định điều trị — kê ở khối Chỉ định điều trị/);
});

test("nút do máy chủ quyết; lệnh đi qua route chuyển tiếp", () => {
  for (const co of ["lam_duoc", "ly_do_khong_lam", "xong_duoc", "huy_lam_duoc", "hoan_tac_xong_duoc"]) {
    assert.match(KHOI, new RegExp(`t\\.${co}`));
  }
  assert.match(KHOI, /thao_tac: "ban-kham"/);
  assert.match(KHOI, /"Idempotency-Key"/);
  assert.doesNotMatch(KHOI, /DOCTOR|NURSE|TKYK|MANAGEMENT|role ===|da_thu \?\s*true/);
  assert.match(ROUTE, /`\/api\/v1\/ho-so-kham\/\$\{vid\}\/dieu-tri\/\$\{oid\}\/\$\{lenh\}`/);
  assert.doesNotMatch(ROUTE, /\.from\(/, "không đọc thẳng database");
});

test('"Khách đã đặt" gộp vào khối 4', () => {
  assert.match(KHOI, /t\.da_dat/);
  assert.doesNotMatch(DV, /khach_da_dat/);
});
