// Màn Đo sinh hiệu: [Bắt đầu] thay cho [Gọi vào đo] (Tuyền chốt 23/09/2026).
//
// Các bất biến dưới đây canh những cách làm sai dễ gặp nhất khi gỡ một nút:
// gỡ nút mà vẫn đọc cột cũ làm trạng thái, gọi nhầm đường cũ, và để lưu lần
// đầu khi chưa bấm [Bắt đầu] (chốt 23/09/2026).

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

test("chưa [Bắt đầu] thì khoá nút Lưu và nói lý do — nhưng KHÔNG khoá ô nhập", () => {
  // Chốt 23/09/2026: lần lưu đầu phải sau [Bắt đầu]. Máy chủ là cửa chặn thật
  // (VITALS_NOT_STARTED); màn chỉ đỡ cho người dùng khỏi ăn lỗi.
  const ma = chiMa(MAN);
  assert.match(ma, /sinh_hieu_trang_thai === "pending"/);
  assert.match(ma, /disabled=\{dangLuu \|\| chuaBatDau\}/, "nút Lưu khoá khi chưa bắt đầu");
  assert.match(ma, /Bấm \[Bắt đầu\] trước khi lưu\./, "phải nói rõ vì sao không lưu được");
  // Ô nhập không có `disabled` nào: gõ chưa phải lưu.
  const oNhap = ma.match(/<input[\s\S]*?\/>/g) ?? [];
  assert.ok(oNhap.length > 0);
  for (const o of oNhap) assert.doesNotMatch(o, /disabled/);
});

test("đường bắt đầu đo đi qua danh sách trắng của proxy", () => {
  assert.match(
    PROXY,
    /"bat-dau-do": \(id\) => `\/api\/v1\/luot-kham\/visits\/\$\{id\}\/vitals\/start`/,
  );
});
