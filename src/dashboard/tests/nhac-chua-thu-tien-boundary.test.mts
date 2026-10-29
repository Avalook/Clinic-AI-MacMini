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

test("câu nhắc chưa thu tiền kèm ngay ô Làm trước – thu sau (khối 2 Bàn khám)", () => {
  // Nhắc "bấm Làm trước – thu sau" mà không có nút ở đó (Tuyền 29/10/2026).
  const src = doc("../app/(dashboard)/_lam-viec/PhieuKetQua.tsx");
  assert.match(src, /\{nhacNut && luotId \? \(\s*<OLamTruocThuSau\s+visitId=\{luotId\}/);
  const the = doc("../app/(dashboard)/_lam-viec/phieu-kham/KetQuaChiDinh.tsx");
  assert.match(the, /luotId=\{dauDoLuot\}/);
});

test("máy chủ dùng mã CHUA_THU_TIEN cho câu nhắc thu tiền", () => {
  const ex = doc("../../clinicai/core/exceptions.py");
  assert.match(ex, /class ChuaThuTienError\(ValidationError\)/);
  assert.match(ex, /error_code: str = "CHUA_THU_TIEN"/);
});
