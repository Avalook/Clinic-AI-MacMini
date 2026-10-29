// "Chưa thu tiền" khi Hoàn tất phiếu là LỜI NHẮC vàng, không phải lỗi đỏ
// (Tuyền 29/10/2026). Mã lỗi máy chủ đi qua lớp chuyển tiếp ở trường `ma_loi`
// (`error` là câu cho người) — bản đầu đọc `error` nên trên staging vẫn đỏ.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("lớp chuyển tiếp đưa mã lỗi máy chủ vào ma_loi", () => {
  const proxy = doc("../lib/backend-proxy.ts");
  assert.match(proxy, /ma_loi: maLoi/);
});

test("PhieuKetQua đọc ma_loi và vẽ CHUA_THU_TIEN thành lời nhắc", () => {
  const src = doc("../app/(dashboard)/_lam-viec/PhieuKetQua.tsx");
  assert.match(src, /d\?\.ma_loi/);
  assert.doesNotMatch(src, /ma: typeof d\?\.error/);
  assert.match(src, /setNhacNut\(kq\.ma === "CHUA_THU_TIEN"\)/);
  assert.match(src, /<BaoLoiCanhNut muc=\{nhacNut \? "nhac" : "loi"\}>/);
});

test("câu nhắc bảo bấm Làm trước – thu sau thì ô ấy phải có sẵn ở cột phải, MỌI lượt", () => {
  // Lượt Thủ thuật / Điều trị từng ẩn ô cột phải, ô khối 1 chỉ hiện khi máy chủ
  // mời → nhắc bấm mà không thấy nút đâu (Tuyền 29/10/2026).
  const luot = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
  assert.match(luot, /\{choGhi \? \(\s*<div className="w-72 shrink-0 lg:w-full">\s*<OLamTruocThuSau visitId=\{visitId\} \/>/);
  assert.doesNotMatch(luot, /choGhi && !khoi1 \?/);
  const khoi = doc("../app/(dashboard)/_lam-viec/phieu-kham/KhoiDieuTri.tsx");
  assert.doesNotMatch(khoi, /OTickTaiCho/, "không vẽ ô thứ hai ở khối 1");
});

test("nhãn Làm trước – thu sau: không tên người tick, giờ xuống dòng ở cột phải", () => {
  const o = doc("../app/(dashboard)/_lam-viec/OLamTruocThuSau.tsx");
  assert.match(o, /return \["Làm trước – thu sau", gio\(lt\.bat_luc\)\]/);
  assert.doesNotMatch(o, /lt\.bat_boi/);
  assert.match(o, /<Chip tone="info">Làm trước – thu sau<\/Chip>\s*\{gio\(tt\.bat_luc\) \?/);
});

test("máy chủ dùng mã CHUA_THU_TIEN cho câu nhắc thu tiền", () => {
  const ex = doc("../../clinicai/core/exceptions.py");
  assert.match(ex, /class ChuaThuTienError\(ValidationError\)/);
  assert.match(ex, /error_code: str = "CHUA_THU_TIEN"/);
});
