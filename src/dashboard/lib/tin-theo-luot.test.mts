// Tin SSE mang id lượt (`v`) — người nghe theo MỘT lượt bỏ tin của lượt khác (16/11/2026).
//
// Đo prod 13–16/11: tin chỉ có tên bảng nên phiếu khách B hỏi lại mỗi khi lượt
// khách A đổi — một lượt ghi kéo theo ~15 GET, đỉnh 443 lượt/phút/người. Bất biến
// canh ở đây: KHÔNG BAO GIỜ bỏ sót — tin không rõ bảng, hoặc không có `v`, thì
// vẫn hỏi lại như trước.
import assert from "node:assert/strict";
import test from "node:test";

import { canHoiLai, docTin, TIN_KHONG_RO } from "./tin-theo-luot.ts";

const BANG = new Set(["service_order", "visit"]);

test("đọc tin có id lượt", () => {
  assert.deepEqual(docTin('{"t":"visit","c":"x","v":"L1"}'), { t: "visit", v: "L1" });
});

test("tin cũ (không v) vẫn đọc được", () => {
  assert.deepEqual(docTin('{"t":"visit","c":"x"}'), { t: "visit", v: null });
});

test("tin méo hoặc t rỗng → không rõ (thà thừa một lượt)", () => {
  assert.deepEqual(docTin("{méo"), TIN_KHONG_RO);
  assert.deepEqual(docTin('{"t":null,"c":"x"}'), TIN_KHONG_RO);
  assert.deepEqual(docTin('{"c":"x"}'), TIN_KHONG_RO);
});

test("không truyền lượt: hành vi y như cũ — chỉ lọc theo bảng", () => {
  assert.equal(canHoiLai({ t: "visit", v: "L2" }, BANG), true);
  assert.equal(canHoiLai({ t: "payment", v: "L2" }, BANG), false);
});

test("đang mở lượt L1: bỏ tin lượt L2, nhận tin lượt L1", () => {
  assert.equal(canHoiLai({ t: "service_order", v: "L2" }, BANG, "L1"), false);
  assert.equal(canHoiLai({ t: "service_order", v: "L1" }, BANG, "L1"), true);
});

test("tin không có v (bảng không có cột lượt) → vẫn hỏi lại", () => {
  assert.equal(canHoiLai({ t: "service_order", v: null }, BANG, "L1"), true);
});

test("tin không rõ → mọi người nghe hỏi lại, kể cả đang lọc theo lượt", () => {
  assert.equal(canHoiLai(TIN_KHONG_RO, BANG, "L1"), true);
  assert.equal(canHoiLai(null, BANG, "L1"), true);
});

test("lượt rỗng (chưa chọn khách) → không lọc theo lượt", () => {
  assert.equal(canHoiLai({ t: "visit", v: "L2" }, BANG, null), true);
  assert.equal(canHoiLai({ t: "visit", v: "L2" }, BANG, ""), true);
});
