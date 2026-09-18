// HÀNG ĐỢI TIẾP NHẬN — MỘT HÀNG CHUNG, KÉO NGAY TRONG DANH SÁCH.
//
// Tuyền 16/09/2026: *"hàng chung cho cả phòng khám khi vào check-in"*, và
// *"trước số thứ tự có cái gạch ngang nhỏ để lễ tân click vào và di chuyển lên
// xuống được"*. Trước đó màn này có HAI bảng cùng kể một hàng đợi: "Thứ tự khám
// hôm nay" (chia theo bác sĩ, kéo được) và "Danh sách hàng đợi" (phẳng, không
// kéo được, gồm cả người chưa tới). Hai bảng cạnh nhau là hai bảng sẽ lệch.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { choTruoc } from "../app/(dashboard)/reception/queue/thu-tu-chen.ts";

const board = readFileSync(
  new URL("../app/(dashboard)/reception/queue/QueueBoard.tsx", import.meta.url),
  "utf8",
);
const ma = board.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");

test("chèn một khách vào giữa hai người — luật thuần, không chạm mạng", () => {
  const hang = ["a", "b", "c", "d"];
  // Kéo d lên trước b ⇒ đứng sau a, trước b.
  assert.deepEqual(choTruoc(hang, "d", "b"), { sau: "a", truoc: "b" });
  // Kéo a lên đầu (thả trước chính người đầu còn lại).
  assert.deepEqual(choTruoc(hang, "c", "a"), { sau: null, truoc: "a" });
  // Thả xuống cuối: đứng sau người cuối cùng còn lại.
  assert.deepEqual(choTruoc(hang, "a", null), { sau: "d", truoc: null });
  // Đích không còn trong hàng (vừa được gọi vào khám) ⇒ không ghi gì.
  assert.equal(choTruoc(hang, "a", "z"), null);
});

test("hàng đợi chỉ gồm người ĐÃ check-in, xếp theo thứ tự của backend", () => {
  assert.match(
    ma,
    /if \(!item\.checked_in_at\) return false;/,
    "người chưa tới không thuộc hàng đợi — họ ở bảng Lịch hẹn khám",
  );
  // Thứ tự lấy từ `call_order` của backend, KHÔNG tự xếp theo chờ lâu/mã số.
  assert.match(ma, /thuTu\.get\(x\.appointment_id\)/);
  assert.doesNotMatch(ma, /sort === "wait"/);
  assert.doesNotMatch(ma, /SortMode/);
});

test("ba ô lọc cũ đã bỏ, và không còn mã bước viết cứng trong giao diện", () => {
  for (const bo of ["Khách ưu tiên", "Cần xác minh", "Sắp xếp: chờ lâu", "LUOTKHAM-02"]) {
    assert.doesNotMatch(ma, new RegExp(bo), `"${bo}" đáng lẽ đã bỏ khỏi màn này`);
  }
  const page = readFileSync(
    new URL("../app/(dashboard)/reception/queue/page.tsx", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(page, /LUOTKHAM-02/);
  assert.doesNotMatch(page, /ThuTuKham/, "bảng thứ tự riêng đã gộp vào danh sách");
});

test('"Vào khám" gửi ĐỦ hai lệnh, và lệnh sau dùng version mới', () => {
  // Bỏ lệnh `complete` là bước tiếp nhận không bao giờ đóng ⇒ khách kẹt ở quầy.
  assert.match(ma, /issue\("start", v\)/);
  assert.match(ma, /issue\("complete", v\)/);
  assert.match(
    ma,
    /body\?\.version === "number" \? body\.version/,
    "lệnh thứ hai phải dùng version kernel vừa trả, gửi lại số cũ là 409",
  );
  assert.doesNotMatch(ma, /Xong tiếp nhận/);
});
