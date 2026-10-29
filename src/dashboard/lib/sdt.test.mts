import assert from "node:assert/strict";
import test from "node:test";
import { cheSdt, dinhDangSdt, soSdtKhop } from "./sdt.ts";

test("định dạng số VN, số quốc tế; giữ nguyên dữ liệu cũ sai dạng", () => {
  for (const [raw, formatted, masked] of [
    ["0912345678", "0912 345 678", "0912 ••• 678"],
    ["0281234567", "0281 234 567", "0281 ••• 567"],
    ["0912 345 678", "0912 345 678", "0912 ••• 678"],
    ["+14155552671", "+1 415 555 2671", "+1 415 ••• 2671"],
    ["+821012345678", "+82 101 234 5678", "+82 101 ••• 5678"],
    ["+358401234567", "+358 40 123 4567", "+358 40 ••• 4567"],
    ["0912", "0912", "0912"],
    ["  sai dạng  ", "  sai dạng  ", "  sai dạng  "],
    ["0912 ••• 678", "0912 ••• 678", "0912 ••• 678"],
    ["0334***897", "0334***897", "0334***897"],
  ]) {
    assert.equal(dinhDangSdt(raw), formatted, raw);
    assert.equal(cheSdt(raw), masked, raw);
  }
});

test("dữ liệu rác không ném; số dạng number cũ vẫn đọc được", () => {
  for (const raw of [null, undefined, "", {}, [], false, Symbol("sdt")]) {
    assert.equal(dinhDangSdt(raw), null);
    assert.equal(cheSdt(raw), null);
  }
  assert.equal(dinhDangSdt(1234567890), "1234 567 890");
  for (const raw of ["x".repeat(5000), "０９１２３４５６７８", "0912\u200b345678"]) {
    assert.equal(dinhDangSdt(raw), raw);
    assert.equal(cheSdt(raw), raw);
  }
});

test("tìm tối thiểu 3 chữ số, hiểu dạng VN và tiền tố quốc tế", () => {
  for (const q of ["0912", "912", "345 678", "+84912345678", "84912345678", "0084 912 345 678", "+84 912", "0084 912", "84 912"]) {
    assert.equal(soSdtKhop(q, "0912345678"), true, q);
  }
  for (const q of ["+1 415 555 2671", "0014155552671", "415555"]) {
    assert.equal(soSdtKhop(q, "+14155552671"), true, q);
  }
  for (const q of ["", "09", "1", "abc", "0912 gặp Hoa", null, {}, "1".repeat(5000)]) {
    assert.equal(soSdtKhop(q, "0912345678"), false);
  }
  assert.equal(soSdtKhop("0912", null), false);
  assert.equal(soSdtKhop("999", "0912345678"), false);
});
