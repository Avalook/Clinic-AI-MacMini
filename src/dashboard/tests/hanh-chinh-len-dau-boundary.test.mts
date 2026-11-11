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

test("chỉ một bản PatientAdminEditor, nằm trong ngăn gập có nhớ trạng thái", () => {
  const cac = [...view.matchAll(/<PatientAdminEditor\b/g)];
  assert.equal(cac.length, 1);
  const ngan = view.indexOf("<NganGap\n                  tieuDe=\"Thông tin hành chính\"");
  const dong = view.indexOf("</NganGap>", ngan);
  const i = cac[0].index ?? -1;
  assert.ok(ngan > 0 && i > ngan && i < dong, "PatientAdminEditor phải nằm trong ngăn gập");
  assert.match(view.slice(ngan, i), /nhoKhoa="khach-hanh-chinh"/);
});
