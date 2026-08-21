// Màn Quản lý khách hàng đi MỘT vòng gói dữ liệu — không được lùi về mười vòng.
//
// LÁT 2 CỦA LỘ TRÌNH CHỊU TẢI, 22/08/2026. Trước đó trang /customers tự đi
// mười vòng PostgREST cho phần làm giàu, mỗi vòng kèm nghi lễ
// BEGIN/set_config/COMMIT — đo một lần mở trang ra 73 câu SQL thì 44 câu là
// nghi lễ. Gói về `/api/v1/cskh/man-khach-hang` thì mười câu chạy trên một kết
// nối. Lỗi kiểu này KHÔNG có triệu chứng chức năng: thêm lại một vòng PostgREST
// thì màn vẫn đúng dữ liệu, chỉ chậm dần — nên phải có test đếm, người đọc code
// sau không tự nhận ra được.
//
// Ba điều canh, mỗi điều hỏng một kiểu riêng:
//   1. Đúng MỘT lời gọi gói. Hai lời gọi là ai đó quên xoá bản cũ khi sửa.
//   2. KHÔNG còn `.from(...)` nào chạm chín bảng làm giàu. `.from("patient")`
//      và `.from("appointment")` vẫn hợp lệ — đó là DANH SÁCH và BỘ LỌC, không
//      phải làm giàu; backend không thay chúng.
//   3. `recall-jobs` PHẢI còn — nó không chỉ đọc: lời gọi ấy kích
//      `sinh_viec_nhac_tai_kham` phía backend, hệ không có scheduler nào khác.
//      Gộp nhầm nó vào gói là cả phòng khám mất việc "nhắc tái khám" một cách
//      im lặng.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(
  new URL("../app/(dashboard)/customers/page.tsx", import.meta.url),
  "utf8",
);

test("đúng một lời gọi gói man-khach-hang", () => {
  const goi = page.match(/fetchFromBackend[^;]*man-khach-hang\?ids=/g) ?? [];
  assert.equal(
    goi.length,
    1,
    "phải đúng MỘT lời gọi gói — nhiều hơn là quên xoá bản cũ, " +
      "bằng không là màn mất sạch dữ liệu làm giàu",
  );
});

test("không còn vòng PostgREST nào chạm chín bảng làm giàu", () => {
  // Chín bảng/view đã dọn về backend trong Lát 2. Thêm lại một dòng
  // `.from("work_roster")` là trang chạy đúng nhưng trả lại nghi lễ
  // BEGIN/set_config/COMMIT cho từng người mở màn.
  const bang = [
    "work_roster",
    "v_trang_thai_cskh",
    "v_viec_cskh",
    "tep_ket_qua",
    "phan_hoi_khach",
    "hen_goi_lai",
    "tuong_tac_cskh",
    "cskh_action",
    "visit",
  ];
  for (const b of bang) {
    assert.ok(
      !page.includes(`.from("${b}")`),
      `còn .from("${b}") — dữ liệu này phải lấy qua gói man-khach-hang`,
    );
  }
});

test("recall-jobs vẫn được gọi riêng — nó là trigger, không phải dữ liệu", () => {
  // So chuỗi thẳng, không regex vắt qua generic type: khai báo kiểu của
  // fetchFromBackend chứa dấu `;` nên `[^;]*` không với tới đường dẫn.
  assert.ok(
    page.includes('("/api/v1/cskh/recall-jobs")'),
    "lời gọi recall-jobs biến mất: sinh_viec_nhac_tai_kham sẽ không bao " +
      "giờ chạy nữa vì hệ không có scheduler nào khác kích nó",
  );
});

test("backend im thì màn phải nói ra, không hiện danh sách 'sạch bong'", () => {
  // Mười khối cùng rỗng trông y hệt phòng khám mới không có lịch sử — người
  // trực sẽ tin vào một màn trống. `goiLoi` phải tồn tại và phải nằm trong
  // điều kiện hiện băng rôn lỗi.
  assert.match(page, /const goiLoi =/);
  assert.match(
    page,
    /error \|\| goiLoi \|\|/,
    "goiLoi chưa được nối vào băng rôn lỗi — backend chết là màn trống câm lặng",
  );
});
