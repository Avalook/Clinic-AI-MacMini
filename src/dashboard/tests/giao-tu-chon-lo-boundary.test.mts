import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Giao thuốc tự chọn lô (27/10/2026): máy chủ chọn lô hết hạn sớm nhất và trừ kho;
// màn chỉ bấm "Giao thuốc" và NÓI LẠI câu máy chủ trả (`tom_tat`), không tự suy lô.

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const dongThuoc = doc("app/(dashboard)/pharmacy/DongThuoc.tsx");

test("giao không chỉ định lô: màn hiện câu máy chủ trả, không tự tính lô", () => {
  assert.match(dongThuoc, /tom_tat\?: string \| null/);
  assert.match(dongThuoc, /setTin\(ketQua\?\.tom_tat \?\? null\)/);
  assert.match(dongThuoc, /\{tin && dong\.dispensed_qty > 0 \? <p role="status" className="text-body text-ink">\{tin\}<\/p> : null\}/);
  // Thẻ dựng lại theo key sau khi giao: câu báo phải do cha giữ, không thì mất ngay.
  assert.match(dongThuoc, /useState<string \| null>\(tinDau\)/);
});

test("câu 'chờ gán lô' là việc thường: trung tính, không tô đỏ/vàng", () => {
  const khoi = dongThuoc.slice(dongThuoc.indexOf("{tin &&"), dongThuoc.indexOf("{loi ?"));
  assert.doesNotMatch(khoi, /danger|warning|amber|yellow/);
});

test("chữ hướng dẫn nút Giao không còn bảo 'gán lô sau' mặc định", () => {
  assert.match(dongThuoc, /Máy tự chọn lô hết hạn sớm nhất và trừ kho ngay\./);
  assert.doesNotMatch(dongThuoc, /Chưa cần lô — gán lô sau ở Kho thuốc\./);
});

test("lô vừa quét vẫn giao thẳng từ lô đó (không để máy chọn đè)", () => {
  assert.match(
    dongThuoc,
    /\.\.\.\(loGiaoQuet \? \{ drug_batch_id: loGiaoQuet\.drug_batch_id \} : \{\}\)/,
  );
});
