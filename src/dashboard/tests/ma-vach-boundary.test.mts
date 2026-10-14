// Code 128 tự vẽ phải GIẢI MÃ lại ra đúng chuỗi bằng zxing — cùng thư viện camera
// dùng quét thật. Không giải mã được = tem in ra quét không ra.
import assert from "node:assert/strict";
import test from "node:test";

import { BarcodeFormat, BinaryBitmap, DecodeHintType, HybridBinarizer, MultiFormatReader, RGBLuminanceSource } from "@zxing/library";

import { doRongCode128B, thanhVachCode128B } from "../lib/ma-vach.ts";

function giaiMa(chu: string): string {
  const v = thanhVachCode128B(chu);
  assert.ok(v, `không vẽ được ${chu}`);
  const heSo = 3;
  const w = v.rong * heSo;
  const h = 40;
  const sang = new Uint8ClampedArray(w * h).fill(255);
  for (const t of v.thanh) {
    for (let y = 0; y < h; y++) {
      for (let x = t.x * heSo; x < (t.x + t.w) * heSo; x++) sang[y * w + x] = 0;
    }
  }
  const src = new RGBLuminanceSource(sang, w, h);
  const hints = new Map();
  hints.set(DecodeHintType.POSSIBLE_FORMATS, [BarcodeFormat.CODE_128]);
  const r = new MultiFormatReader();
  r.setHints(hints);
  return r.decode(new BinaryBitmap(new HybridBinarizer(src))).getText();
}

test("mọi mẫu Code 128 đủ 11 module (stop 13)", () => {
  for (const chu of ["A", "LT00000012", "LOT-2026/05 x"]) {
    const dr = doRongCode128B(chu);
    assert.ok(dr);
    // start(6) + n ký tự(6) + kiểm(6) + stop(7) phần tử; tổng module = 11*(n+2) + 13
    assert.equal(dr.reduce((a, b) => a + b, 0), 11 * (chu.length + 2) + 13);
  }
});

test("giải mã lại đúng chuỗi — toàn bộ ASCII in được", () => {
  for (const chu of ["LT00000012", "LOT-2026/05 x", "8934588012228"]) {
    assert.equal(giaiMa(chu), chu);
  }
  let moi = "";
  for (let c = 32; c <= 126; c++) moi += String.fromCharCode(c);
  for (let i = 0; i < moi.length; i += 20) {
    const doan = moi.slice(i, i + 20);
    assert.equal(giaiMa(doan), doan);
  }
});

test("chuỗi rác → null, không ném", () => {
  for (const rac of [null, undefined, 12, "", "ký tự việt", "a\nb", "x".repeat(81)]) {
    assert.equal(thanhVachCode128B(rac), null);
  }
});

// ── Ô quét (G3b) — đọc nguồn như các test boundary khác ──────────────────
import { readFileSync } from "node:fs";

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");
const KHO = "app/(dashboard)/pharmacy/inventory/";

test("ô quét: Enter chốt một mã, bỏ mã dội trong 800ms, camera chỉ khi HTTPS", () => {
  const o = doc(`${KHO}OQuetMa.tsx`);
  assert.match(o, /e\.key === "Enter"/);
  assert.match(o, /CUA_SO_DOI_MS = 800/);
  assert.match(o, /window\.isSecureContext/);
  // Ô quét là ô RIÊNG, không chiếm ô tìm kiếm thường.
  assert.match(o, /aria-label="Ô quét mã vạch"/);
});

test("quét KHÔNG tự cộng số lượng / số đếm — chỉ nhảy tới ô để người gõ", () => {
  const pn = doc(`${KHO}PhieuNhap.tsx`);
  const kk = doc(`${KHO}KiemKho.tsx`);
  assert.match(pn, /pn-so-luong-/);
  assert.match(kk, /kk-dem-/);
  for (const f of [pn, kk]) assert.doesNotMatch(f, /so_luong: String\(Number/);
});

test("proxy chỉ cho đúng các đường mã vạch, tham số tra-ma được làm sạch", () => {
  const r = doc("app/api/pharmacy/[action]/route.ts");
  assert.match(r, /"gan-ma-vach": "\/api\/v1\/pharmacy\/gan-ma-vach"/);
  assert.match(r, /"go-ma-vach": "\/api\/v1\/pharmacy\/go-ma-vach"/);
  assert.match(r, /"tra-ma": \(q\) => `\/api\/v1\/pharmacy\/tra-ma\?\$\{new URLSearchParams/);
});

test("quầy: quét chỉ ĐIỀN SẴN lô, người bấm Chọn lô; lô hết hạn / huỷ không được điền", () => {
  const b = doc("app/(dashboard)/pharmacy/PharmacyBoard.tsx");
  assert.match(b, /kq\.lo\.trang_thai !== "ok"/);
  assert.match(b, /kiểm số rồi bấm \$\{buoc\}/);
  assert.match(b, /dong\.thao_tac\.giao_khong_lo \? "Giao thuốc \(giao đúng lô này\)" : "Chọn lô"/);
  const d = doc("app/(dashboard)/pharmacy/DongThuoc.tsx");
  assert.match(d, /loQuet && dong\.lo_goi_y\.some/);
  // Đã thu, chưa phân lô: "Giao thuốc" gửi đúng lô vừa quét, không bỏ qua im lặng.
  assert.match(d, /\.\.\.\(loGiaoQuet \? \{ drug_batch_id: loGiaoQuet\.drug_batch_id \} : \{\}\)/);
});
