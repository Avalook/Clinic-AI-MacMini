import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// THÔNG TIN HÀNH CHÍNH LÊN ĐẦU (chị Hoài, 11/11/2026). Ở `/customers` khối sửa thông
// tin bệnh nhân từng nằm CUỐI cột phải — đo trên staging: nút "Sửa thông tin" ở
// ~2.300px trong khung cuộn 718px (1280), ~9.800px (375). Bài này canh nó đứng đầu
// thân cột phải, trong một ngăn gập, và chỉ có MỘT bản (không mọc thêm bản thứ hai).

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const view = doc("../app/(dashboard)/customers/CustomersView.tsx");

test("khối hành chính là thứ đầu tiên trong thân cột phải", () => {
  const than = view.indexOf('<div className="space-y-3 py-4">');
  const ngan = view.indexOf('tieuDe="Thông tin hành chính"');
  assert.ok(than > 0 && ngan > than, "ngăn Thông tin hành chính phải nằm trong thân cột phải");
  for (const sau of [
    "{canManage && apptSuaDuoc ? (", // thẻ lịch đang xem
    "{canOperateCskh && (\n                <div", // khung xác nhận lịch & gọi điện
    "<KhungKhach",
    "<LichSuNotion",
    "Đặt lịch mới",
  ]) {
    const i = view.indexOf(sau, than);
    assert.ok(i > ngan, `"${sau.split("\n")[0]}" phải đứng SAU khối hành chính`);
  }
});

/** Vị trí mở / đóng của ngăn "Thông tin hành chính" — không phụ thuộc thụt dòng. */
function ngan(): { mo: number; dong: number; dau: string } {
  // Thuộc tính đứng thứ tự nào cũng được (`co="the"` có thể đứng trước `tieuDe`).
  const m = /<NganGap\s+(?:\w+="[^"]*"\s+)*tieuDe="Thông tin hành chính"/.exec(view);
  assert.ok(m, "không thấy ngăn Thông tin hành chính");
  const dong = view.indexOf("</NganGap>", m.index);
  const dauHet = view.indexOf(">\n", m.index);
  return { mo: m.index, dong, dau: view.slice(m.index, dauHet) };
}

test("cả hai nhánh (sửa được / chỉ xem) nằm trong ngăn, chỉ một bản mỗi nhánh", () => {
  const { mo, dong } = ngan();
  const sua = [...view.matchAll(/<PatientAdminEditor\b/g)];
  assert.equal(sua.length, 1);
  const i = sua[0].index ?? -1;
  assert.ok(i > mo && i < dong, "PatientAdminEditor phải nằm trong ngăn gập");
  // Nhánh chỉ xem: dòng "Kênh đặt gần nhất" của khung phải cũng phải nằm trong ngăn.
  const xem = [...view.matchAll(/label="Kênh đặt gần nhất"/g)];
  assert.equal(xem.length, 1);
  const j = xem[0].index ?? -1;
  assert.ok(j > mo && j < dong, "nhánh chỉ xem phải nằm trong ngăn gập");
});

test("người sửa được: gập mặc định; người chỉ xem: mở sẵn; nhớ theo người", () => {
  const { dau } = ngan();
  // Người sửa = quyền SỬA HÀNH CHÍNH (khớp máy chủ), không phải `canEdit` (gồm cả đặt lịch).
  assert.match(dau, /moSan=\{!canSuaHanhChinh\}/);
  // Tiêu đề to + đậm (dáng `the`), không phải dòng chữ nhỏ mờ (Tuyền 13/11).
  assert.match(dau, /co="the"/);
  assert.match(dau, /nhoKhoa="khach-hanh-chinh"/);
});
