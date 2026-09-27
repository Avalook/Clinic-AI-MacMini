// Thanh bên dựng theo QUYỀN, không chỉ theo vai (chốt với Tuyền, 23/09/2026).
//
// Ví dụ trong chính lời chốt: *"Quản lý cấp được bất kỳ khối nào cho bất kỳ ai,
// kể cả cho lễ tân màn siêu âm"*. Trước hôm nay điều đó bất khả thi ở giao
// diện: `NAV_ROLES` chỉ biết vai, nên lễ tân có quyền mà không có lối vào.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { hienTrenThanhBen, quyenMoDuocMan } from "../lib/roles.ts";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("quyền mở được màn mà vai không có", () => {
  // Lễ tân không nằm trong NAV_ROLES của /phong/* (một luật cho mọi room_id).
  const phong = "/phong/5f0c7a2e-0000-4000-8000-000000000001";
  assert.equal(hienTrenThanhBen("RECEPTION", phong), false);
  assert.equal(hienTrenThanhBen("RECEPTION", "/phong"), false);
  // Được cấp khối Thực hiện dịch vụ thì thấy.
  assert.equal(hienTrenThanhBen("RECEPTION", phong, ["service.execute.start"]), true);
});

test("21 lego (25/09): biết quyền thì thanh bên đi CHẶT theo lego", () => {
  // Tuyền 25/09/2026: quyền theo TÀI KHOẢN — thu lego là mất mục, dù vai có.
  assert.equal(hienTrenThanhBen("DOCTOR", "/ban-kham", []), false);
  assert.equal(
    hienTrenThanhBen("DOCTOR", "/ban-kham", ["clinical.consult.perform"]),
    true,
  );
  // Cấp lego ngoài vai: lễ tân được bật Báo cáo thì thấy Báo cáo.
  assert.equal(hienTrenThanhBen("RECEPTION", "/reports", ["report.view"]), true);
  assert.equal(hienTrenThanhBen("RECEPTION", "/reports", []), false);
  // Màn luôn bật (không thuộc lego) vẫn theo luật cũ.
  assert.equal(hienTrenThanhBen("RECEPTION", "/home", []), true);
});

test("backend im (null) thì rơi về luật vai — không để thanh bên trống trơn", () => {
  assert.equal(hienTrenThanhBen("DOCTOR", "/ban-kham", null), true);
});

test("Chờ xếp bác sĩ + Bảng giá thuốc tắt khỏi thanh bên cho mọi người", () => {
  for (const href of ["/appointments/cho-xep-bac-si", "/cashier/thuoc"]) {
    assert.equal(hienTrenThanhBen("MANAGEMENT", href, null), false);
  }
});

test("Thu tiền thuốc mở bằng quyền THU TIỀN THUỐC (sửa gắn nhầm 25/09)", () => {
  assert.equal(quyenMoDuocMan(["payment.medicine.collect"], "/thu-ngan/thuoc"), true);
  assert.equal(quyenMoDuocMan(["payment.service.collect"], "/thu-ngan/thuoc"), false);
});

test("màn không khai quyền thì quyền không mở bừa", () => {
  // Quyền của lego khác không mở /settings; /home không thuộc lego nào.
  assert.equal(quyenMoDuocMan(["permission.manage"], "/settings"), false);
  assert.equal(quyenMoDuocMan([], "/phan-quyen"), false);
  assert.equal(quyenMoDuocMan(["permission.manage"], "/home"), false);
});

test("cửa trang cũng mở theo quyền, không chỉ thanh bên", () => {
  // Ẩn mục trong menu mà gõ thẳng URL vẫn bị đá về /home thì quyền vô dụng.
  const guard = doc("../lib/clinic-session.ts");
  // 27/09/2026: MỘT luật cho mọi trang — `vaoDuocMan(href, vai, quyen)`.
  assert.match(guard, /getQuyenCuaToi\(\)\]\);\s*return vaoDuocMan\(href, vai, quyen\)/);
  // Backend im → null (khác [] = biết chắc không có quyền) → thanh bên rơi về
  // luật vai, không khoá cả phòng khám.
  assert.match(guard, /return d\?\.quyen \?\? null/);
});

test("thanh bên và thanh dưới dùng chung một luật", () => {
  // Hai thanh lệch nhau là người dùng mất màn ở một cỡ màn hình.
  for (const f of ["../app/(dashboard)/Nav.tsx", "../app/(dashboard)/BottomNav.tsx"]) {
    assert.match(
      doc(f),
      /\(r, href\) => hienTrenThanhBen\(r, href, quyen\)/,
      `${f} phải truyền quyền vào bộ lọc`,
    );
  }
});
