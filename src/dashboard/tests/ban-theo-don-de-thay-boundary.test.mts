import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// BÁN THEO ĐƠN — làm cho dễ THẤY (Tuyền bấm thử 16/10/2026: "chưa hình dung ra
// thao tác, chưa thấy các đơn thuốc trước của khách, chưa thấy chỗ bán theo đơn").
// Luật nghiệp vụ không đổi (chỉ nhắc, không chặn; lần bán gắn lượt khám có đơn
// gốc) — bài này khoá phía màn: khách được chọn là đơn cũ hiện ngay, lối bán lẻ trơn
// đứng SAU, nối đơn xong có lời báo giữ lại, chip "Vượt số kê" nằm ở dòng giỏ.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const khach = doc("app/(dashboard)/pharmacy/KhachMuaThuoc.tsx");
const lichSu = doc("app/(dashboard)/pharmacy/LichSuDonThuoc.tsx");
const banLe = doc("app/(dashboard)/pharmacy/BanLeThu.tsx");
const board = doc("app/(dashboard)/pharmacy/PharmacyBoard.tsx");
const gio = doc("app/(dashboard)/thu-ngan/ChinhDonQuay.tsx");
const kho = doc("app/(dashboard)/pharmacy/inventory/KhoThuoc.tsx");
const kho2 = doc("app/(dashboard)/pharmacy/thong-bao-noi-don.ts");

test("chọn khách là đơn thuốc cũ hiện ngay — không cần bấm tên", () => {
  // Một kết quả duy nhất → chọn luôn.
  assert.match(khach, /if \(ds\.length === 1\) setChon\(ds\[0\]\.clinic_patient_id\);/);
  // Dòng kết quả chỉ để CHỌN khách; không còn nút mở lượt trần ở từng dòng.
  assert.doesNotMatch(khach, /^\s*Mở lượt mua thuốc\s*$/m);
  assert.match(khach, /Xem đơn thuốc/);
  // Có chữ "đang tìm" trong lúc đợi máy chủ (không nhấp nháy "Không thấy khách").
  assert.match(khach, /daTim !== tim\.trim\(\)/);
  assert.match(khach, /Đang tìm khách…/);
});

test("lối bán lẻ trơn đổi nhãn và đứng SAU danh sách đơn", () => {
  assert.match(khach, /Bán lẻ — không theo đơn/);
  const iDon = khach.indexOf("<LichSuDonThuoc");
  const iLe = khach.lastIndexOf("Bán lẻ — không theo đơn");
  assert.ok(iDon > 0 && iLe > iDon, "nút bán lẻ phải nằm sau khối lịch sử đơn");
  assert.match(lichSu, /bấm “Bán lẻ — không theo đơn” bên dưới/);
});

test("khung chờ lịch sử đơn có chữ và khung xám", () => {
  assert.match(lichSu, /Đang tải đơn thuốc của khách…/);
  assert.match(lichSu, /className="skeleton h-10 w-full"/);
});

test("Bán theo đơn này: lời báo nói đơn nào, mấy thuốc, thuốc nào không thêm được", () => {
  assert.match(lichSu, /Đã mở lượt bán theo đơn/);
  assert.match(lichSu, /Đã nối lượt này với đơn/);
  assert.match(lichSu, /thuốc đã thêm vào giỏ/);
  assert.match(lichSu, /Không thêm được \$\{boQua\.length\} thuốc:/);
  // Chưa có lượt: ghim lời báo cho lượt máy chủ vừa mở RỒI mới báo màn cha chọn lượt.
  assert.match(
    lichSu,
    /baoNoiDon\(kq\.d\.visit_id, cau\);\s*onMo\?\.\(kq\.d\.visit_id\);/,
  );
  // Lượt đang mở: nạp lại trước (thao tác xoá lời báo cũ) rồi mới ghim lời mới.
  assert.match(lichSu, /await onDoi\(null, null\);\s*baoNoiDon\(visitId, cau\);/);
});

test("lời báo nối đơn GIỮ trên khung lượt tới khi thao tác hoặc bấm Ẩn", () => {
  assert.match(banLe, /const noiDon = useNoiDon\(visitId\);/);
  assert.match(banLe, /\{baoNoi\}/);
  assert.match(banLe, /onClick=\{anNoiDon\}/);
  // Thu / sửa giỏ / nối-gỡ đơn đều xoá lời báo cũ.
  assert.ok((banLe.match(/anNoiDon\(\);/g) ?? []).length >= 4);
  // Không phải toast tự tắt.
  assert.doesNotMatch(kho2, /setTimeout/);
  assert.doesNotMatch(banLe + lichSu, /setTimeout/);
  // Lối từ Kho thuốc: cùng component, điều hướng giữ bộ nhớ trang nên lời báo đi theo.
  assert.match(kho, /<KhachMuaThuoc sangNhaThuoc \/>/);
});

test("mở lượt xong: chọn đúng lượt, cuộn tới khung, viền + chip Vừa mở", () => {
  assert.match(board, /canCuon\.current = id;/);
  assert.match(board, /scrollIntoView\(\{ behavior: "smooth", block: "start" \}\)/);
  assert.match(board, /focus\(\{ preventScroll: true \}\)/);
  assert.match(board, /vuaMo === luot\.visit_id \? "border-brand-600" : "border-line"/);
  assert.match(board, /<Chip tone="brand">Vừa mở<\/Chip>/);
  // Đi từ Kho thuốc (?luot=) cũng đánh dấu + cuộn.
  assert.match(board, /useState<string \| null>\(chonDau\)/);
});

test("chip Vượt số kê nằm ở dòng thuốc trong giỏ; chỉ nhắc, không khoá nút", () => {
  assert.match(gio, /Vượt số kê — đã mua \{td\.da_mua\} \+ đang bán \{td\.dang_ban\} \/ kê/);
  assert.match(gio, /td\?\.vuot/);
  // Số liệu đến từ lịch sử đơn (máy chủ tính `vuot`), BanLeThu chỉ chuyển đi.
  assert.match(lichSu, /onGoi\?: \(goi: GoiLichSu \| null\) => void;/);
  assert.match(banLe, /theoDon=\{donNoi \? theoDon : undefined\}/);
  assert.match(banLe, /nhacChung=\{donNoi \? goiDon\?\.nhac_chung : undefined\}/);
  // Không có điều kiện nào khoá nút từ cờ vượt.
  assert.doesNotMatch(gio, /disabled=\{[^}]*vuot/);
  assert.doesNotMatch(banLe, /disabled=\{[^}]*vuot/);
  // QuayThuNgan dùng chung ChinhDonQuay: prop mới đều tuỳ chọn.
  assert.match(gio, /theoDon\?: Record<string, TheoDonDong>;/);
  assert.match(gio, /nhacChung\?: string\[\];/);
});

test("dòng đơn cũ chưa gắn thuốc kho: có giải thích và lối chọn thuốc kho", () => {
  assert.match(lichSu, /Đơn cũ nhập từ hồ sơ giấy nên chưa biết đây là thuốc nào trong kho/);
  // Không còn cụm "Kê — · Đã mua 0 · Còn —" cho dòng chưa gắn kho.
  assert.match(lichSu, /\{d\.drug_catalog_id \? \(\s*<span className="text-meta tabular-nums text-ink-soft">/);
  assert.match(lichSu, /Chọn thuốc kho/);
  assert.match(banLe, /goiYThuoc=\{goiYThuoc\}/);
  assert.match(gio, /tuKhoaDau=\{goiYThuoc\?\.ten\}/);
});
