import assert from "node:assert/strict";
import test from "node:test";

import { khungDaQua, khungDaQuaTheoPhut, khungDaQuaVn } from "./khung-da-qua.ts";

const luc = (hhmm: string, giay = 0) =>
  new Date(`2026-10-09T${hhmm}:${String(giay).padStart(2, "0")}+07:00`).getTime();

test("khung đang chạy CHƯA qua — ca của phòng khám: 17:15–17:30 lúc 17:25", () => {
  assert.equal(khungDaQua(luc("17:15"), 15, luc("17:25")), false);
  assert.equal(khungDaQuaVn("2026-10-09", "17:15", 15, luc("17:25")), false);
  assert.equal(khungDaQuaTheoPhut(17 * 60 + 15, 15, 17 * 60 + 25), false);
});

test("biên đúng phút: kết thúc = bây giờ là đã qua (như slot_end <= now)", () => {
  assert.equal(khungDaQua(luc("17:15"), 15, luc("17:29", 59)), false);
  assert.equal(khungDaQua(luc("17:15"), 15, luc("17:30")), true);
  assert.equal(khungDaQua(luc("17:15"), 15, luc("17:30", 1)), true);
  assert.equal(khungDaQuaTheoPhut(17 * 60 + 15, 15, 17 * 60 + 30), true);
  assert.equal(khungDaQuaTheoPhut(17 * 60 + 15, 15, 17 * 60 + 29), false);
  // Khung tương lai.
  assert.equal(khungDaQua(luc("18:00"), 15, luc("17:25")), false);
});

test("đầu vào: ISO, Date, số ms đều hiểu", () => {
  assert.equal(khungDaQua("2026-10-09T10:15:00.000Z", 15, luc("17:25")), false); // 17:15 VN
  assert.equal(khungDaQua(new Date(luc("17:00")), 15, luc("17:25")), true);
});

test("rác không ném: không biết giờ → chưa qua; không biết độ dài → so giờ bắt đầu", () => {
  for (const x of [null, undefined, "", "rác", Number.NaN, Infinity, {}, new Date("x")]) {
    assert.equal(khungDaQua(x, 15, luc("17:25")), false);
    assert.equal(khungDaQua(luc("17:15"), 15, x), false);
  }
  // Độ dài khung rác / âm / 0 → 0 phút: khung bắt đầu trước bây giờ là đã qua.
  for (const n of [null, "15", -5, 0, Number.NaN]) {
    assert.equal(khungDaQua(luc("17:15"), n, luc("17:25")), true);
    assert.equal(khungDaQua(luc("17:30"), n, luc("17:25")), false);
  }
  assert.equal(khungDaQuaTheoPhut("x", 15, 600), false);
  assert.equal(khungDaQuaTheoPhut(600, 15, null), false);
});

test("ô Ngày + Giờ rác không ném", () => {
  assert.equal(khungDaQuaVn("", "17:15", 15, luc("17:25")), false);
  assert.equal(khungDaQuaVn("2026-10-09", "", 15, luc("17:25")), false);
  assert.equal(khungDaQuaVn("2026-13-40", "17:15", 15, luc("17:25")), false);
  assert.equal(khungDaQuaVn("2026-10-09", "25:99", 15, luc("17:25")), false);
  assert.equal(khungDaQuaVn(null, undefined, 15, luc("17:25")), false);
  assert.equal(khungDaQuaVn("2026-10-08", "17:15", 15, luc("17:25")), true); // hôm qua
});
