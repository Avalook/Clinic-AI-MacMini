import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const board = readFileSync(
  new URL("../app/(dashboard)/doctor/board/DoctorBoard.tsx", import.meta.url),
  "utf8",
);
const page = readFileSync(
  new URL("../app/(dashboard)/doctor/board/page.tsx", import.meta.url),
  "utf8",
);

/** Mã nguồn đã BỎ CHÚ THÍCH, dùng cho các khẳng định PHỦ ĐỊNH.
 *
 *  Một câu như "trang này từng in lại 'Danh sách khám bệnh đang mở'" nằm trong
 *  chú thích giải thích vì sao đã bỏ — và bài canh phủ định lại khớp vào đúng
 *  câu ấy rồi báo đỏ. Đây là lần thứ ba lỗi này xảy ra trong dự án, nên lột chú
 *  thích ra thay vì đi sửa cách viết bình luận. */
const khongChuThich = (src: string): string =>
  src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
const pageCode = khongChuThich(page);

test("the doctor board keeps the reference design's three working regions", () => {
  assert.match(board, /aria-label="Hàng đợi đang mở"/);
  assert.match(board, /aria-label="Hồ sơ khám bệnh"/);
  assert.match(board, /aria-label="Việc còn thiếu và điều phối"/);
  // CANH TỈ LỆ, KHÔNG CANH CHUỖI LỚP.
  //
  // Bản trước ghim nguyên văn `xl:grid-cols-[minmax(250px,1.05fr)_…]`. Mỗi lần
  // chỉnh bố cục là bài kiểm đỏ vì một lý do không liên quan gì tới thứ nó
  // muốn bảo vệ — và thứ nó muốn bảo vệ là: BỆNH ÁN PHẢI RỘNG HƠN HÀNG ĐỢI.
  // Biểu mẫu khám có lưới ba cột; cột giữa hẹp thì nó không bao giờ bung ra và
  // bác sĩ phải bấm "Mục sau" liên tục.
  const layout = board.match(/xl:grid-cols-\[minmax\((\d+)px,([\d.]+)fr\)_minmax\((\d+)px,([\d.]+)fr\)/);
  assert.ok(layout, "bàn khám phải khai lưới cột cho màn rộng");
  const [, hangDoiPx, hangDoiFr, benhAnPx, benhAnFr] = layout;
  assert.ok(
    Number(benhAnFr) > Number(hangDoiFr) * 2,
    `bệnh án (${benhAnFr}fr) phải rộng hơn hẳn hàng đợi (${hangDoiFr}fr)`,
  );
  assert.ok(
    Number(benhAnPx) >= 420 && Number(hangDoiPx) >= 200,
    "cả hai vùng phải có bề rộng tối thiểu đọc được",
  );
});

test("the worklist and clinical workspace expose the reference navigation", () => {
  for (const label of [
    "Tìm bệnh nhân hoặc mã hồ sơ",
    "Chờ khám",
    "Đang khám",
    "Quay lại đọc kết quả",
    "Khám bác sĩ",
    "Chỉ định",
    "Kết quả",
    "Đơn thuốc",
    "Thuốc & thanh toán",
  ]) {
    assert.match(board, new RegExp(label));
  }
});

test("the redesign preserves real workflow actions and the shared status vocabulary", () => {
  assert.match(board, /STATUS_PRESENTATION/);
  assert.match(board, /resolveStatus/);
  assert.match(board, /WorkItemActions/);
  assert.match(board, /\/api\/work-items\/\$\{item\.id\}\/commands\/\$\{command\}/);
  assert.match(board, /Mở màn chỉ định dịch vụ/);
  assert.match(board, /visibleItems\.find\(\(item\) => item\.id === selectedId\) \?\?/);
  assert.match(board, /<QueuePanel\s+items=\{visibleItems\}/);
  assert.doesNotMatch(board, /getSupabaseService|SUPABASE_SERVICE_ROLE_KEY/);
});

test("clinical cards tell the truth when their source data is unavailable", () => {
  // Ô KHÁM BÁC SĨ ĐÃ NỐI DỮ LIỆU THẬT (07/08/2026), nên bốn thẻ "chưa kết nối
  // nội dung khám lâm sàng" không còn nữa. Bài canh đi theo Ý ĐỊNH — "đừng vẽ
  // dữ liệu lâm sàng giả" — chứ không đi theo câu chữ cũ, nên phần còn lại của
  // nó giữ nguyên và phần đã nối được thay bằng khẳng định mạnh hơn.
  for (const label of [
    "Màn này chưa kết nối nguồn dữ liệu sinh hiệu",
    "Màn này chưa kết nối chỉ định hoặc kết quả để hiển thị",
    "Màn này chưa kết nối dữ liệu đơn thuốc",
    "Màn này chưa kết nối dữ liệu thanh toán",
  ]) {
    assert.match(board, new RegExp(label));
  }

  // Biểu mẫu khám phải là biểu mẫu THẬT, chọn theo `form_code` của lượt.
  assert.match(board, /ServiceFormEngine/);
  assert.match(board, /serviceCode=\{item\.form_code\}/);
  // Và khi dịch vụ không có biểu mẫu thì phải NÓI RA, không để trống.
  assert.match(board, /chưa gắn biểu mẫu/);

  assert.doesNotMatch(board, /110\/70|36\.6|52\.0|Viêm âm đạo|Clotrimazole/);
  // Tiêu đề trang đã bỏ vì trùng với thanh trên cùng (07/08/2026).
  assert.doesNotMatch(pageCode, /Danh sách khám bệnh đang mở/);
  assert.doesNotMatch(
    pageCode + khongChuThich(board),
    /Tổng: \{visible\.length\} bệnh nhân|Lịch hôm nay/,
  );
});
