// `/api/appointments` KHÔNG được ném lỗi khi hỏi theo bệnh nhân mà không có ngày.
//
// LỖI 10/08/2026 — một lỗi 500 CÂM, sống suốt từ lúc nhánh "khách này đã có
// lịch gì" ra đời (09/08).
//
//   if (!date && !benhNhan) → 400          ← hỏi theo bệnh nhân KHÔNG kèm ngày
//                                            đi qua được cửa này
//   new Date(`${date}T00:00:00+07:00`)     ← `date` là null ⇒ Invalid Date
//     .toISOString()                       ← NÉM RangeError
//
// Nghĩa là chính cái nhánh sinh ra để CHẶN ĐẶT TRÙNG thì chưa từng chạy được
// lần nào. Và nó hỏng theo kiểu tệ nhất: panel bên phải rơi vào `kind: "hong"`,
// mà nhánh ấy (trước 10/08) không vẽ gì — nên màn hình trông y hệt lúc khách
// sạch lịch, và người trực đọc sự im lặng ấy thành "được, đặt đi".
//
// Ba dấu vết của cùng một lỗi: dòng `RangeError: Invalid time value` rải rác
// trong log dashboard, panel Đặt lịch im lặng, và bài kiểm
// `booking-double-check-boundary` cảnh báo về đúng sự im lặng ấy.
//
// Bài kiểm đọc mã nguồn thay vì gọi route: route cần phiên đăng nhập + Supabase,
// còn thứ cần canh ở đây là THỨ TỰ hai câu lệnh — và thứ tự thì đọc được.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const route = readFileSync(
  new URL("../app/api/appointments/route.ts", import.meta.url),
  "utf8",
);

test("cửa sổ một ngày chỉ được tính SAU khi đã chắc có `date`", () => {
  const iChanBenhNhan = route.indexOf("if (benhNhan) {");
  const iTinhNgay = route.indexOf("new Date(`${date}T00:00:00");
  assert.ok(iChanBenhNhan > 0, "không tìm thấy nhánh hỏi theo bệnh nhân");
  assert.ok(iTinhNgay > 0, "không tìm thấy chỗ dựng cửa sổ một ngày");
  assert.ok(
    iTinhNgay > iChanBenhNhan,
    "Cửa sổ một ngày đang được tính TRƯỚC nhánh hỏi theo bệnh nhân. " +
      "Nhánh ấy không có `date`, nên `new Date(...)` ra Invalid Date và " +
      "`toISOString()` ném RangeError — một lỗi 500 câm cho đúng cái nhánh " +
      "sinh ra để chặn đặt trùng.",
  );
});

test("Invalid Date bị bắt TRƯỚC khi gọi toISOString", () => {
  // Trên Invalid Date thì chính `toISOString()` là thứ ném lỗi; mọi câu kiểm
  // đặt sau nó không bao giờ chạy tới.
  const iKiem = route.indexOf("Number.isNaN(dauNgay.getTime())");
  const iGoi = route.indexOf("dauNgay.toISOString()");
  assert.ok(iKiem > 0, "không thấy câu kiểm Invalid Date");
  assert.ok(iGoi > 0, "không thấy lời gọi toISOString");
  assert.ok(
    iKiem < iGoi,
    "Câu kiểm Invalid Date đang nằm SAU toISOString — nó sẽ không bao giờ chạy.",
  );
});

test("thiếu `date` ở nhánh theo ngày trả 400, không nổ 500", () => {
  assert.match(
    route,
    /Missing date parameter/,
    "phải có câu trả lời 400 rõ ràng khi thiếu `date`",
  );
  assert.match(
    route,
    /Ngày không hợp lệ/,
    "phải có câu trả lời 400 cho một `date` gõ sai",
  );
});
