import assert from "node:assert/strict";
import test from "node:test";

import { canSeeNav } from "../lib/roles.ts";

test("reception is not offered the reconciliation board it cannot safely read", () => {
  assert.equal(canSeeNav("RECEPTION", "/cashier/board"), false);
  assert.equal(canSeeNav("CASHIER", "/cashier/board"), true);
  assert.equal(canSeeNav("TRUONG_CA", "/cashier/board"), true);
});
