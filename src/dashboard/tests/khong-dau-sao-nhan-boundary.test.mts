// BỎ DẤU `*` Ở NHÃN / TIÊU ĐỀ (V6, Tuyền chốt 30/09/2026).
//
// Trước đó 22 chỗ trong 11 file vẽ dấu `*` sau nhãn ô bắt buộc — 4 helper vẽ
// theo điều kiện (`Req`, `Field required`, `o.batBuoc`, `required &&`) và 18
// chuỗi viết tay ("Số lô *", `Lý do huỷ <span>*</span>`…). Tuyền: bỏ hết ký
// hiệu; Ô VẪN BẮT BUỘC — kiểm tra khi bấm Lưu và ở máy chủ giữ nguyên, câu báo
// lỗi nói rõ ô nào thiếu.
//
// Bài này quét MỌI tệp .tsx của app/ và components/ để dấu `*` không quay lại
// trong nhãn: chuỗi kết thúc bằng " *", phần tử chỉ chứa "*", `{" *"}`.

import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const GOC = fileURLToPath(new URL("..", import.meta.url));

function tsx(thuMuc: string): string[] {
  const ra: string[] = [];
  for (const ten of readdirSync(thuMuc)) {
    const p = join(thuMuc, ten);
    if (statSync(p).isDirectory()) {
      if (ten !== "node_modules") ra.push(...tsx(p));
    } else if (ten.endsWith(".tsx")) {
      ra.push(p);
    }
  }
  return ra;
}

/** Bỏ chú thích (`// …`, `/* … *\/`, `{/* … *\/}`) — dấu * trong chú thích không vẽ gì. */
const boChuThich = (ma: string) =>
  ma.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");

const MAU: [RegExp, string][] = [
  // "Số lô *" · 'Lý do *' · `Tên thuốc *`
  [/["'`][^"'`\n]*[^\s"'`*/]\s+\*["'`]/, 'chuỗi nhãn kết thúc bằng " *"'],
  // <label>Dịch vụ *</label> · <span>Lý do *</span> — kể cả khi chữ xuống dòng
  // trước thẻ đóng (`{i + 1}. Thuốc *` rồi `</span>` ở dòng dưới).
  [/[^\s>*/{}]\s+\*\s*<\//, 'chữ nhãn kết thúc bằng " *" ngay trước thẻ đóng'],
  // <span className="text-danger">*</span>
  [/>\s*\*\s*</, 'phần tử chỉ chứa dấu "*"'],
  // {" *"} · {"*"}
  [/\{\s*["'`]\s*\*\s*["'`]\s*\}/, 'biểu thức JSX vẽ dấu "*"'],
];

test("không nhãn / tiêu đề nào vẽ dấu * (ô vẫn bắt buộc, chỉ bỏ ký hiệu)", () => {
  const loi: string[] = [];
  for (const f of [...tsx(join(GOC, "app")), ...tsx(join(GOC, "components"))]) {
    // Quét CẢ TỆP (không từng dòng): chữ JSX hay xuống dòng trước thẻ đóng.
    const ma = boChuThich(readFileSync(f, "utf8"));
    for (const [mau, ly_do] of MAU) {
      for (const m of ma.matchAll(new RegExp(mau.source, `${mau.flags}g`))) {
        const dong = ma.slice(0, m.index).split("\n").length;
        loi.push(`${f.slice(GOC.length)}:${dong} — ${ly_do}: ${m[0].trim()}`);
      }
    }
  }
  assert.deepEqual(loi, [], `Dấu * quay lại trong nhãn:\n${loi.join("\n")}`);
});

test("bài quét bắt được đúng các kiểu dấu * đã từng có", () => {
  const mau = (d: string) => MAU.some(([m]) => m.test(d));
  assert.ok(mau('{o("so_lo", "Số lô *")}'));
  assert.ok(mau("<label className={LABEL}>Dịch vụ *</label>"));
  assert.ok(mau('Lý do huỷ <span className="text-danger">*</span>'));
  assert.ok(mau('{required ? <span className="text-danger"> *</span> : null}'));
  assert.ok(mau('return <span className="text-brand-600">*</span>;'));
  assert.ok(mau('{walkin ? "Kênh đặt" : "Kênh đặt *"}'));
  assert.ok(mau("{i + 1}. Thuốc *\n                  </span>"));
  // Không bắt nhầm phép nhân, glob, hay chữ bình thường.
  assert.ok(!mau("{gia * soLuong}</span>"));
  assert.ok(!mau("const tong = gia *"));
  assert.ok(!mau('accept="image/*"'));
  assert.ok(!mau("<span>Họ tên</span>"));
});
