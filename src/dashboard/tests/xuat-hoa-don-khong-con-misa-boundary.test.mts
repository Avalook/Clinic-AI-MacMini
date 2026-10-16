import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const co = (p: string) => existsSync(new URL(p, import.meta.url));

// Tuyền 16/10/2026: nút "Đánh dấu đã xuất MISA" thừa, gỡ khỏi màn Xuất hoá đơn.
// Phần máy chủ (bảng, API misa-xuat) còn nguyên, chưa ai gọi — gỡ hẳn ở lượt sau nếu cần.
test("màn Xuất hoá đơn không còn nút / khối / nhãn MISA", () => {
  const ui = read("../app/(dashboard)/xuat-hoa-don/XuatHoaDon.tsx");
  assert.doesNotMatch(ui, /Đánh dấu đã xuất MISA|Đã xuất MISA|LanXuatMisa|TrangThaiMisa/);
  assert.doesNotMatch(ui, /\/api\/xuat-hoa-don\/misa/);
  // Vẫn tải được file Excel đúng mẫu.
  assert.match(ui, /xuat=xlsx/);
});

test("file giao diện và route chuyển tiếp của MISA đã gỡ", () => {
  assert.equal(co("../app/(dashboard)/xuat-hoa-don/LanXuatMisa.tsx"), false);
  assert.equal(co("../app/api/xuat-hoa-don/misa/route.ts"), false);
  assert.equal(co("../app/api/xuat-hoa-don/misa/[id]/route.ts"), false);
});
