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

import { weekStartOf } from "../lib/roster.ts";

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

test("mọi embed `staff` trên tuong_tac_cskh phải GỌI TÊN cột khoá ngoại", () => {
  // LỖI 10/08/2026, và nó làm TRẮNG CẢ MÀN Quản lý khách hàng.
  //
  // `staff(full_name)` chạy đúng suốt vì `tuong_tac_cskh` chỉ có MỘT khoá ngoại
  // sang `staff`. Migration 20260810000009 thêm cái thứ hai (`huy_boi_staff_id`,
  // cho hoàn tác) và PostgREST từ chối cả câu:
  //   "Could not embed because more than one relationship was found for
  //    'tuong_tac_cskh' and 'staff'"
  // Không phải một cột null — là 400 cho toàn bộ truy vấn.
  //
  // Bài học rộng hơn con lỗi này: THÊM MỘT KHOÁ NGOẠI THỨ HAI sang cùng một
  // bảng là đủ để phá một câu select viết đúng từ trước. Gọi tên cột thì không
  // bao giờ mơ hồ, dù sau này có thêm bao nhiêu khoá nữa.
  // BỎ CHÚ THÍCH TRƯỚC KHI DÒ. Bản đầu của bài kiểm này đỏ vì nó khớp phải
  // chính dòng chú thích giải thích lỗi — một bài kiểm đọc mã nguồn thì phải
  // phân biệt được mã với lời kể về mã.
  const page = readFileSync(
    new URL("../app/(dashboard)/customers/page.tsx", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "");
  assert.doesNotMatch(
    page,
    /\bstaff\s*\(\s*full_name\s*\)/,
    "còn một embed `staff(full_name)` không gọi tên cột khoá ngoại — " +
      "PostgREST sẽ trả 400 cho cả câu ngay khi bảng ấy có khoá ngoại thứ hai " +
      "sang `staff`.",
  );
});

test("`/api/roster` cũng phải kiểm ngày trước khi gọi toISOString", () => {
  // TÌM ĐƯỢC KHI NGHIỆM THU 10/08/2026: `GET /api/roster?date=99-99-9999` trả
  // 500 với thân RỖNG. `weekStartOf` dựng `new Date(iso + "T00:00:00Z")` rồi gọi
  // `toISOString()` — Invalid Date thì chính lời gọi ấy ném.
  //
  // Con thứ HAI cùng họ trong một ngày (con đầu ở `/api/appointments`). Luật:
  // mọi chỗ dựng `Date` từ chuỗi NGƯỜI GỬI phải kiểm `Number.isNaN(getTime())`
  // TRƯỚC khi gọi `toISOString()`.
  // 13/08/2026 — CON THỨ BA, và nó cho thấy chỗ bài test này từng đo sai. Bản cũ
  // đọc mã nguồn của route rồi tìm chuỗi "Number.isNaN(d.getTime())". Route ấy
  // có hàm `weekStartOf` RIÊNG, đã vá; nhưng `lib/roster.ts` có một hàm CÙNG TÊN
  // chưa vá, và đó mới là bản mà TRANG CHỦ và trang lịch dùng. Bài test xanh
  // suốt, trong khi `/home?weekAppt=abc` vẫn làm sập trang chủ.
  //
  // Giờ chỉ còn MỘT hàm, ở lib, và bài test hỏi HÀNH VI của nó thay vì hỏi mã
  // nguồn trông như thế nào — cách đo cũ xanh cả khi thứ nó bảo vệ đã hỏng.
  for (const rac of ["99-99-9999", "abc", "2026-13-45", ""]) {
    assert.equal(
      weekStartOf(rac),
      null,
      `weekStartOf(${JSON.stringify(rac)}) phải trả null, không được ném`,
    );
  }
  assert.equal(weekStartOf("2026-08-05"), "2026-08-03", "ngày đúng vẫn phải ra thứ Hai");

  // Đoạn đo cũ ĐÃ BỎ (13/08/2026). Nó đọc mã nguồn của route rồi tìm chuỗi
  // "Number.isNaN(d.getTime())" — nhưng route không còn hàm riêng nữa, nó gọi
  // bản dùng chung ở lib. Chính cách đo ấy là lý do bài kiểm xanh suốt trong
  // khi trang chủ vẫn sập: nó hỏi mã nguồn TRÔNG THẾ NÀO thay vì hỏi hàm LÀM GÌ.
  // Phần hỏi hành vi nằm ngay bên trên; phần dưới đây chỉ còn kiểm câu trả lời
  // 400 mà người dùng đọc được.
  const roster = readFileSync(
    new URL("../app/api/roster/route.ts", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "");
  assert.match(
    roster,
    /Ngày không hợp lệ/,
    "phải trả 400 với câu đọc được khi `date` gõ sai, không phải 500 thân rỗng",
  );
});

test("trang chủ và trang lịch không được sập vì một tham số tuần gõ sai", () => {
  // Đây là chỗ con thứ ba thật sự nổ: `/home?weekAppt=<rác>` và
  // `/schedule?week=<rác>` lấy thẳng tham số URL đưa vào `weekStartOf`. Server
  // component mà ném thì cả trang rơi vào error.tsx — màn hình đầu ngày của mọi
  // nhân viên không mở được cho tới khi có người nghĩ ra là phải xoá đuôi URL.
  for (const [ten, duong] of [
    ["trang chủ", "../app/(dashboard)/home/page.tsx"],
    ["trang lịch", "../app/(dashboard)/schedule/page.tsx"],
  ] as const) {
    // Đây là phép đo GIÁN TIẾP — hai trang này là server component, không gọi
    // thẳng trong bài test được. Nên bài test chỉ hỏi một câu bền: mỗi chỗ nhận
    // tham số tuần từ URL đều phải có đường lùi. Phần hành vi thật của
    // `weekStartOf` đã được bài test ở trên và `lib/roster.test.mts` canh.
    const src = readFileSync(new URL(duong, import.meta.url), "utf8").replace(/\/\/.*$/gm, "");
    const soLanGoi = (src.match(/weekStartOf\(/g) ?? []).length;
    const soDuongLui = (src.match(/\?\?\s*currentWeekStartVn\(\)/g) ?? []).length;
    assert.ok(soLanGoi > 0, `${ten}: không còn gọi weekStartOf?`);
    assert.equal(
      soDuongLui,
      soLanGoi,
      `${ten}: có ${soLanGoi} chỗ đọc tuần từ URL nhưng chỉ ${soDuongLui} chỗ có ` +
        "đường lùi `?? currentWeekStartVn()` — chỗ thiếu sẽ làm sập cả trang khi " +
        "tham số gõ sai",
    );
  }
});
