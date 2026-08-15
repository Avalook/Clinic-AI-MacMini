// Bước 2 đại tu giao diện — bảng không kẻ dọc, danh sách xuống thẻ trên mobile
// (DESIGN.md §6–§7).
//
// "Google Sheets" mà Tuyền tả (15/08/2026) đến từ đúng một thứ: kẻ ô CẢ HAI
// CHIỀU. Bảng dữ liệu chỉ được kẻ ngang bằng hairline; căn cột và khoảng trắng
// làm việc còn lại. Ngoại lệ duy nhất được phép: lưới đặt chỗ kiểu rạp phim —
// nó là ma trận ghế thật, không phải bảng dữ liệu.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) =>
  readFileSync(new URL(p, import.meta.url), "utf8")
    .replace(/\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");

test("bảng lịch tuần và Lịch đổ về: KHÔNG còn kẻ dọc", () => {
  for (const f of [
    "../app/(dashboard)/home/WeeklyAppointmentsTable.tsx",
    "../app/(dashboard)/lich-do-ve/page.tsx",
  ]) {
    const ma = doc(f);
    assert.doesNotMatch(
      ma,
      /border-r\b/,
      `${f}: border-r quay lại — đây chính là cảm giác Google Sheets`,
    );
    assert.match(ma, /border-hairline/, `${f}: kẻ ngang phải bằng hairline`);
  }
});

test("header bảng không mặc màu thương hiệu", () => {
  // Teal dành cho hành động và điểm nhấn (DESIGN.md §2). Dải teal trên đầu
  // mỗi bảng làm màu thương hiệu thành giấy dán tường — và khi mọi thứ teal
  // thì không thứ gì nổi bật nữa.
  const ma = doc("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx");
  const th = /const TH =[\s\S]{0,220}?;/.exec(ma);
  assert.ok(th, "không tìm thấy hằng TH");
  assert.doesNotMatch(th![0], /brand/, "header bảng phải nền trung tính");
});

test("danh sách khách: dưới md là thẻ xếp dọc, không phải bảng bị bóp", () => {
  const ma = doc("../app/(dashboard)/customers/CustomersView.tsx");
  // Hàng phải có hai chế độ trong CÙNG một phần tử: flex-col (mobile) và
  // md:grid (desktop). Thiếu md: là bảng bị bóp vào 375px trở lại.
  assert.match(
    ma,
    /flex w-full flex-col[^"`]*md:grid/,
    "hàng phải là thẻ dọc dưới md và lưới từ md trở lên",
  );
  // Các cột ít giá trị trên điện thoại phải được giấu — nếu không thẻ dọc
  // thành một cột dài tám tầng thông tin.
  const soGiau = (ma.match(/hidden[^"`]*md:block/g) ?? []).length;
  assert.ok(
    soGiau >= 3,
    `chỉ ${soGiau} ô được giấu trên mobile — cần ít nhất 3 (tương tác gần ` +
      "nhất, người xử lý, nút ⋮)",
  );
});

test("thẻ KPI: 2×2 trên điện thoại, 4 hàng ngang từ md", () => {
  // Bốn thẻ ép một hàng ở màn hẹp là nhãn xuống dòng từng-chữ-một — lỗi tự
  // khai khi kiểm 3 cỡ màn ngày 15/08.
  const ma = doc("../components/ui/StatCard.tsx");
  assert.match(ma, /grid-cols-2[^"`]*md:grid-cols-4/, "StatRow phải là lưới đáp ứng");
  assert.doesNotMatch(
    ma,
    /flex divide-x/,
    "flex một hàng + divide-x là bố cục đã gây lỗi, không quay lại",
  );
});
