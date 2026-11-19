// Nháp "Lấy thêm thuốc" KHÔNG được nằm trong state của `ChinhDonQuay` (16/11/2026).
//
// Prod 16/11: khung bị gắn lại sau mỗi lần trang làm mới → thuốc vừa chọn + số đang
// gõ mất, quầy bán lẻ không thêm được thuốc. Nháp sống ở `lib/nhap-lay-them` (theo
// lượt). Máy này giữ cho không ai đưa nó về `useState` — tsc và test hành vi của kho
// không bắt được việc component thôi dùng kho.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const chinh = readFileSync(
  new URL("../app/(dashboard)/thu-ngan/ChinhDonQuay.tsx", import.meta.url),
  "utf8",
);

test("ChinhDonQuay đọc nháp + lời từ chối từ kho theo lượt", () => {
  assert.match(chinh, /useSyncExternalStore\(\s*khoNhapLayThem\.nghe,\s*\(\) => khoNhapLayThem\.doc\(visitId\)/);
  assert.match(chinh, /const them = nhap\.dong;/);
  assert.match(chinh, /const loiTaiCho = nhap\.loi;/);
});

test("nháp không còn là state của component (gắn lại là mất)", () => {
  assert.doesNotMatch(chinh, /useState<DongThuoc\[\]>/);
  assert.doesNotMatch(chinh, /\[loiTaiCho, setLoiTaiCho\] = useState/);
});

test("bị từ chối thì giữ nháp; chỉ bỏ nháp khi lưu được", () => {
  assert.match(chinh, /if \(!loi\) khoNhapLayThem\.bo\(visitId\);/);
});
