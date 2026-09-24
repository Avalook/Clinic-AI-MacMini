import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Thanh bên theo VỊ TRÍ (Tuyền chốt 16/09/2026). Đọc `nav-items.ts` bằng chữ
// thay vì import: tệp ấy kéo theo cả bộ icon, còn thứ cần canh ở đây chỉ là
// hai bảng khai báo.
//
// Danh mục vị trí nay nằm trong DATABASE (CORE-C4, 23/09/2026) — ba bài "mọi
// vị trí đều có màn / có nhóm / không có mã ma" chuyển sang bài kiểm có
// database: src/tests/services/test_vi_tri_tu_database_db.py.

const nav = readFileSync(
  new URL("../app/(dashboard)/nav-items.ts", import.meta.url),
  "utf8",
);

const khoiViTri = nav.slice(
  nav.indexOf("export const MAN_THEO_VI_TRI"),
  nav.indexOf("export function hrefTheoViTri"),
);
const hrefDaKhai = new Set(
  [...khoiViTri.matchAll(/"(\/[a-z0-9/-]*)"/g)].map((m) => m[1]),
);
const hrefTrongNav = new Set(
  [...nav.matchAll(/href:\s*"(\/[a-z0-9/-]*)"/g)].map((m) => m[1]),
);

test("mọi màn khai theo vị trí đều TỒN TẠI trong thanh bên", () => {
  // Khai một href không có trong NAV thì `mucHienRa` lặng lẽ bỏ nó — vị trí ấy
  // mất đúng màn chính của mình mà không có lỗi nào để thấy.
  const khongCo = [...hrefDaKhai].filter((h) => !hrefTrongNav.has(h));
  assert.deepEqual(khongCo, [], `màn không tồn tại: ${khongCo.join(", ")}`);
});

test("quản lý KHÔNG bị thu thanh bên về theo vị trí", () => {
  const i = nav.indexOf("export function mucHienRa");
  const than = nav.slice(i, i + 2600);
  assert.match(than, /role !== "MANAGEMENT"/);
});

test("không có ca hôm nay thì rơi về menu theo vai, không trống trơn", () => {
  const i = nav.indexOf("export function mucHienRa");
  const than = nav.slice(i, i + 2600);
  assert.match(than, /return NAV\.filter\(\(item\) => hienTrenThanhBen\(role, item\.href\)/);
});

