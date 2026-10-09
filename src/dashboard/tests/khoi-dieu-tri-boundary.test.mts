import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Thẻ chỉ định điều trị của hồ sơ khám (Tuyền chốt 07/10/2026 chiều + phản hồi bấm
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
const KQC = doc("../app/(dashboard)/_lam-viec/phieu-kham/KetQuaChiDinh.tsx");
const GHI = doc("../app/(dashboard)/_lam-viec/phieu-kham/GhiChuLuot.tsx");
const DV = doc("../app/(dashboard)/_lam-viec/phieu-kham/KhoiDichVuHoSo.tsx");
const ROUTE = doc("../app/api/ho-so-kham/route.ts");
const IN = doc("../app/print/phieu-kham/[visitId]/InPhieuKham.tsx");

// Sắp lại khối (Tuyền chốt 08/10 — docs/KE-HOACH-LIEU-TRINH.md Phần A): thẻ điều
// trị DỜI vào đầu khối 3 "Chỉ định điều trị", khối 4 là "Đơn thuốc" (mục E), mục D
// "Chẩn đoán và xử lý" DỜI xuống cuối khối 2 (CLS → kết quả → chẩn đoán → điều
// trị), SỬA ĐƯỢC, mọi phiếu — HMVS 16 ô / NT 9 ô không được mất.
test("bốn khối: 2 = CLS + Chẩn đoán (C · D), 3 = Chỉ định điều trị (F · G), 4 = Đơn thuốc (E)", () => {
  assert.match(LIB, /\{ so: 1, ten: "Thông tin cơ bản", muc: \["A", "B"\] \}/);
  assert.match(LIB, /\{ so: 2, ten: "Chỉ định cận lâm sàng", muc: \["C", "D"\] \}/);
  assert.match(LIB, /\{ so: 3, ten: "Chỉ định điều trị", muc: \["F", "G"\] \}/);
  assert.match(LIB, /\{ so: 4, ten: "Đơn thuốc", muc: \["E"\] \}/);
  assert.doesNotMatch(LIB, /ten: "Điều trị", muc/);
  // Khối 4 luôn có (không ẩn khi không có điều trị).
  assert.doesNotMatch(PHIEU, /cacKhoi|tomTatDieuTri/);
  assert.match(PHIEU, /\{KHOI\.map\(\(k\) =>/);
  // Tóm tắt thanh bước bên phải.
  assert.match(PHIEU, /`\$\{ketQuaDT\.length\} điều trị`/);
  assert.match(PHIEU, /`\$\{ketQuaTT\.length\} thủ thuật`/);
  assert.match(PHIEU, /4: soThuoc \? `\$\{soThuoc\} thuốc`/);
});

test("mục D cuối khối 2: sửa được như mọi mục, mở sẵn, tóm tắt 'có chẩn đoán'", () => {
  // Không còn đường "bỏ mục" / chỉ đọc riêng cho D.
  assert.doesNotMatch(LIB + PHIEU, /MUC_DA_BO|đã ghi trước đây/);
  assert.match(PHIEU, /<NhomOPhieu key=\{`\$\{m\.ma\}-\$\{i\}`\} nhom=\{n\} gia=\{gia\} onDoi=\{doi\} chiDoc=\{!ghi\}/);
  assert.match(PHIEU, /D: \{ ten: "Chẩn đoán và xử lý"/);
  // Mục gõ đầu của khối mở sẵn (khối 2: danh mục C không có ô → D mở).
  assert.match(PHIEU, /m\.lien_ket\?\.loai !== "mang_sang" && m\.block\.length > 0/);
  assert.match(PHIEU, /m\.ma === mucDau\(mucKhoi\) \|\| m\.ma === mucGoDau/);
  assert.match(PHIEU, /coChanDoan \? " · có chẩn đoán" : ""/);
});

test("khối 3 xếp: thẻ điều trị → (D cũ) → thủ thuật đã chỉ định → lưới Dịch vụ khác → Hẹn khám", () => {
  assert.match(PHIEU, /\{khoi === 3 \? oDieuTri : null\}\s*\{mucKhoi\.map/);
  assert.doesNotMatch(PHIEU, /khoi === 4 \? oDieuTri/);
  // Thẻ thủ thuật ở thẻ con RIÊNG đứng trước thẻ con của mục F (lưới chọn).
  const tt = PHIEU.indexOf('ten="Thủ thuật đã chỉ định"');
  const theMucF = PHIEU.indexOf("ten={td.ten}", tt);
  assert.ok(tt > 0 && theMucF > tt, "thẻ thủ thuật phải đứng trên lưới");
  const noiDung = PHIEU.slice(PHIEU.indexOf("const noiDung = ("), PHIEU.indexOf("return (", PHIEU.indexOf("const noiDung = (")));
  assert.doesNotMatch(noiDung, /<KetQuaChiDinh/, "không còn thẻ nằm dưới lưới");
});

test("MỘT định nghĩa điều trị: cờ dieu_tri máy chủ, không dò maThuThuat", () => {
  assert.match(LIB, /if \(c\.dieu_tri\) ra\.dieuTri\.push\(c\);\s*else if \(maThuThuat\?\.has/);
  assert.match(PHIEU, /phanChiDinh\(ketQuaChiDinh, maThuThuat, khoi1\)/);
  assert.doesNotMatch(PHIEU, /laTT/);
  assert.match(LUOT, /phanChiDinh\(ketQua, maThuThuat, khoi1\)/);
  assert.match(LUOT, /const dsDieuTri = phan\.dieuTri;/);
});

test("thẻ điều trị = khung thẻ chỉ định + phần điều trị (một thẻ mỗi chỉ định)", () => {
  assert.match(KHOI, /<KetQuaChiDinh ds=\{chiDinh\} \{\.\.\.ketQua\} dieuTri=\{\{ chip, than \}\} \/>/);
  // Khung thẻ: Hoàn tác chỉ định, Ảnh · tệp, tiền giữ nguyên; không [Mở phiếu kết
  // quả] và không tóm tắt (phiếu 2 ô đã nằm trong thẻ); mọi lần hiện cùng nhau.
  assert.match(KQC, /choSua && !dieuTri \?/);
  assert.match(KQC, /coKq && !dieuTri \?/);
  assert.match(KQC, /const nhieuLan = !dieuTri && cacLan\.length > 1/);
  assert.match(KQC, /chipDieuTri \?\? <Chip tone=\{tt\.tone\}>/);
  assert.match(KQC, /nhan="Hoàn tác chỉ định"/);
  // Shell dựng MỘT bộ thuộc tính thẻ cho cả phiếu đầy đủ lẫn hồ sơ tối giản.
  assert.match(LUOT, /oDieuTri=\{chiMuc \|\| khoi1 \? undefined : theDieuTri\}/);
  assert.match(LUOT, /<KhoiDieuTri visitId=\{visitId\} choGhi=\{choGhi\} chiDinh=\{dsDieuTri\} ketQua=\{propsKetQua\} \/>/);
  assert.match(LUOT, /ketQua=\{propsKetQua\}/);
});

test("hồ sơ tối giản: thẻ điều trị → đã chỉ định (không lặp điều trị) → kê chỉ định", () => {
  const tg = LUOT.slice(LUOT.indexOf("if (chonDuoc) {"), LUOT.indexOf("if (!phieu) {"));
  const a = tg.indexOf("{theDieuTri}");
  const b = tg.indexOf("Đã chỉ định &amp; kết quả");
  const c = tg.indexOf("Kê chỉ định");
  assert.ok(a > 0 && a < b && b < c, "thứ tự thẻ điều trị → đã chỉ định → kê chỉ định");
  assert.match(tg, /ketQua\.filter\(\(c\) => !dsDieuTri\.includes\(c\)\)/);
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
  assert.match(KHOI, /Chưa có chỉ định điều trị — chọn dịch vụ điều trị ở danh mục bên dưới/);
  // Chưa có chỉ định điều trị: dòng gợi ý (khi ghi được) + phần liệu trình
  // (liệu trình chỉ đề xuất, lối "Chỉ đề xuất") — 08/10/2026.
  assert.match(KHOI, /if \(chiDinh\.length === 0\) \{\s*return \(\s*<div className="space-y-2">\s*\{choGhi && goiYTrong \?/);
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

test('"Khách đã đặt" nằm ở thẻ điều trị', () => {
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

// KHỐI 1 THEO LOẠI LƯỢT (Tuyền chốt 09/10/2026): lượt Điều trị / Thủ thuật vẽ
// thẻ làm tại bàn khám ở KHỐI 1 (`oKhoi1`), KHÔNG vẽ lại ở khối 3; lượt Điều trị
// ẩn mục A/B; ô "Làm trước – thu sau" chỉ khi máy chủ mời, không hai bản.
test("khối 1: oKhoi1 đầu khối 1, thẻ điều trị không vẽ hai lần", () => {
  assert.match(PHIEU, /\{khoi === 1 \? oKhoi1 : null\}/);
  assert.match(PHIEU, /const an = khoi === 1 \? mucAnKhoi1\(khoi1\) : \[\];/);
  assert.match(LIB, /return khoi1 === "DIEU_TRI" \? \["A", "B"\] : \[\];/);
  // Khối 1 dùng thẻ `ban_kham`; khối 3 bỏ thẻ khi lượt có khối 1 riêng.
  assert.match(LUOT, /chiDinh=\{dsBanKham\}/);
  assert.match(LUOT, /oKhoi1=\{oKhoi1\}/);
  assert.match(LUOT, /khoi1=\{khoi1\}/);
  assert.match(LIB, /if \(khoi1 && c\.ban_kham\) ra\.banKham\.push\(c\);/);
  // Lượt Thủ thuật: nút gọn chọn thủ thuật ĐẦU khối 1, mục B vẫn hiện.
  assert.match(LUOT, /khoi1 === "THU_THUAT" \? \(\s*<ChonThuThuatBanKham/);
  // Hồ sơ tối giản: thẻ điều trị đứng đầu (trước ô ghi chú lượt Khác).
  const tg = LUOT.slice(LUOT.indexOf("if (chonDuoc) {"), LUOT.indexOf("if (!phieu) {"));
  assert.ok(tg.indexOf("{theDieuTri}") < tg.indexOf("<GhiChuLuot"), "thẻ điều trị trước ghi chú");
});

test("ô Làm trước – thu sau ở khối 1: chỉ khi máy chủ mời, cột phải chỉ lượt khám thường", () => {
  assert.match(KHOI, /oTick && choGhi && !chiDoc \? <OTickTaiCho visitId=\{visitId\} moi=\{nhacTick\} onDoi=\{nap\} \/>/);
  assert.match(KHOI, /setNhacTick\(Boolean\(d\.nhac_tick\)\)/);
  assert.match(LUOT, /\{choGhi && !khoi1 \? \(\s*<div className="w-72 shrink-0 lg:w-full">\s*<OLamTruocThuSau visitId=\{visitId\} \/>/);
  assert.match(LUOT, /oTick\s*\n\s*goiYTrong=/);
});

test("bản in lượt Điều trị: tiêu đề theo khung trung tính 'Hồ sơ điều trị', không 'Phiếu thủ thuật'", () => {
  // Máy chủ mở khung HO_SO_DIEU_TRI cho lượt Điều trị; bản in lấy tiêu đề từ `ten`.
  assert.match(IN, /tieuDe=\{TIEU_DE_PHAN\[phan\] \?\? phieu\?\.ten \?\? "Hồ sơ lượt khám"\}/);
  const hs = JSON.parse(doc("../../clinicai/phieu_kham/dinh_nghia/HO_SO_DIEU_TRI.json")) as {
    ten: string;
    khung: { ma: string }[];
  };
  assert.equal(hs.ten, "Hồ sơ điều trị");
  assert.deepEqual(
    hs.khung.map((m) => m.ma),
    ["HANH_CHINH", "C", "D", "E", "F", "G"],
  );
  // Màn không tự chọn phiếu cho lượt Điều trị (máy chủ quyết khung).
  assert.doesNotMatch(LUOT, /napPhieu\("THU_THUAT"\)|"HO_SO_DIEU_TRI"/);
});

test("chọn thủ thuật: một lệnh máy chủ, lọc ở lib, ô bấm ≥40px", () => {
  const CHON = doc("../app/(dashboard)/_lam-viec/phieu-kham/ChonThuThuatBanKham.tsx");
  assert.match(CHON, /thao_tac: "chon-thu-thuat", visit_id: visitId, service_code: m\.service_code/);
  assert.match(CHON, /danhSachThuThuatBanKham\(ds, tu\)/);
  assert.match(CHON, /＋ Thủ thuật đã làm/);
  assert.match(CHON, /aria-expanded=\{hienDs\}/);
  assert.match(CHON, /min-h-10/);
  assert.doesNotMatch(ma(CHON), /window\.confirm|style=\{\{/);
  assert.match(ROUTE, /body\?\.thao_tac === "chon-thu-thuat"/);
  assert.match(ROUTE, /\/api\/v1\/ho-so-kham\/\$\{vid\}\/dieu-tri\/chon-thu-thuat/);
});
