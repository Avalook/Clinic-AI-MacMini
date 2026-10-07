import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Khối 4 "Điều trị" của hồ sơ khám (Tuyền chốt 07/10/2026 chiều + phản hồi bấm
// thử staging tối 07/10): danh sách CHỈ ĐỊNH ĐIỀU TRỊ — mỗi thẻ là phiếu điều trị
// của chính chỉ định, vẽ bằng MỘT component `PhieuDieuTri` dùng chung với khung
// kết quả của phòng dịch vụ (`PhieuKetQua` chuyển sang khi mẫu PHIEU_DIEU_TRI).
// Gọn: mỗi ô một nhãn, không "Hoàn tất phiếu", không gập/mở. Máy chủ quyết nút,
// câu chặn và chỉ đọc sau check-out.
const doc = (f: string) => readFileSync(new URL(f, import.meta.url), "utf8");
/** Bỏ dòng chú thích — chỉ soi mã thật. */
const ma = (s: string) => s.replace(/^\s*\/\/.*$/gm, "");
const LIB = doc("../lib/phieu-kham.ts");
const PHIEU = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKham.tsx");
const LUOT = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
const KHOI = doc("../app/(dashboard)/_lam-viec/phieu-kham/KhoiDieuTri.tsx");
const DT = doc("../app/(dashboard)/_lam-viec/PhieuDieuTri.tsx");
const KQ = doc("../app/(dashboard)/_lam-viec/PhieuKetQua.tsx");
const GHI = doc("../app/(dashboard)/_lam-viec/phieu-kham/GhiChuLuot.tsx");
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

test("MỘT component phiếu điều trị cho bàn khám và phòng dịch vụ", () => {
  assert.match(KHOI, /import PhieuDieuTri/);
  assert.match(KHOI, /<PhieuDieuTri serviceOrderId=\{t\.order_id\} choGhi=\{ghiPhieu\} banDoc=\{t\.phieu\}/);
  // Phòng: khung kết quả chuyển sang cùng component khi mẫu là phiếu điều trị.
  assert.match(KQ, /import PhieuDieuTri from "\.\/PhieuDieuTri"/);
  assert.match(KQ, /chonMau === MAU_PHIEU_DIEU_TRI/);
  assert.match(KQ, /<PhieuDieuTri serviceOrderId=\{serviceOrderId\} choGhi onXong=\{onHoanTat\}/);
  // Cùng dữ liệu: phiếu kết quả của chỉ định qua engine phiếu (`/api/phieu`).
  assert.match(DT, /fetch\("\/api\/phieu"/);
  assert.match(DT, /form_id: `KQ_\$\{MAU_PHIEU_DIEU_TRI\}`/);
  assert.match(KHOI, /Chưa có chỉ định điều trị — kê ở khối Chỉ định điều trị/);
});

test("phiếu điều trị GỌN: mỗi ô một nhãn, tự lưu, chân Bản n · người · giờ, không Hoàn tất", () => {
  assert.match(DT, /<span className=\{LABEL\}>\{o\.ten\}<\/span>/);
  assert.doesNotMatch(ma(DT), /legend|Phiếu kết quả|Hoàn tất phiếu|Gập phiếu/);
  assert.doesNotMatch(ma(KHOI), /Gập phiếu điều trị|Mở phiếu điều trị|anPhieu/);
  assert.match(DT, /`Bản \$\{revision\} · /);
  assert.match(DT, /<TrangThaiLuu /);
  assert.match(DT, /\/print\/ket-qua\/\$\{serviceOrderId\}/);
  // [Xong] chỉ ở phòng (đóng dịch vụ); bàn khám có [Xong] riêng của thẻ.
  assert.match(DT, /\{onXong \? \(/);
  assert.doesNotMatch(KHOI, /onXong/);
});

test("nút do máy chủ quyết; lệnh đi qua route chuyển tiếp; chỉ đọc sau check-out", () => {
  for (const co of ["lam_duoc", "ly_do_khong_lam", "xong_duoc", "huy_lam_duoc", "hoan_tac_xong_duoc"]) {
    assert.match(KHOI, new RegExp(`t\\.${co}`));
  }
  assert.match(KHOI, /chi_doc/);
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

test('lượt "Khác": MỘT ô chữ tự do, mỗi lần lưu một phiên bản, máy chủ quyết hiện', () => {
  assert.match(LUOT, /<GhiChuLuot visitId=\{visitId\} choGhi=\{choGhi\} \/>/);
  assert.match(GHI, /xem=ghi-chu/);
  assert.match(GHI, /method: "PUT"/);
  assert.match(GHI, /phien_ban: daLuu\.current\.ban/);
  assert.match(GHI, /if \(!gc \|\| !gc\.hien\) return null/);
  assert.match(GHI, /r\.status === 409/);
  assert.match(ROUTE, /export async function PUT/);
  assert.match(ROUTE, /`\/api\/v1\/ho-so-kham\/\$\{vid\}\/ghi-chu`/);
});

test("in gộp một lượt: không báo 'chưa có gì' khi có điều trị / ghi chú; chữ ký cuối cùng", () => {
  assert.doesNotMatch(IN, /chưa mở phiếu khám nào/);
  assert.match(IN, /c\.dieu_tri/);
  assert.match(IN, /<DieuTriIn ds=\{dieuTri\} \/>/);
  assert.match(IN, /ten="Ghi chú"/);
  assert.match(IN, /xem=ghi-chu/);
  assert.match(LIB, /x\.form_id === "KQ_PHIEU_DIEU_TRI"/);
  // Chữ ký bác sĩ LUÔN sau mọi mục, kể cả trang ảnh (memory in-a4).
  const ky = IN.indexOf("<footer");
  for (const truoc of ["<DieuTriIn", 'ten="Ghi chú"', "<TrangAnh"]) {
    assert.ok(IN.lastIndexOf(truoc) < ky, `${truoc} phải trước chữ ký`);
  }
});
