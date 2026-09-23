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
  // Lễ tân không nằm trong NAV_ROLES của /phong/*.
  assert.equal(hienTrenThanhBen("RECEPTION", "/phong/KN-SA1"), false);
  // Được cấp khối Thực hiện dịch vụ thì thấy.
  assert.equal(
    hienTrenThanhBen("RECEPTION", "/phong/KN-SA1", ["service.execute.start"]),
    true,
  );
});

test("mở THÊM chứ không thay — không ai mất lối vào cũ", () => {
  // Bác sĩ vẫn thấy bàn khám kể cả khi danh sách quyền rỗng (backend im).
  assert.equal(hienTrenThanhBen("DOCTOR", "/ban-kham", []), true);
});

test("màn không khai quyền thì quyền không mở bừa", () => {
  // Không có quyền nào trỏ tới /settings → giữ nguyên luật vai.
  assert.equal(quyenMoDuocMan(["permission.manage"], "/settings"), false);
  assert.equal(quyenMoDuocMan([], "/phan-quyen"), false);
});

test("cửa trang cũng mở theo quyền, không chỉ thanh bên", () => {
  // Ẩn mục trong menu mà gõ thẳng URL vẫn bị đá về /home thì quyền vô dụng.
  const guard = doc("../lib/clinic-session.ts");
  assert.match(guard, /quyenMoDuocMan\(await getQuyenCuaToi\(\), href\)/);
  // Backend im thì rơi về luật vai, không khoá cả phòng khám.
  assert.match(guard, /return d\?\.quyen \?\? \[\]/);
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
