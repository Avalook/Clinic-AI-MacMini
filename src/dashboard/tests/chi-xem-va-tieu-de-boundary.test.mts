// Hai lỗi giao diện bắt được khi bấm thật 18/09/2026 (tài khoản thư ký).
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("ô bị khoá phải TRÔNG khoá — khai một lần trong INPUT dùng chung", () => {
  // Bệnh án chỉ xem ở Trang chủ: 24/24 ô khoá nhưng trắng y ô gõ được.
  const formUi = read("../app/(dashboard)/form-ui.ts");
  assert.match(formUi, /disabled:bg-surface-sunken/);
  assert.match(formUi, /disabled:cursor-not-allowed/);
});

test("phiếu mở từ Trang chủ nói thẳng là chỉ xem và sửa ở đâu", () => {
  const f = read("../app/(dashboard)/tasks/ClinicalRecordForm.tsx");
  assert.match(f, /\{readOnly && vitalsOnly && \(/);
  assert.match(f, /Chỉ xem — sửa bệnh án ở Bàn khám/);
});

test("trang không có tiêu đề riêng lấy đúng tên nút ở thanh bên", () => {
  // Rà 18/09: 32/46 mục thanh bên hiện "Hệ thống Quản lý ClinicAI".
  const h = read("../app/(dashboard)/GlobalHeader.tsx");
  assert.match(h, /import \{ NAV, navLabelFor \} from "\.\/nav-items"/);
  assert.match(h, /title: navLabelFor\(muc, role\)/);
});
