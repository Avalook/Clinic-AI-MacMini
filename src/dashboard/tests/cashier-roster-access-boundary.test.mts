import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { hienTrenThanhBen, legoChoHien, vaoDuocMan } from "../lib/roles.ts";

test("ngoài ca chỉ hiện lịch sử; vai thu ngân không vượt dữ kiện máy chủ", () => {
  const quyen = ["payment.service.history"];
  assert.equal(hienTrenThanhBen("CASHIER", "/thu-ngan/dich-vu", quyen), false);
  assert.equal(vaoDuocMan("/thu-ngan/dich-vu", ["CASHIER"], quyen), false);
  assert.equal(hienTrenThanhBen("CASHIER", "/thu-ngan/dich-vu/lich-su", quyen), true);
  assert.equal(vaoDuocMan("/thu-ngan/thuoc/lich-su", ["CASHIER"], quyen), false);
  assert.equal(legoChoHien(quyen, "/thu-ngan/thuoc"), false);
});

test("không đọc được quyền thì quầy đóng thay vì suy ra từ vai", () => {
  for (const href of ["/thu-ngan/dich-vu", "/thu-ngan/thuoc", "/thu-ngan/dich-vu/lich-su", "/thu-ngan/thuoc/lich-su"]) {
    assert.equal(hienTrenThanhBen("MANAGEMENT", href, null), false);
    assert.equal(vaoDuocMan(href, ["MANAGEMENT"], null), false);
    assert.equal(legoChoHien(null, href), false);
  }
});

test("hai lối lịch sử có cửa gác riêng và luôn chỉ đọc", () => {
  for (const kind of ["dich-vu", "thuoc"]) {
    const source = readFileSync(new URL(`../app/(dashboard)/thu-ngan/${kind}/lich-su/page.tsx`, import.meta.url), "utf8");
    assert.ok(source.includes(`requireNavAccess("/thu-ngan/${kind}/lich-su")`));
    assert.match(source, /<TabThuNgan[^>]*chiXem/);
  }
});


test("đến giờ đổi ca làm mới menu và phạm vi quầy mà không thêm poll", () => {
  const refresher = readFileSync(new URL("../app/(dashboard)/RealtimeRefresher.tsx", import.meta.url), "utf8");
  assert.match(refresher, /Date.parse\(lamMoiQuyenLuc\)/);
  assert.match(refresher, /clearTimeout\(timerQuyen\)/);
  assert.match(refresher, /window.dispatchEvent\(new CustomEvent\(SU_KIEN_DOI_CA\)\)/);
  const days = readFileSync(new URL("../app/(dashboard)/thu-ngan/NgayTruc.tsx", import.meta.url), "utf8");
  assert.match(days, /\[quay, doiCa\]/);
});
