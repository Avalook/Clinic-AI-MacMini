// `nhanLoi()` KHÔNG được ném, dù backend trả về hình dạng nào.
//
// LỖI TÌM ĐƯỢC KHI NGHIỆM THU 11/08/2026 — nhập sai ngày sinh thì màn hình
// KHÔNG hiện gì cả.
//
// Backend nói bằng ba hình dạng, không phải hai:
//   1. {"error": "...", "message": "câu tiếng Việt"}     ← ngoại lệ ứng dụng
//   2. {"detail": "câu tiếng Việt"}                      ← HTTPException
//   3. {"error": [{loc, msg, type, input}, …]}           ← 422 kiểm tra dữ liệu
//
// Bản trước có sẵn `doDetail()` viết riêng cho hình dạng mảng — nhưng gắn vào ô
// `detail`, trong khi Pydantic đặt mảng ở ô `error`. Đúng hình dạng, sai chỗ, nên
// nhánh ấy không bao giờ chạy tới.
//
// Và nó không hỏng bằng cách hiện sai chữ. Nó NỔ:
//     const chu = d?.message ?? d?.error ?? doDetail(d?.detail);
//     return (chu ?? "").trim() || macDinh;   ← .trim() trên một Array
//     TypeError: (chu ?? "").trim is not a function
//
// Trình xử lý lỗi tự chết ⇒ `setLoi()` không bao giờ chạy ⇒ người trực bấm Lưu
// và thấy MÀN HÌNH IM LẶNG. Một câu khó hiểu còn đỡ hơn thế nhiều.
//
// `nhanLoi` đang được gọi ở ~20 chỗ khắp vùng CSKH, nên một chỗ hỏng là hai mươi
// màn cùng câm.

import assert from "node:assert/strict";
import test from "node:test";
import { nhanLoi } from "../lib/loi-api.ts";

const MAC_DINH = "Không lưu được.";

test("hình dạng 1 — message là chuỗi", () => {
  assert.equal(
    nhanLoi({ error: "BAD_REQUEST", message: "Phải nhập họ tên." }, MAC_DINH),
    "Phải nhập họ tên.",
  );
});

test("hình dạng 2 — detail là chuỗi", () => {
  assert.equal(
    nhanLoi({ detail: "Quá nhiều yêu cầu, thử lại sau." }, MAC_DINH),
    "Quá nhiều yêu cầu, thử lại sau.",
  );
});

test("hình dạng 3 — mảng Pydantic nằm ở `error`, KHÔNG ném", () => {
  // Thân thật do máy chủ staging trả về ngày 11/08/2026.
  const than = {
    error: [
      {
        type: "date_from_datetime_parsing",
        loc: ["body", "date_of_birth"],
        msg: "Input should be a valid date or datetime, invalid character in year",
        input: "32/13/2026",
      },
    ],
  };
  const cau = nhanLoi(than, MAC_DINH);
  assert.equal(typeof cau, "string", "phải trả về chuỗi, không được ném");
  assert.notEqual(cau, MAC_DINH, "không được rơi xuống câu mặc định");
  assert.match(cau, /Ngày sinh/, "phải nói rõ ô nào sai");
  assert.match(cau, /không hợp lệ/, "phải nói bằng tiếng Việt");
});

test("mảng Pydantic ở `detail` cũng phải chạy (đường cũ không được gãy)", () => {
  const cau = nhanLoi(
    { detail: [{ loc: ["body", "phone_primary"], msg: "field required" }] },
    MAC_DINH,
  );
  assert.match(cau, /Số điện thoại/);
});

test("KHÔNG ném với mọi hình dạng lạ", () => {
  // Đây là điều bài kiểm này thật sự canh: hình dạng thứ TƯ, chưa ai thấy.
  const la: unknown[] = [
    null,
    undefined,
    {},
    { message: 42 },
    { message: {} },
    { error: [] },
    { error: [{}] },
    { error: [1, 2, 3] },
    { error: { msg: "câu lồng trong đối tượng" } },
    { detail: { nested: { deep: true } } },
    { message: null, error: null, detail: null },
    { error: [{ msg: null }] },
  ];
  for (const than of la) {
    const cau = nhanLoi(than as never, MAC_DINH);
    assert.equal(
      typeof cau,
      "string",
      `ném hoặc trả về thứ không phải chuỗi với: ${JSON.stringify(than)}`,
    );
    assert.ok(cau.length > 0, "không bao giờ được trả về chuỗi rỗng");
  }
});

test("đối tượng lồng trong mảng vẫn lấy được câu", () => {
  assert.match(
    nhanLoi({ error: [{ msg: "Input should be a valid integer", loc: ["body", "tuoi"] }] }, MAC_DINH),
    /tuoi: phải là một con số/,
  );
});

test("ô không có trong từ điển thì giữ nguyên tên gốc, không nuốt mất", () => {
  const cau = nhanLoi(
    { error: [{ loc: ["body", "mot_o_la_hoac"], msg: "field required" }] },
    MAC_DINH,
  );
  assert.match(cau, /mot_o_la_hoac/, "tên ô lạ vẫn phải hiện ra để còn lần được");
});

test("backend im lặng thì dùng câu mặc định", () => {
  assert.equal(nhanLoi({}, MAC_DINH), MAC_DINH);
  assert.equal(nhanLoi({ message: "   " }, MAC_DINH), MAC_DINH);
});
