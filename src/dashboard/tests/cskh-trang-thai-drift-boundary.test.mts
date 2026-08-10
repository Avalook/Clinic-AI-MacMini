// LƯỚI CANH CHO DANH MỤC TRẠNG THÁI CSKH — chỗ đã vỡ ba lần liên tiếp.
//
// Mã trạng thái CSKH được chép tay ở NHIỀU nơi, và tới 10/08/2026 không một bài
// kiểm nào canh chúng. Ba lỗi Quang bắt được trong cùng một ngày đều là cùng
// một bệnh: thêm mã ở một bản, quên bản còn lại, không ai báo — màn hình chỉ
// lặng lẽ nói sai.
//
//   b2dea31 · 4383ba3 · bf3fcab   — ba lần vá liên tiếp cùng gốc
//   66c7aeb                        — "danh mục lý do huỷ có BA bản chứ không phải hai"
//
// Bài kiểm này KHÔNG đòi mọi bản phải bằng nhau. Chúng cố ý khác nhau: view chỉ
// suy được việc CÒN PHẢI LÀM, còn cột giữa còn có những trạng thái CSKH tự chọn.
// Nó chỉ đòi đúng hai điều, và đó là hai điều mà lệch thì người dùng thấy ngay:
//
//   1. Mỗi node trên cột giữa PHẢI có một bộ nút ở cột phải.
//      Thiếu → bấm vào node thì cột phải hiện "Chọn một trạng thái ở cột giữa",
//      tức màn bảo người ta làm đúng cái họ vừa làm.
//
//   2. Mỗi mã ghi được vào `trang_thai_ma` PHẢI có nhãn tiếng Việt.
//      Thiếu → "Lịch sử các lần khám" in MÃ TRẦN (`SAU_SINH_1_THANG`) ngay
//      trước mặt khách.
//
// Đọc bằng regex trên mã nguồn thay vì import: các file này là client component
// kéo theo cả React và next/navigation, và bài kiểm chạy bằng `node --test`
// thuần. Regex đủ chặt vì cả ba bảng đều là literal khai ở cấp module.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const vungLamViec = read("../app/(dashboard)/customers/VungLamViecKhach.tsx");
const hanhDong = read("../app/(dashboard)/customers/HanhDongTrangThai.tsx");
const lichSuKham = read("../app/(dashboard)/customers/LichSuCacLanKham.tsx");
const customersView = read("../app/(dashboard)/customers/CustomersView.tsx");

/** Mọi `ma: "XXX"` trong cột giữa = một node người dùng bấm được. */
function maNodeCotGiua(): string[] {
  const ra = new Set<string>();
  for (const m of vungLamViec.matchAll(/\bma:\s*"([A-Z0-9_]+)"/g)) ra.add(m[1]!);
  // Hai hàng gộp truyền mã qua prop `ma="..."` chứ không qua object literal.
  for (const m of vungLamViec.matchAll(/\bma="([A-Z0-9_]+)"/g)) ra.add(m[1]!);
  return [...ra];
}

