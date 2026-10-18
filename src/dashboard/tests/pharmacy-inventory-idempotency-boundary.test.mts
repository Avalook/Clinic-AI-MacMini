import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { guiKho } from "../app/(dashboard)/pharmacy/inventory/gui-kho.ts";

const guiKhoSource = readFileSync(
  new URL("../app/(dashboard)/pharmacy/inventory/gui-kho.ts", import.meta.url),
  "utf8",
);
const inventoryBoard = readFileSync(
  new URL("../app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx", import.meta.url),
  "utf8",
);
const nhapLo = readFileSync(
  new URL("../app/(dashboard)/pharmacy/inventory/NhapLo.tsx", import.meta.url),
  "utf8",
);

test("điều chỉnh, huỷ và nhập lô giữ khoá theo payload qua lần gửi lại", () => {
  assert.match(guiKhoSource, /receive.*adjust.*discard/s);
  assert.match(guiKhoSource, /sessionStorage/);
  assert.match(guiKhoSource, /Idempotency-Key/);
  assert.match(guiKhoSource, /removeItem/);
  assert.match(inventoryBoard, /guiKho\(lo\.loai/);
  assert.match(nhapLo, /guiKho\("receive"/);
});

test("các request đồng thời cùng payload dùng chung khoá và giữ khoá nếu có request lỗi", async () => {
  const luu = new Map<string, string>();
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      sessionStorage: {
        getItem: (key: string) => luu.get(key) ?? null,
        setItem: (key: string, value: string) => luu.set(key, value),
        removeItem: (key: string) => luu.delete(key),
      },
    },
  });
  const payload = { drug_catalog_id: crypto.randomUUID(), batch_code: "RACE-1", so_luong: 4 };
  const keys: string[] = [];
  let request = 0;
  globalThis.fetch = async (_input, init) => {
    const headers = init?.headers as Record<string, string>;
    keys.push(headers["Idempotency-Key"]);
    request += 1;
    if (request === 2) throw new Error("simulated lost response");
    return Response.json({ ok: true });
  };

  const [a, b] = await Promise.all([
    guiKho("receive", payload),
    guiKho("receive", payload),
  ]);
  assert.equal(a.ok, true);
  assert.equal(b.ok, false);
  assert.equal(keys[0], keys[1]);
  assert.equal(luu.size, 1);

  await guiKho("receive", payload);
  assert.equal(keys[2], keys[0]);
  assert.equal(luu.size, 0);
});

test("không gửi khi sessionStorage bị chặn vì retry sau tải lại sẽ không an toàn", async () => {
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      sessionStorage: {
        getItem: () => {
          throw new Error("storage disabled");
        },
        setItem: () => {
          throw new Error("storage disabled");
        },
        removeItem: () => {
          throw new Error("storage disabled");
        },
      },
    },
  });
  let requests = 0;
  globalThis.fetch = async () => {
    requests += 1;
    return Response.json({ ok: true });
  };

  const result = await guiKho("adjust", {
    drug_batch_id: crypto.randomUUID(),
    so_luong: -1,
  });
  assert.equal(result.ok, false);
  assert.match(result.loi, /chưa được gửi/);
  assert.equal(requests, 0);
});

test("mất response rồi nạp lại module vẫn đọc lại key đã lưu trong sessionStorage", async () => {
  const luu = new Map<string, string>();
  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      sessionStorage: {
        getItem: (key: string) => luu.get(key) ?? null,
        setItem: (key: string, value: string) => luu.set(key, value),
        removeItem: (key: string) => luu.delete(key),
      },
    },
  });
  const payload = {
    drug_batch_id: crypto.randomUUID(),
    so_luong: -2,
  };
  const keys: string[] = [];
  globalThis.fetch = async (_input, init) => {
    keys.push((init?.headers as Record<string, string>)["Idempotency-Key"]);
    throw new Error("simulated lost response");
  };
  const first = await guiKho("adjust", payload);
  assert.equal(first.ok, false);
  assert.equal(luu.size, 1);

  const reloaded = await import("../app/(dashboard)/pharmacy/inventory/gui-kho.ts?reload=1");
  globalThis.fetch = async (_input, init) => {
    keys.push((init?.headers as Record<string, string>)["Idempotency-Key"]);
    return Response.json({ ok: true });
  };
  const second = await reloaded.guiKho("adjust", payload);
  assert.equal(second.ok, true);
  assert.equal(keys[0], keys[1]);
  assert.equal(luu.size, 0);
});
