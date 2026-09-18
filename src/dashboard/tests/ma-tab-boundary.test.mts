// Hai tab cùng nhập khách mới KHÔNG được đè bản nháp của nhau.
//
// Bẫy đã có thật trong mã: khoá nháp của form khách mới là chữ "form" cố định,
// nên hai tab cùng khoá. Lễ tân quầy mở hai tab (một người đang gọi điện, một
// người đứng trước mặt) thì tab gõ sau ghi đè tab gõ trước — và người kia F5
// một cái là nhận về thông tin của khách KHÔNG PHẢI của mình. Dữ liệu sai còn
// tệ hơn dữ liệu mất.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const GOC = new URL("..", import.meta.url).pathname;
const doc = (p: string) => readFileSync(GOC + p, "utf8");

test("khoá nháp khách mới phải theo TAB, không phải chuỗi cố định", () => {
  const ma = doc("app/(dashboard)/patients/new/NewPatientForm.tsx");
  assert.ok(
    !/khoaNhap\(staffId,\s*"khach-moi",\s*"form"\)/.test(ma),
    'khoá nháp quay về chuỗi cố định "form" — hai tab sẽ đè nhau lần nữa',
  );
  assert.match(
    ma,
    /khoaNhap\(staffId,\s*"khach-moi",\s*maTab\(\)/,
    "khoá nháp khách mới phải lấy mã tab từ lib/ma-tab",
  );
});

test("mã tab lấy từ sessionStorage — kho DUY NHẤT riêng từng tab", () => {
  const ma = doc("lib/ma-tab.ts");
  assert.match(ma, /sessionStorage/, "phải dùng sessionStorage");
  // Bỏ chú thích trước khi soi: file này GIẢI THÍCH vì sao không dùng
  // localStorage, nên tìm chữ ấy trong văn xuôi sẽ báo oan.
  const chiMa = ma.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
  assert.ok(
    !/localStorage\s*[.[]/.test(chiMa),
    "localStorage dùng chung mọi tab — dùng nó ở đây là hỏng đúng thứ đang chữa",
  );
  // Chạy trên máy chủ (SSR) không có tab nào: phải trả rỗng chứ không được ném.
  assert.match(ma, /typeof window === "undefined"/);
  // Trình duyệt chặn kho hoặc HTTP thường (không có crypto.randomUUID) vẫn phải
  // chạy được — staging/prod đang là HTTP thường.
  assert.match(ma, /catch/);
  assert.match(ma, /randomUUID === "function"/);
});
