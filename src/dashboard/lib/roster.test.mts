import assert from "node:assert/strict";
import test from "node:test";

import { chiaHaiHang, demBacSiTruc } from "./roster.ts";

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

test("demBacSiTruc: dòng nạp từ Excel chưa nối được staff_id vẫn được đếm", () => {
  // 2 ô trên prod có staff_id NULL (tên gõ tay từ file Excel). Bỏ qua chúng là
  // cột "Số BS" nói ít hơn số người đứng ngay bên cạnh nó trong cùng hàng.
  const rows = [
    { work_date: "2026-08-03", station: "LICH_KHAM", staff_id: null, staff_name: "BS LINH Nam khoa" },
    { work_date: "2026-08-03", station: "LICH_KHAM", staff_id: "a", staff_name: "BS Thành" },
  ];
  assert.equal(demBacSiTruc(rows, "2026-08-03"), 2);
});
