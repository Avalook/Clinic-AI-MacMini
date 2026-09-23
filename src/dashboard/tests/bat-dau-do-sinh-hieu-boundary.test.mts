// Màn Đo sinh hiệu: [Bắt đầu] thay cho [Gọi vào đo] (Tuyền chốt 23/09/2026).
//
// Ba bất biến dưới đây canh đúng ba cách làm sai dễ gặp nhất khi gỡ một nút:
// gỡ nút mà vẫn đọc cột cũ làm trạng thái, gọi nhầm đường cũ, và biến mốc đo
// thời gian thành cửa khoá.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const MAN = readFileSync(
  new URL("../app/(dashboard)/do-sinh-hieu/BangDoSinhHieu.tsx", import.meta.url),
  "utf8",
);
const PROXY = readFileSync(
  new URL("../app/api/luot-kham/route.ts", import.meta.url),
  "utf8",
);

/** Bỏ chú thích: nhắc tên cột cũ trong lời giải thích là tốt, DÙNG nó thì sai. */
const chiMa = (nguon: string) =>
  nguon.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

test("màn gọi [Bắt đầu], không còn gọi đường [Gọi vào đo]", () => {
  const ma = chiMa(MAN);
  assert.match(ma, /thao_tac: "bat-dau-do"/);
  assert.doesNotMatch(ma, /thao_tac: "goi-do"/);
  assert.doesNotMatch(ma, /Gọi vào đo|Gọi lại/);
});

test('"Đang đo" đọc từ trạng thái thật, không suy từ giờ gọi', () => {
  // Bản trước lấy `goi_do_luc` làm "đang đo": "đã gọi" bị đọc thành "đã bắt
  // đầu đo". Cột ấy giờ chỉ còn là dữ liệu cũ.
  const ma = chiMa(MAN);
  assert.doesNotMatch(ma, /goi_do_luc|goi_do_boi/);
  assert.match(ma, /sinh_hieu_trang_thai === "in_progress"/);
});

test("[Bắt đầu] là mốc đo thời gian, KHÔNG phải cửa khoá ô nhập", () => {
  // Ô nhập và nút Lưu không được phụ thuộc vào việc đã bấm Bắt đầu hay chưa.
  const ma = chiMa(MAN);
  assert.doesNotMatch(
    ma,
    /disabled=\{[^}]*sinh_hieu_trang_thai[^}]*\}/,
    "không khoá gì theo trạng thái bắt đầu",
  );
});

test("đường bắt đầu đo đi qua danh sách trắng của proxy", () => {
  assert.match(
    PROXY,
    /"bat-dau-do": \(id\) => `\/api\/v1\/luot-kham\/visits\/\$\{id\}\/vitals\/start`/,
  );
});
