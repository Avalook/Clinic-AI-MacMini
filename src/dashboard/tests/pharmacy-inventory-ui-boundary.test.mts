import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const source = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

test("inventory status cards summarize fetched batches and drive the active expiry filter", () => {
  const inventory = source("../app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");

  assert.ok(inventory.includes("const FILTER_CARDS ="));
  assert.ok(inventory.includes("all: batches.length"));
  assert.ok(inventory.includes('b.trang_thai_han === "con_han"'));
  assert.ok(inventory.includes('b.trang_thai_han === "sap_het_han"'));
  assert.ok(inventory.includes('b.trang_thai_han === "het_han"'));
  assert.ok(inventory.includes("FILTER_CARDS.map((card) =>"));
  assert.ok(inventory.includes("const dangChon = filter === card.value;"));
  assert.ok(inventory.includes("aria-pressed={dangChon}"));
  assert.ok(inventory.includes("onClick={() => setFilter(card.value)}"));
  assert.ok(inventory.includes("statusCounts[card.value]"));
});

test("inventory lots switch to readable cards on mobile and retain the desktop table", () => {
  const inventory = source("../app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");

  assert.ok(inventory.includes('<ul aria-label="Danh sách lô thuốc"'));
  assert.ok(inventory.includes('className="space-y-2 md:hidden"'));
  assert.ok(inventory.includes('className={`${TBL_WRAP} hidden overflow-x-auto md:block`}'));
  for (const field of ["Mã lô", "Hạn dùng", "Tồn", "Giá nhập"]) {
    assert.ok(inventory.includes(field));
  }
  assert.ok(inventory.includes("guiKho(lo.loai"));
  assert.ok(inventory.includes("router.refresh()"));
});

test("filtered empty inventory can clear the current search and expiry filter", () => {
  const inventory = source("../app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");

  assert.ok(inventory.includes('aria-label="Xoá bộ lọc"'));
  assert.ok(inventory.includes("setSearch(\"\")"));
  assert.ok(inventory.includes('setFilter("all")'));
  assert.ok(inventory.includes("Không có lô thuốc phù hợp với bộ lọc."));
});
