// VAI "KẾ TOÁN" `ACCOUNTANT` (16/10/2026) — chỉ là NHÃN để chọn ở ô Vai khi thêm
// nhân viên. Quyền thật vẫn là lego Kế toán (`accounting.finance.full`), nên ở
// giao diện: vai này xuất hiện trong danh sách/nhãn/landing, nhưng KHÔNG mở thêm
// màn nào khi máy chủ đã trả lời quyền (backend: test_vai_ke_toan_db.py).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  ALL_ROLES,
  ROLE_LABEL,
  canSeeNavGoc,
  hienTrenThanhBen,
  isClinicRole,
  roleLanding,
  vaoDuocMan,
} from "../lib/roles.ts";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("ACCOUNTANT có trong danh sách vai, nhãn 'Kế toán', landing /ke-toan", () => {
  assert.ok(ALL_ROLES.includes("ACCOUNTANT"));
  assert.ok(isClinicRole("ACCOUNTANT"));
  assert.equal(ROLE_LABEL.ACCOUNTANT, "Kế toán");
  assert.equal(roleLanding("ACCOUNTANT"), "/ke-toan");
  // Mã gần giống vẫn là rác — không vai lạ nào lọt qua kiểu enum đóng.
  for (const rac of ["accountant", "KE_TOAN", "ACCOUNTANTS", "", undefined, null]) {
    assert.equal(isClinicRole(rac as string | undefined | null), false, String(rac));
  }
});

test("ô Vai ở Thêm nhân viên có 'Kế toán'; backend enum + nhãn khớp", () => {
  assert.match(
    doc("../app/(dashboard)/nhan-su/NhanSuBoard.tsx"),
    /\{ value: "ACCOUNTANT", label: "Kế toán" \}/,
  );
  assert.match(doc("../../clinicai/schemas/staff.py"), /ACCOUNTANT = "ACCOUNTANT"/);
  assert.match(doc("../../clinicai/api/identity.py"), /ACCOUNTANT = "ACCOUNTANT"/);
  assert.match(doc("../../clinicai/services/nhan_vai.py"), /"ACCOUNTANT": \("Kế toán"/);
});

test("vai KHÔNG tự mở màn nào: có quyền thì lego quyết, thiếu quyền là đóng", () => {
  // Máy chủ đã trả lời quyền: chỉ lego quyết, bất kể vai.
  const khongLego: string[] = [];
  const coLego = ["accounting.finance.full", "report.view"];
  assert.equal(vaoDuocMan("/ke-toan", ["ACCOUNTANT"], khongLego), false);
  assert.equal(vaoDuocMan("/reports", ["ACCOUNTANT"], khongLego), false);
  assert.equal(vaoDuocMan("/xuat-hoa-don", ["ACCOUNTANT"], khongLego), false);
  assert.equal(hienTrenThanhBen("ACCOUNTANT", "/ke-toan", khongLego), false);
  assert.equal(vaoDuocMan("/ke-toan", ["ACCOUNTANT"], coLego), true);
  assert.equal(vaoDuocMan("/hoa-don", ["ACCOUNTANT"], coLego), true);
  assert.equal(hienTrenThanhBen("ACCOUNTANT", "/ke-toan", coLego), true);
  // Màn nhạy cảm khác: có vai cũng không vào.
  for (const href of [
    "/settings",
    "/phan-quyen",
    "/nhan-su",
    "/thu-ngan/dich-vu",
    "/thu-ngan/thuoc",
    "/ban-kham",
    "/phong",
    "/pharmacy",
    "/truong-ca",
    "/doi-tac",
  ]) {
    assert.equal(vaoDuocMan(href, ["ACCOUNTANT"], khongLego), false, href);
    assert.equal(canSeeNavGoc("ACCOUNTANT", href), false, href);
  }
});

test("luật gốc (máy chủ im): chỉ thêm ba màn tài chính, các màn nội bộ chung vẫn vào", () => {
  for (const href of ["/reports", "/hoa-don", "/xuat-hoa-don"]) {
    assert.equal(canSeeNavGoc("ACCOUNTANT", href), true, href);
    assert.equal(canSeeNavGoc("CSKH", href), false, href); // vai khác không đổi
  }
  for (const href of ["/home", "/hanh-trinh", "/schedule", "/xac-nhan-ket-qua"]) {
    assert.equal(canSeeNavGoc("ACCOUNTANT", href), true, href);
  }
});
