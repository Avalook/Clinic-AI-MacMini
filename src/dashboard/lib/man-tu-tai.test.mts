import assert from "node:assert/strict";
import test from "node:test";

import { BANG_LAYOUT, canDungLaiTrang, laManTuTai } from "./man-tu-tai.ts";

const TAT_CA = new Set(["visit", "payment", "appointment", "work_roster", "queue_entry"]);

test("năm màn tự tải được nhận ra, kể cả có id/mã phòng và dấu / cuối", () => {
  for (const p of [
    "/ban-kham",
    "/ban-kham/",
    "/ban-kham/ee1a-uuid",
    "/tu-van",
    "/phong/3f2c-uuid",
    "/hanh-trinh",
    "/thu-ngan/dich-vu",
    "/thu-ngan/thuoc",
    "/thu-ngan/dich-vu/lich-su",
    "/thu-ngan/thuoc/lich-su",
  ]) {
    assert.equal(laManTuTai(p), true, p);
  }
});

test("màn có dữ liệu sống ở server KHÔNG bị liệt vào tự tải", () => {
  for (const p of [
    "/phong", // danh sách phòng vẽ số khách ở server
    "/reception/queue",
    "/reception/checkout",
    "/truong-ca",
    "/home",
    "/appointments",
    "/ban-kham/a/b",
    "/phong/a/b",
    "/thu-ngan",
    "/thu-ngan/khac",
    "",
    null,
    undefined,
  ]) {
    assert.equal(laManTuTai(p), false, String(p));
  }
});

test("màn thường: dựng lại cho bảng của màn và cho tin không rõ bảng", () => {
  assert.equal(canDungLaiTrang("/home", "visit", TAT_CA), true);
  assert.equal(canDungLaiTrang("/home", null, TAT_CA), true);
  assert.equal(canDungLaiTrang("/home", "bang_la", TAT_CA), false);
});

test("màn tự tải: chỉ dựng lại cho bảng của PHẦN LAYOUT, không cho visit/payment/null", () => {
  assert.equal(canDungLaiTrang("/ban-kham", "visit", TAT_CA), false);
  assert.equal(canDungLaiTrang("/ban-kham", "payment", TAT_CA), false);
  assert.equal(canDungLaiTrang("/phong/abc", "queue_entry", TAT_CA), false);
  assert.equal(canDungLaiTrang("/thu-ngan/dich-vu", null, TAT_CA), false);
  for (const b of BANG_LAYOUT) {
    assert.equal(canDungLaiTrang("/ban-kham", b, TAT_CA), true, b);
  }
});

test("màn tự tải vẫn tôn trọng danh sách bảng của prop `tables`", () => {
  const chiVisit = new Set(["visit"]);
  assert.equal(canDungLaiTrang("/ban-kham", "appointment", chiVisit), false);
});
