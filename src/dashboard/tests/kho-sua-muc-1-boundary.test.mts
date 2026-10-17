import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

// (Mảng từ vm khác realm nên so bằng JSON.)
// Sửa mức 1 sau buổi mổ xẻ kho thuốc / vật tư (17/10/2026): ô "Tổng tồn" không
// cộng lẫn hộp với viên; lỗi bán lẻ hiện cạnh nút bấm.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");

type Lo = { unit: string | null; quantity_on_hand: number | string };
type TonDonVi = { don_vi: string; ton: number };

function napGuiKho(): {
  tongTonTheoDonVi: (lo: Lo[]) => TonDonVi[];
  tonTheoDonVi: (ds: TonDonVi[]) => string;
} {
  const exports: Record<string, unknown> = {};
  const code = ts.transpileModule(doc("app/(dashboard)/pharmacy/inventory/gui-kho.ts"), {
    // ES2020: mặc định ES5 biến `[...map.values()]` thành mảng rỗng.
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  runInNewContext(code, { exports, Intl, fetch: () => new Promise(() => {}), URLSearchParams });
  return exports as ReturnType<typeof napGuiKho>;
}

test("tổng tồn tách theo đơn vị: hộp, viên, gói không cộng lẫn", () => {
  const { tongTonTheoDonVi, tonTheoDonVi } = napGuiKho();
  const ds = tongTonTheoDonVi([
    { unit: "viên", quantity_on_hand: "300" },
    { unit: "viên", quantity_on_hand: 28 },
    { unit: "hộp", quantity_on_hand: "20.000" },
    { unit: "gói", quantity_on_hand: 6 },
  ]);
  assert.equal(
    JSON.stringify(ds.map((d) => [d.don_vi, d.ton])),
    JSON.stringify([
      ["gói", 6],
      ["hộp", 20],
      ["viên", 328],
    ]),
  );
  assert.equal(tonTheoDonVi(ds), "6 gói · 20 hộp · 328 viên");
});

test("tổng tồn: gộp viết hoa / khoảng trắng khác nhau, bỏ đơn vị tồn 0, rác thành 0", () => {
  const { tongTonTheoDonVi } = napGuiKho();
  const ds = tongTonTheoDonVi([
    { unit: "Viên ", quantity_on_hand: 5 },
    { unit: "viên", quantity_on_hand: 5 },
    { unit: "hộp", quantity_on_hand: 0 },
    { unit: "vỉ", quantity_on_hand: "abc" },
    { unit: null, quantity_on_hand: 2 },
  ]);
  assert.equal(
    JSON.stringify(ds.map((d) => [d.don_vi.toLowerCase(), d.ton])),
    JSON.stringify([
      ["", 2],
      ["viên", 10],
    ]),
  );
  assert.equal(tongTonTheoDonVi([]).length, 0);
});

test("màn kho thuốc không còn cộng mọi lô thành một con số", () => {
  const board = doc("app/(dashboard)/pharmacy/inventory/InventoryBoard.tsx");
  assert.ok(!board.includes("totalUnits"), "còn biến cộng lẫn đơn vị");
  assert.ok(board.includes("tongTonTheoDonVi(batches)"));
  assert.ok(board.includes("Tổng tồn (theo từng đơn vị)"));
});

test("lỗi thêm mặt hàng ở quầy bán hiện ngay trên nút bấm, có cuộn tới", () => {
  const src = doc("app/(dashboard)/thu-ngan/ChinhDonQuay.tsx");
  const loi = src.indexOf("loiTaiCho ? (");
  const nut = src.indexOf("mặt hàng vào đơn bán");
  assert.ok(loi > 0 && nut > 0 && loi < nut, "lỗi phải nằm TRƯỚC nút trong cùng khối");
  assert.ok(src.includes("scrollIntoView"), "lỗi nằm ngoài màn hình thì phải cuộn tới");
  assert.ok(src.includes("setLoiTaiCho(loi)"), "mọi thao tác dòng đơn đều ghi lỗi tại chỗ");
});
