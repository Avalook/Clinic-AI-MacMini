import assert from "node:assert/strict";
import test from "node:test";

import { taoCsvExcel } from "./xuat-bang-excel.ts";

test("CSV Excel giữ dấu tiếng Việt và quote dấu phẩy, dấu ngoặc kép, xuống dòng", () => {
  const csv = taoCsvExcel(["Tên vật tư", "Ghi chú"], [["Găng tay", 'hộp, size "M"\nkiểm']]);
  assert.ok(csv.startsWith("\uFEFF"));
  assert.equal(csv, '\uFEFF"Tên vật tư","Ghi chú"\r\n"Găng tay","hộp, size ""M""\nkiểm"');
});

test("CSV ngăn công thức chạy khi mở trong Excel nhưng giữ số âm", () => {
  const csv = taoCsvExcel(["Mã", "Lệch"], [["=HYPERLINK(\"https://bad\")", -2], ["-SUM(A1:A2)", 0], ["  =1+1", 1]]);
  assert.match(csv, /'=HYPERLINK/);
  assert.match(csv, /"-2"/);
  assert.match(csv, /'-SUM/);
  assert.match(csv, /'  =1\+1/);
});
