import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Thuốc khách trả chờ kiểm (17/10/2026, việc B). Luật nằm ở máy chủ
// (test_xu_ly_thuoc_tra_db.py); ở đây canh màn gắn đúng đường và không tự quyết.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const kho = "app/(dashboard)/pharmacy/inventory";

test("tab nằm ở khu QUẦY và có chấm báo khi còn thuốc chờ kiểm", () => {
  const s = doc(`${kho}/KhoThuoc.tsx`);
  assert.match(s, /TAB_QUAY: readonly Tab\[\] = \[[^\]]*"tra_cho_kiem"/);
  assert.ok(s.includes("Thuốc trả chờ kiểm (${thuocTraChoKiem.length})"));
  assert.ok(s.includes("choGanLo.length > 0 || thuocTraChoKiem.length > 0"));
  assert.ok(s.includes('<ThuocTraChoKiem dong={thuocTraChoKiem} ghiDuoc={ghiDuoc} />'));
});

test("trang đọc danh sách từ máy chủ, đọc hỏng thì tab rỗng", () => {
  const s = doc(`${kho}/page.tsx`);
  assert.ok(s.includes('"/api/v1/pharmacy/thuoc-tra-cho-kiem"'));
  assert.ok(s.includes("traCho?.dong ?? []"));
});

test("hai nút chỉ gửi quyết định + lý do; huỷ bắt lý do; không hộp thoại trình duyệt", () => {
  const s = doc(`${kho}/ThuocTraChoKiem.tsx`);
  assert.ok(s.includes('guiKho("xu-ly-thuoc-tra"'));
  assert.match(s, /drug_return_id: d\.id,\s*quyet_dinh: quyetDinh/);
  assert.ok(s.includes("lyDo.trim().length < 3"), "nút huỷ khoá khi lý do ngắn");
  assert.ok(!s.includes("window.confirm") && !s.includes("confirm("));
  assert.ok(s.includes("Không sửa lại được sau khi xác"), "báo trước là không sửa lại");
  assert.ok(!/\bfetch\(/.test(s), "không tự gọi mạng ngoài guiKho");
});

test("người chỉ xem thì không có nút quyết", () => {
  const s = doc(`${kho}/ThuocTraChoKiem.tsx`);
  assert.ok(s.includes("!ghiDuoc ?"));
  assert.ok(s.includes("Bạn chỉ xem"));
});

test("proxy và kiểu gửi cho phép đúng thao tác xu-ly-thuoc-tra", () => {
  assert.ok(doc("app/api/pharmacy/[action]/route.ts").includes('"xu-ly-thuoc-tra": "/api/v1/pharmacy/xu-ly-thuoc-tra"'));
  assert.ok(doc(`${kho}/gui-kho.ts`).includes('"xu-ly-thuoc-tra"'));
});