/** Khoá của `HANH_DONG` + `HANH_DONG_THEM` — tập mã có bộ nút ở cột phải. */
function maCoBoNut(): string[] {
  const ra = new Set<string>();
  for (const ten of ["HANH_DONG", "HANH_DONG_THEM"]) {
    const i = hanhDong.indexOf(`const ${ten}: Record<string, HanhDongViec> = {`);
    assert.ok(i > 0, `không tìm thấy bảng ${ten} — bài kiểm này đã lạc hậu`);
    const than = hanhDong.slice(i, hanhDong.indexOf("\n};", i));
    for (const m of than.matchAll(/^ {2}([A-Z0-9_]+):\s*\{/gm)) ra.add(m[1]!);
  }
  return [...ra];
}

test("mỗi node ở cột giữa đều có một bộ nút ở cột phải", () => {
  const node = maNodeCotGiua();
  const coNut = new Set(maCoBoNut());
  assert.ok(node.length >= 12, `đếm được ${node.length} node, quá ít — regex hỏng?`);

  const thieu = node.filter((ma) => !coNut.has(ma));
  assert.deepEqual(
    thieu,
    [],
    "Node trên cột giữa KHÔNG có bộ nút ở HanhDongTrangThai: " +
      `${thieu.join(", ")}. Bấm vào chúng thì cột phải hiện câu "Chọn một ` +
      'trạng thái ở cột giữa" — tức màn bảo người dùng làm đúng việc họ vừa làm.',
  );
});

test("mỗi mã trạng thái đều có nhãn tiếng Việt ở Lịch sử các lần khám", () => {
  const i = lichSuKham.indexOf("const NHAN_BUOC: Record<string, string> = {");
  assert.ok(i > 0, "không tìm thấy NHAN_BUOC — bài kiểm này đã lạc hậu");
  const than = lichSuKham.slice(i, lichSuKham.indexOf("\n};", i));
  const coNhan = new Set(
    [...than.matchAll(/^ {2}([A-Z0-9_]+):/gm)].map((m) => m[1]!),
  );

  // Mọi mã có bộ nút đều ghi được vào `trang_thai_ma`, nên đều có thể xuất hiện
  // trong sổ chăm sóc của một lượt.
  const thieu = maCoBoNut().filter((ma) => !coNhan.has(ma));
  assert.deepEqual(
    thieu,
    [],
    `Mã ghi được vào sổ nhưng KHÔNG có nhãn tiếng Việt: ${thieu.join(", ")}. ` +
      "Lịch sử các lần khám sẽ in mã trần ra trước mặt khách.",
  );
});

test("bảng màu và bảng bước-tiếp của danh sách phủ cùng một tập mã", () => {
  function khoa(ten: string): string[] {
    const i = customersView.indexOf(`const ${ten}: Record<string,`);
    assert.ok(i > 0, `không tìm thấy ${ten} — bài kiểm này đã lạc hậu`);
    const than = customersView.slice(i, customersView.indexOf("\n};", i));
    return [...than.matchAll(/^ {2}([A-Z0-9_]+):/gm)].map((m) => m[1]!);
  }
  const tone = khoa("TONE_VIEC");
  const buoc = khoa("BUOC_TIEP");
  assert.deepEqual(
    [...tone].sort(),
    [...buoc].sort(),
    "TONE_VIEC và BUOC_TIEP lệch nhau. Hai bảng cùng đọc `tt.trang_thai` ở " +
      "cùng một dòng danh sách; lệch nghĩa là một trạng thái có màu mà không " +
      "có việc phải làm, hoặc ngược lại — và cả hai đều rơi vào nhánh `??` " +
      "im lặng, không nổ lỗi.",
  );
});

test("lượt đang xem đi từ MỘT vật, không ghép id và status từ hai nguồn", () => {
  // ĐÂY LÀ LỖI 10/08/2026, và nó câm hoàn toàn.
  //
  // `lich.id` từng lấy ở `selectedAppt?.appt?.id` (chỉ có khi lịch còn đổi được)
  // còn `lich.status` lấy ở `selectedAppt.status` (lịch đại diện). Một lượt đã
  // khám xong cho ra `status = "COMPLETED"` kèm `id = null`, và `lich.id` null
  // làm bộ lọc sổ theo lượt tự huỷ — mọi node tích xanh bằng dữ liệu lượt khác.
  assert.doesNotMatch(
    customersView,
    /lich=\{\{/,
    "prop `lich` đang được dựng bằng object literal tại chỗ. Nó phải là MỘT " +
      "vật (`luotDangXem`) để `id` và `status` không thể đến từ hai lượt khác nhau.",
  );
  assert.match(
    customersView,
    /lich=\{luotDangXem/,
    "prop `lich` phải đọc từ `luotDangXem`.",
  );
});

test("sổ chăm sóc không lặng lẽ rơi về sổ của cả khách", () => {
  // `lich.id ? filter(...) : lichSu` là đường lùi đã biến một `id` thiếu thành
  // "mọi bước đã xong". Rỗng thì phải rỗng, và phải có chữ nói ra.
  assert.doesNotMatch(
    vungLamViec,
    /lichSuLuotNay\s*=\s*lich\.id\s*\?\s*lichSu\.filter\([^)]*\)\s*:\s*lichSu\b/,
    "`lichSuLuotNay` đang rơi về sổ của CẢ KHÁCH khi thiếu `lich.id`. " +
      "Nó tích xanh cả timeline bằng dữ liệu của lượt khác, trong im lặng.",
  );
});
