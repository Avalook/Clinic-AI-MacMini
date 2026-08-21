import assert from "node:assert/strict";
import test from "node:test";

import {
  docKhungNhanLich,
  thuCuaNgay,
  trongKhungNhanLich,
} from "./khung-nhan-lich.ts";

// Ba ca mặc định của Dr4Women, đã quy ra phút và gộp: nghỉ trưa 13:00–14:00
// cắt ngày làm hai, còn chiều với tối liền nhau nên nhập làm một khoảng.
const KHUNG: [number, number][] = [
  [480, 780],
  [840, 1290],
];

test("trongKhungNhanLich: giờ trong ca thì nhận", () => {
  const k = { "1": KHUNG };
  assert.equal(trongKhungNhanLich(k, 1, 8 * 60), true, "08:00 đầu ca sáng");
  assert.equal(trongKhungNhanLich(k, 1, 10 * 60), true, "10:00");
  assert.equal(trongKhungNhanLich(k, 1, 17 * 60 + 30), true, "17:30 giao chiều-tối");
  assert.equal(trongKhungNhanLich(k, 1, 21 * 60 + 29), true, "21:29 sát cuối ca tối");
});

test("trongKhungNhanLich: ba khoảng trống thì từ chối", () => {
  const k = { "1": KHUNG };
  assert.equal(trongKhungNhanLich(k, 1, 7 * 60 + 15), false, "07:15 trước ca sáng");
  assert.equal(trongKhungNhanLich(k, 1, 13 * 60 + 30), false, "13:30 nghỉ trưa");
  assert.equal(trongKhungNhanLich(k, 1, 21 * 60 + 30), false, "21:30 vừa hết ca tối");
});

test("trongKhungNhanLich: chưa biết thì KHÔNG chặn", () => {
  // Hỏi hụt mà chặn là khoá sạch lưới vì một lần mạng lỗi. Backend vẫn còn
  // chốt cứng ở dưới, nên sai theo hướng này chỉ mất một lần bấm.
  assert.equal(trongKhungNhanLich(undefined, 1, 13 * 60), true);
  assert.equal(trongKhungNhanLich({}, 1, 13 * 60), true);
  assert.equal(trongKhungNhanLich({ "1": [] }, 1, 13 * 60), true);
  assert.equal(trongKhungNhanLich({ "2": KHUNG }, 1, 13 * 60), true, "thứ khác");
});

test("docKhungNhanLich: đọc đúng dữ liệu backend gửi", () => {
  const k = docKhungNhanLich({ "1": [[480, 780], [840, 1290]] });
  assert.deepEqual(k["1"], KHUNG);
  assert.equal(trongKhungNhanLich(k, 1, 13 * 60 + 30), false);
});

test("docKhungNhanLich: thiếu khoá thì trả rỗng, không nổ", () => {
  // Backend cũ chưa gửi khoá này. Cả màn đặt lịch không được sập vì thế —
  // chỉ là không lọc được giờ, và backend vẫn chặn.
  assert.deepEqual(docKhungNhanLich(undefined), {});
  assert.deepEqual(docKhungNhanLich(null), {});
});

test("docKhungNhanLich: dữ liệu hỏng thì bỏ hẳn, không chặn bừa", () => {
  const rac: unknown[] = [
    { "1": "khong-phai-mang" },
    { "1": [[480]] },
    { "1": [["480", "780"]] },
    { "1": [[780, 480]] },
    { "1": [[480.5, 780]] },
    "chuoi",
    42,
  ];
  for (const r of rac) {
    assert.deepEqual(docKhungNhanLich(r), {}, `phải bỏ: ${JSON.stringify(r)}`);
  }
});

test("thuCuaNgay: 0 là Chủ nhật", () => {
  assert.equal(thuCuaNgay("2026-08-23"), 0, "23/08/2026 là Chủ nhật");
  assert.equal(thuCuaNgay("2026-08-21"), 5, "21/08/2026 là thứ Sáu");
});
