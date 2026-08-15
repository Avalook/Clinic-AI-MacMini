// Bước 1 đại tu giao diện — nguyên tử Button/Chip và luật "không viền trên
// cung tròn" (DESIGN.md §5).
//
// Lỗi gốc Tuyền tả 15/08/2026: "các góc bo bị mỏng hơn so với cạnh". Nguyên
// nhân vật lý: `border` 1px chạy theo cung tròn bị khử răng cưa nên đoạn cong
// nhạt hơn đoạn thẳng. Cách chữa nằm trong CẤU TRÚC component: primary phủ đặc
// không viền, secondary/danger "viền" bằng ring-inset (box-shadow — vẽ đè lên
// nền, không bị ăn mòn ở góc).
//
// Bài kiểm giữ cấu trúc ấy khỏi trôi ngược — vì 304 cái nút tự vẽ ngoài kia
// chính là bằng chứng nó SẼ trôi nếu không ai canh.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) =>
  readFileSync(new URL(p, import.meta.url), "utf8")
    .replace(/\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");

test("Button không dùng `border-*` — viền là ring-inset", () => {
  const ma = doc("../components/ui/Button.tsx");
  assert.match(ma, /ring-1 ring-inset/, "secondary/danger phải viền bằng ring");
  assert.doesNotMatch(
    ma,
    /["'` ]border(-[a-z])/,
    "border 1px trên cung tròn là chính cái lỗi 'góc bo mỏng hơn cạnh'",
  );
});

test("Chip: một hình dạng, không pill, không viền", () => {
  const ma = doc("../components/ui/Chip.tsx");
  assert.match(ma, /rounded-chip/, "chip là chữ nhật mềm 6px theo thang");
  assert.doesNotMatch(ma, /rounded-full/, "pill bị cấm ở chip (DESIGN.md §4)");
  assert.doesNotMatch(ma, /border/, "chip không viền — nền nhạt + chữ đậm là đủ");
  // Vỏ dùng chung phải là MỘT: Chip render qua chipClass, không chép chuỗi.
  const soVo = (ma.match(/inline-flex h-5 items-center/g) ?? []).length;
  assert.equal(soVo, 1, "chuỗi vỏ chip phải tồn tại đúng một lần (trong chipClass)");
});

test("danh sách khách hàng không còn pill viền tự vẽ", () => {
  // Ba chip trong danh sách ("+N việc", "N lịch trùng", "Khách mới/cũ") từng là
  // pill `rounded-full border …` cỡ 10px tự vẽ tại chỗ — mỗi cái một kiểu.
  // Nay tất cả đi qua Chip/chipClass. Bài kiểm đếm để chỗ thứ tư thêm sau này
  // cũng phải theo (cùng phép với ba lưới đặt chỗ — Luật 12.2).
  const ma = doc("../app/(dashboard)/customers/CustomersView.tsx");
  assert.doesNotMatch(
    ma,
    /rounded-full border/,
    "pill có viền quay lại danh sách — dùng Chip hoặc chipClass",
  );
  assert.match(ma, /chipClass\(/, "chip bấm được phải mượn vỏ từ chipClass");
});

test("thang chữ 5 bậc tồn tại trong theme", () => {
  const css = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
  for (const bac of ["--text-label", "--text-meta", "--text-body", "--text-emph", "--text-title"]) {
    assert.match(css, new RegExp(bac + ":"), `thiếu bậc ${bac} (DESIGN.md §3)`);
  }
  assert.match(css, /--color-hairline:/, "thiếu token viền mảnh (DESIGN.md §2)");
  assert.match(css, /--radius-control: 8px/, "bo góc control phải là 8px theo thang");
});
