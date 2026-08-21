import assert from "node:assert/strict";
import test from "node:test";

import {
  SHIFTS,
  SHIFT_LABEL,
  chiaHaiHang,
  currentWeekStartVn,
  demBacSiTruc,
  weekDates,
  weekStartOf,
} from "./roster.ts";

// Hai luật này là chỗ dễ đoán sai nhất của bảng lịch làm việc, và đoán sai thì
// bảng vẫn vẽ ra bình thường — chỉ nội dung là sai. Nên ghim bằng test.

test("chiaHaiHang: người đầu ở hàng trên, phần còn lại dồn xuống hàng dưới", () => {
  assert.deepEqual(chiaHaiHang([]), [[], []]);
  assert.deepEqual(chiaHaiHang(["A"]), [["A"], []]);
  assert.deepEqual(chiaHaiHang(["A", "B"]), [["A"], ["B"]]);
  // KHÔNG cắt bớt người thứ ba: Excel cũng viết "Thư/Hà Vũ" chung một ô. Cắt đi
  // nghĩa là bảng nói dối về ai đang trực hôm đó.
  assert.deepEqual(chiaHaiHang(["A", "B", "C"]), [["A"], ["B", "C"]]);
});

test("demBacSiTruc: đếm NGƯỜI ở trạm Lịch khám, không đếm dòng", () => {
  const rows = [
    // Cùng một bác sĩ, trực cả sáng lẫn chiều = HAI dòng work_roster.
    { work_date: "2026-08-04", station: "LICH_KHAM", staff_id: "a", staff_name: "BS Thành" },
    { work_date: "2026-08-04", station: "LICH_KHAM", staff_id: "a", staff_name: "BS Thành" },
    { work_date: "2026-08-04", station: "LICH_KHAM", staff_id: "b", staff_name: "BS Nam" },
    // Trạm khác không tính vào cột "Số BS".
    { work_date: "2026-08-04", station: "LE_TAN", staff_id: "c", staff_name: "Quỳnh Anh" },
    { work_date: "2026-08-05", station: "LICH_KHAM", staff_id: "a", staff_name: "BS Thành" },
  ];
  assert.equal(demBacSiTruc(rows, "2026-08-04"), 2);
  assert.equal(demBacSiTruc(rows, "2026-08-05"), 1);
  assert.equal(demBacSiTruc(rows, "2026-08-06"), 0);
});

// ĐẦU VÀO RÁC. Ba lần hệ thống trả 500 vì cùng một họ lỗi — `new Date(<chuỗi
// người dùng>)` cho Invalid Date, rồi `toISOString()` NÉM `RangeError` — và cả
// ba lần đều được vá tại chỗ nó nổ, không ai viết bài test này. Nên con thứ ba
// mọc trong `lib/roster.ts`, tức là ở TRANG CHỦ. Bài test dưới đây là thứ canh
// họ lỗi ấy, thay cho việc phải nhớ.
test("weekStartOf: ngày không đọc được thì trả null, KHÔNG ném", () => {
  for (const rac of [
    "abc",
    "99-99-9999",
    "2026-13-45",
    "",
    "null",
    "undefined",
    "2026-02-30T00:00",
    "<script>",
  ]) {
    assert.equal(
      weekStartOf(rac),
      null,
      `"${rac}" phải cho null chứ không ném hay trả bừa một ngày`,
    );
  }
});

test("weekStartOf: ngày hợp lệ vẫn ra đúng thứ Hai của tuần đó", () => {
  // 05/08/2026 là thứ Tư → thứ Hai của tuần là 03/08.
  assert.equal(weekStartOf("2026-08-05"), "2026-08-03");
  // Chủ nhật thuộc về tuần TRƯỚC nó, không phải tuần bắt đầu ngày hôm sau.
  assert.equal(weekStartOf("2026-08-09"), "2026-08-03");
  // Chính thứ Hai thì trả về chính nó.
  assert.equal(weekStartOf("2026-08-03"), "2026-08-03");
  // Qua mốc tháng.
  assert.equal(weekStartOf("2026-09-01"), "2026-08-31");
});

test("currentWeekStartVn: luôn ra một thứ Hai đọc được", () => {
  const w = currentWeekStartVn();
  assert.match(w, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(new Date(w + "T00:00:00Z").getUTCDay(), 1, "phải là thứ Hai");
  // Và nó phải khớp với chính weekStartOf khi đưa lại vào — hai đường một kết quả.
  assert.equal(weekStartOf(w), w);
});

test("weekDates: 7 ngày liên tiếp bắt đầu từ thứ Hai", () => {
  assert.deepEqual(weekDates("2026-08-03"), [
    "2026-08-03",
    "2026-08-04",
    "2026-08-05",
    "2026-08-06",
    "2026-08-07",
    "2026-08-08",
    "2026-08-09",
  ]);
});

test("demBacSiTruc: dòng nạp từ Excel chưa nối được staff_id vẫn được đếm", () => {
  // 2 ô trên prod có staff_id NULL (tên gõ tay từ file Excel). Bỏ qua chúng là
  // cột "Số BS" nói ít hơn số người đứng ngay bên cạnh nó trong cùng hàng.
  const rows = [
    { work_date: "2026-08-03", station: "LICH_KHAM", staff_id: null, staff_name: "BS LINH Nam khoa" },
    { work_date: "2026-08-03", station: "LICH_KHAM", staff_id: "a", staff_name: "BS Thành" },
  ];
  assert.equal(demBacSiTruc(rows, "2026-08-03"), 2);
});

// Ba test dưới đây canh cùng MỘT lỗi: bản cũ liệt kê tay "SANG"/"CHIEU" ở
// app/api/roster/route.ts, nên khi thêm ca TỐI (21/08/2026) route lặng lẽ đổi ca
// tối thành "cả ngày" — quản lý xếp ca tối, hệ ghi cả ngày, không lỗi nào bật ra.
// Vá bằng cách để route đọc SHIFTS từ đây; test giữ cho nguồn ấy không lệch.

test("SHIFTS: đủ 4 lựa chọn, có ca tối", () => {
  assert.equal(SHIFTS.length, 4, "đổi số ca thì phải sửa cả nhãn lẫn API");
  assert.deepEqual([...SHIFTS].sort(), ["CHIEU", "FULL", "SANG", "TOI"]);
});

test("SHIFT_LABEL: mọi ca đều có nhãn tiếng Việt, không sót cái nào", () => {
  const thieu = SHIFTS.filter((ca) => !SHIFT_LABEL[ca]);
  assert.deepEqual(thieu, [], `ca chưa có nhãn: ${thieu.join(", ")}`);
  assert.equal(Object.keys(SHIFT_LABEL).length, SHIFTS.length, "nhãn thừa/thiếu so với SHIFTS");
  assert.equal(SHIFT_LABEL.TOI, "Tối");
});

test("luật ép ca của /api/roster: ca tối được giữ, ca lạ mới lùi về cả ngày", () => {
  // Chính là biểu thức trong app/api/roster/route.ts, tách ra để kiểm được.
  const epCa = (gui: string | undefined) =>
    (SHIFTS as readonly string[]).includes(gui ?? "") ? (gui as string) : "FULL";

  for (const ca of SHIFTS) assert.equal(epCa(ca), ca, `${ca} không được bị đổi`);
  assert.equal(epCa("TOI"), "TOI", "ca tối KHÔNG được lặng lẽ thành cả ngày");
  assert.equal(epCa("NUA_DEM"), "FULL");
  assert.equal(epCa(undefined), "FULL");
  assert.equal(epCa(""), "FULL");
});
