import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { STATIONS } from "../lib/roster.ts";

// Thanh bên theo VỊ TRÍ (Tuyền chốt 16/09/2026). Đọc `nav-items.ts` bằng chữ
// thay vì import: tệp ấy kéo theo cả bộ icon, còn thứ cần canh ở đây chỉ là
// hai bảng khai báo.

const nav = readFileSync(
  new URL("../app/(dashboard)/nav-items.ts", import.meta.url),
  "utf8",
);

const khoiViTri = nav.slice(
  nav.indexOf("export const MAN_THEO_VI_TRI"),
  nav.indexOf("export function hrefTheoViTri"),
);
const maViTriDaKhai = new Set(
  [...khoiViTri.matchAll(/^\s+([A-Z0-9_]+):\s*\[/gm)].map((m) => m[1]),
);
const hrefDaKhai = new Set(
  [...khoiViTri.matchAll(/"(\/[a-z0-9/-]*)"/g)].map((m) => m[1]),
);
const hrefTrongNav = new Set(
  [...nav.matchAll(/href:\s*"(\/[a-z0-9/-]*)"/g)].map((m) => m[1]),
);

test("MỌI vị trí trong lịch đều có màn để mở", () => {
  // Thiếu một mã ở đây thì người đứng vị trí ấy hôm đó nhận thanh bên trống
  // — hoặc tệ hơn, rơi về menu theo vai mà không ai hiểu vì sao.
  const thieu = STATIONS.map((s) => s.key).filter((k) => !maViTriDaKhai.has(k));
  assert.deepEqual(thieu, [], `vị trí chưa khai màn: ${thieu.join(", ")}`);
});

test("mọi màn khai theo vị trí đều TỒN TẠI trong thanh bên", () => {
  // Khai một href không có trong NAV thì `mucHienRa` lặng lẽ bỏ nó — vị trí ấy
  // mất đúng màn chính của mình mà không có lỗi nào để thấy.
  const khongCo = [...hrefDaKhai].filter((h) => !hrefTrongNav.has(h));
  assert.deepEqual(khongCo, [], `màn không tồn tại: ${khongCo.join(", ")}`);
});

test("không có mã vị trí MA trong bảng màn", () => {
  // Mã khai ở đây mà không có trong danh mục là dấu vết của một lần đổi mã
  // (như đợt bỏ danh mục Hào Nam) — nó không bao giờ khớp ai.
  const ma = new Set(STATIONS.map((s) => s.key));
  const thua = [...maViTriDaKhai].filter((k) => !ma.has(k));
  assert.deepEqual(thua, [], `mã không còn trong danh mục: ${thua.join(", ")}`);
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
