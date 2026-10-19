import assert from "node:assert/strict";
import test from "node:test";

import {
  calculatePurchaseTotal,
  parseNonNegativeAmount,
  parsePositiveQuantity as parseInventoryQuantity,
} from "../lib/validation.ts";
import {
  calculateCashierTotal,
  parsePositiveQuantity,
} from "../lib/cashier-total.ts";

test("medicine totals multiply unit price by an explicit quantity", () => {
  assert.deepEqual(
    calculateCashierTotal("thuoc", [], [
      { price: 12_000, quantity: "10" },
      { price: 5_000, quantity: "2" },
    ]),
    { sum: 130_000, missing: false },
  );
});

test("a missing price or ambiguous medicine quantity blocks collection", () => {
  assert.deepEqual(
    calculateCashierTotal("dich_vu", [{ price: 100_000 }, { price: null }], []),
    { sum: 100_000, missing: true },
  );
  assert.deepEqual(
    calculateCashierTotal("thuoc", [], [{ price: 10_000, quantity: "2 viên" }]),
    { sum: 0, missing: true },
  );
  assert.deepEqual(
    calculateCashierTotal("thuoc", [], [{ price: 10_000, quantity: null }]),
    { sum: 0, missing: true },
  );
});

test("quantity parsing is finite, positive and locale-friendly", () => {
  assert.equal(parsePositiveQuantity("1"), 1);
  assert.equal(parsePositiveQuantity("1,5"), 1.5);
  for (const value of [null, "", "0", "-1", "2 viên", "Infinity", "NaN"]) {
    assert.equal(parsePositiveQuantity(value), null);
  }
});

test("purchase totals reject non-finite or negative inputs instead of producing NaN", () => {
  assert.equal(parseInventoryQuantity("1"), 1);
  assert.equal(parseInventoryQuantity("-1"), null);
  assert.equal(parseInventoryQuantity("Infinity"), null);
  assert.equal(parseNonNegativeAmount("12,5"), 12.5);
  assert.equal(parseNonNegativeAmount("-1"), null);
  assert.equal(parseNonNegativeAmount("Infinity"), null);
  assert.equal(calculatePurchaseTotal([{ quantity: "", price: "" }]), 0);
  assert.equal(calculatePurchaseTotal([{ quantity: "1,5", price: "2" }]), 3);
  assert.equal(calculatePurchaseTotal([{ quantity: "Infinity", price: "" }]), null);
  assert.equal(calculatePurchaseTotal([{ quantity: "1", price: "Infinity" }]), null);
  assert.equal(calculatePurchaseTotal([{ quantity: "1e308", price: "1e308" }]), null);
});
