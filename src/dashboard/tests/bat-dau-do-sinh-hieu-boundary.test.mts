// Màn Đo sinh hiệu: [Bắt đầu] thay cho [Gọi vào đo] (Tuyền chốt 23/09/2026);
// 24/09/2026: bỏ luôn nút [Bắt đầu] — gõ đầu tiên là bắt đầu, [Đo xong] là lưu.
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

test("không còn nút [Bắt đầu]: gõ đầu tiên là bắt đầu, [Đo xong] không khoá", () => {
  // Tuyền 24/09/2026: "không cần ấn bắt đầu đo nữa, cứ nhập thông tin vào sẽ
  // phát sinh event từ lúc nhập vào đầu tiên và đo xong lúc ấn đo xong". Máy
  // chủ vẫn là cửa chặn (VITALS_NOT_STARTED) — màn tự gửi lệnh bắt đầu.
  const ma = chiMa(MAN);
  assert.doesNotMatch(ma, /"Bắt đầu"|Bấm \[Bắt đầu\]/, "không còn nút / lời nhắc Bắt đầu");
  assert.match(ma, /sinh_hieu_trang_thai === "pending"/);
  // Gõ vào ô → tự gửi bắt đầu (một lần / lượt).
  assert.match(ma, /onChange=\{\(e\) => \{[\s\S]*?void batDau\(\);/);
  // Bấm Đo xong khi chưa có mốc bắt đầu → gửi bắt đầu TRƯỚC khi lưu.
  assert.match(ma, /if \(chuaBd[\s\S]*?await batDau\(\)/);
  assert.match(ma, /"Đo xong"/);
  assert.match(ma, /disabled=\{dangLuu\}/, "nút Đo xong không khoá theo mốc bắt đầu");
  // Ô nhập SINH HIỆU không có `disabled` nào. (Ô tick "Bỏ qua bác sĩ tư vấn",
  // 25/09, khoá có chủ ý khi tư vấn đã nhận / bác sĩ chính đã khám — không
  // phải ô nhập chỉ số, nên loại ra.)
  const oNhap = (ma.match(/<input[\s\S]*?\/>/g) ?? []).filter(
    (o) => !o.includes('type="checkbox"'),
  );
  assert.ok(oNhap.length > 0);
  for (const o of oNhap) assert.doesNotMatch(o, /disabled/);
});

test("đường bắt đầu đo đi qua danh sách trắng của proxy", () => {
  assert.match(
    PROXY,
    /"bat-dau-do": \(id\) => `\/api\/v1\/luot-kham\/visits\/\$\{id\}\/vitals\/start`/,
  );
});
