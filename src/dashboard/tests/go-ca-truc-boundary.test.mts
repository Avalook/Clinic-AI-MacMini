// Gỡ ca trực báo "Lỗi khi gỡ ca." — id tạm bị gửi xuống máy chủ.
//
// Tuyền báo 14/08/2026 kèm ảnh. Log prod nói rõ chuyện gì xảy ra:
//
//   DELETE /roster/shifts/74ba83c4-1e94-4f9d-9c94-fe1c8ae35666   → 200
//   DELETE /roster/shifts/temp-2026-08-22-LICH_KHAM-…-SANG        → 422 (×3)
//
// Ba lần 422 liên tiếp vì không có gì nói cho người bấm biết vì sao.
//
// CƠ CHẾ: xếp ca vẽ trước một dòng mang id tạm `temp-…` cho mượt, rồi gọi
// refresh(). Nhưng popup CỐ Ý ở lại mở (mỗi ô có tới hai người), nên người vừa
// xếp nhìn thấy ngay dòng vừa thêm — và dòng ấy vẫn là dòng tạm. Bấm thùng rác
// trên nó là gửi `temp-…` xuống một đường khai tham số kiểu UUID.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { loiDocDuoc } from "../lib/loi-doc-duoc.ts";

const nguon = readFileSync(
  new URL("../app/(dashboard)/schedule/RosterRegisterTable.tsx", import.meta.url),
  "utf8",
);
const ma = nguon.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");

test("xếp xong thì id tạm được ĐỔI sang id thật của máy chủ", () => {
  // Backend trả `{"ok": true, "id": <uuid>}` — không dùng con số ấy thì dòng
  // trên màn hình vĩnh viễn mang id không gỡ được.
  assert.match(
    ma,
    /than\?\.id|than\.id/,
    "phải đọc id thật từ thân trả về của POST",
  );
  assert.match(
    ma,
    /o\.id === tempId \? \{ \.\.\.o, id: idThat \}/,
    "phải thay id tạm bằng id thật trong danh sách optimistic",
  );
});

test("KHÔNG BAO GIỜ gửi id tạm xuống máy chủ", () => {
  // Chốt cuối, phòng khi vòng mạng đổi id ở trên hỏng. Câu trả lời đúng lúc ấy
  // là "làm mới rồi thử lại", không phải một mã 422 khó hiểu.
  const khoi = /async function remove\([\s\S]*?\n  \}/.exec(ma);
  assert.ok(khoi, "không tìm thấy hàm gỡ ca");
  assert.match(
    khoi![0],
    /startsWith\("temp-"\)/,
    "hàm gỡ ca phải chặn id tạm trước khi gọi mạng",
  );
  const viTriChan = khoi![0].indexOf('startsWith("temp-")');
  const viTriGoi = khoi![0].indexOf("fetch(");
  assert.ok(
    viTriChan < viTriGoi,
    "phải chặn TRƯỚC khi gọi mạng, không phải sau",
  );
});

test("loiDocDuoc lấy được câu thật ra khỏi 422 của FastAPI", () => {
  // `detail` của FastAPI là MẢNG object. Ép kiểu thẳng thì người dùng nhận
  // "[object Object]" — tệ hơn cả câu mặc định.
  assert.equal(
    loiDocDuoc(
      { detail: [{ loc: ["path", "roster_id"], msg: "Input should be a valid UUID" }] },
      "Lỗi khi gỡ ca.",
    ),
    "Input should be a valid UUID",
  );
  assert.equal(
    loiDocDuoc({ detail: [{ msg: "a" }, { msg: "b" }] }, "x"),
    "a; b",
    "nhiều mục thì nối lại",
  );
});

test("loiDocDuoc đọc CÂU trước MÃ", () => {
  assert.equal(
    loiDocDuoc(
      { error: "CONFLICT_ERROR", message: "Khung giờ đã đầy: tối đa 2 chỗ." },
      "Không thể đặt lịch.",
    ),
    "Khung giờ đã đầy: tối đa 2 chỗ.",
  );
  // `error` là mã in hoa toàn phần → thà lấy câu mặc định tiếng Việt.
  assert.equal(
    loiDocDuoc({ error: "CONFLICT_ERROR" }, "Không thể đặt lịch."),
    "Không thể đặt lịch.",
  );
  // Nhưng route Next dùng `error` để chở CÂU — chỗ ấy phải đi qua.
  assert.equal(loiDocDuoc({ error: "Thiếu id." }, "mặc định"), "Thiếu id.");
});

test("thân lỗi rỗng / hỏng thì trả câu mặc định, không nổ", () => {
  for (const x of [null, undefined, {}, "", 0, [], { detail: [] }]) {
    assert.equal(loiDocDuoc(x, "mặc định"), "mặc định");
  }
  assert.equal(loiDocDuoc("máy chủ sập", "mặc định"), "máy chủ sập");
});
