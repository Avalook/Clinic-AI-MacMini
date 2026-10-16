import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// LUỒNG ĐỐI TÁC CHUNG (Tuyền 16/10/2026).
//
//   1. Tài khoản đối tác: thanh bên CHỈ "Việc của đối tác" — bấm thử staging thấy
//      cả "Trang chủ" và "Kế toán" (/ke-toan không có dòng NAV_ROLES nên luật gốc
//      mở cho mọi vai khi `quyen` null — mà đối tác luôn null).
//   2. Bàn /doi-tac: không còn dòng tóm tắt, không "Lấy mẫu", không "Có mẫu ·
//      chờ nhận"; chỉ hai chữ riêng của đối tác.
//   3. Phòng đối tác ở /phong: nút cuối "Đã nhận mẫu" gọi CÙNG lệnh với bàn.

import { canSeeNav, canSeeNavGoc, hienTrenThanhBen, vaoDuocMan } from "../lib/roles.ts";

test("đối tác: thanh bên chỉ /doi-tac — không Trang chủ, không Kế toán", () => {
  assert.equal(hienTrenThanhBen("PARTNER", "/doi-tac", null), true);
  for (const href of ["/home", "/ke-toan", "/hanh-trinh", "/phong", "/reports", "/customers"]) {
    assert.equal(hienTrenThanhBen("PARTNER", href, null), false, href);
    assert.equal(canSeeNav("PARTNER", href), false, href);
    assert.equal(canSeeNavGoc("PARTNER", href), false, href);
    assert.equal(vaoDuocMan(href, ["PARTNER"], null), false, href);
  }
  assert.equal(vaoDuocMan("/doi-tac", ["PARTNER"], null), true);
});

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("bàn /doi-tac theo luồng mới — không Lấy mẫu, không dòng tóm tắt", () => {
  const bang = doc("../app/doi-tac/BangDoiTac.tsx");
  assert.ok(!bang.includes("/api/doi-tac/da-lay-mau"), "bỏ nút Đã lấy mẫu");
  assert.ok(!bang.includes("Có mẫu · chờ nhận"));
  assert.ok(!bang.includes("chờ lấy\n          mẫu"), "bỏ dòng tóm tắt");
  assert.ok(bang.includes("KetQuaDoiTac"), "phiếu + Trả kết quả");
  assert.ok(bang.includes("/api/doi-tac/phieu"), "đối tác điền phiếu qua cửa đối tác");
  const khoi = doc("../app/(dashboard)/_lam-viec/KhoiDoiTac.tsx");
  assert.ok(khoi.includes('"Đã nhận mẫu · chờ kết quả"'));
  assert.ok(khoi.includes('"Có kết quả"'));
  assert.ok(!khoi.includes("tham khảo"), "bỏ dòng Thu hộ đối tác · tham khảo");
  assert.ok(!khoi.includes("Chưa thu hộ"), "bỏ chip Chưa thu hộ");
});

test("phòng đối tác: Đã nhận mẫu = cùng lệnh bàn đối tác", () => {
  const phong = doc("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
  assert.ok(phong.includes('DOI_TAC: "Đã nhận mẫu"'));
  assert.ok(phong.includes("/api/doi-tac/cho-tai-lieu"));
  assert.ok(phong.includes("la_doi_tac"));
});
