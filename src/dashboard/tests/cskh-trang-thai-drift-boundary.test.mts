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
const motCham = read("../app/(dashboard)/customers/mot-cham.ts");

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

test("mọi trạng thái một-chạm đều có node để bấm ở cột giữa", () => {
  // `MOT_CHAM` là thứ biến một nút thành một hành động. Một mã nằm trong bảng
  // ấy mà KHÔNG có node ở cột giữa thì không ai bấm được nó — bảng có, nút
  // không, và không gì nổ lỗi.
  const i = motCham.indexOf("export const MOT_CHAM: Record<string, MotCham> = {");
  assert.ok(i > 0, "không tìm thấy bảng MOT_CHAM — bài kiểm này đã lạc hậu");
  const than = motCham.slice(i, motCham.indexOf("\n};", i));
  const ma = [...than.matchAll(/^ {2}([A-Z0-9_]+):\s*\{/gm)].map((m) => m[1]!);
  assert.ok(ma.length >= 9, `đếm được ${ma.length} mã một-chạm, quá ít`);

  const node = new Set(maNodeCotGiua());
  const thieu = ma.filter((x) => !node.has(x));
  assert.deepEqual(
    thieu,
    [],
    `Mã có trong MOT_CHAM nhưng KHÔNG có node ở cột giữa: ${thieu.join(", ")}.`,
  );
});

test("cột phải không dựng lại nút ghi cho trạng thái đã một-chạm", () => {
  // Quang 10/08/2026: *"bỏ ô đã xác nhận cuộc gọi vì bên kia ấn là được rồi"*.
  // Hai nút ghi cho một cuộc gọi là hai dòng sổ cho một sự thật.
  for (const chu of [
    'nhan="Đã gọi xác nhận lịch"',
    'nhan="Đã gọi nhắc hẹn"',
    'nhan="Check-in cho khách"',
  ]) {
    assert.ok(
      !hanhDong.includes(chu),
      `Cột phải đang dựng lại nút ${chu} — trạng thái ấy đã một-chạm ở cột giữa.`,
    );
  }
});

test("cả ba nút Kết thúc lượt khám đều đi qua đường đóng lượt", () => {
  // Quang 10/08/2026: *"ấn tái khám hay checkout hay đặt lịch mới thì bản chất
  // chúng nó đều là khám xong rồi"*.
  //
  // Trước đó chỉ nút Checkout đóng lượt; hai nút kia mở thẳng form đặt lịch và
  // để lượt cũ treo mãi ở CHECKED_IN — khách "đã khám xong" theo lời người trực
  // mà hệ thống vẫn coi là đang khám.
  assert.match(
    vungLamViec,
    /ketThucRoiDatLich\("tai-kham"\)/,
    "nút Tái khám phải đi qua `ketThucRoiDatLich`, không gọi thẳng `onDatLich`",
  );
  assert.match(
    vungLamViec,
    /ketThucRoiDatLich\("kham-moi"\)/,
    "nút Đặt lịch khám mới phải đi qua `ketThucRoiDatLich`",
  );
  // Và đường ấy phải THẬT SỰ đóng lượt, không chỉ đổi tên hàm.
  assert.match(
    vungLamViec,
    /async function ketThucRoiDatLich[\s\S]{0,400}ghiCheckout\(\)/,
    "`ketThucRoiDatLich` phải gọi `ghiCheckout` trước khi mở form đặt lịch",
  );
});

test("chip danh sách kể việc VỪA BẤM trước việc còn phải làm", () => {
  // Quang chốt 10/08/2026 sau khi thấy chip không đổi dù đã bấm đủ tám bước.
  const iChamCuoi = customersView.indexOf("const chamCuoi = nhanLanChamCuoi(");
  const iViecMo = customersView.indexOf("const nhan = nhanChiTiet(");
  assert.ok(iChamCuoi > 0 && iViecMo > 0, "không tìm thấy hai nhánh của chip");
  assert.ok(
    iChamCuoi < iViecMo,
    "Nhánh 'lần chạm gần nhất' phải đứng TRƯỚC nhánh 'việc còn phải làm' — " +
      "nếu không, bấm xong một bước là bước ấy đóng và chip không kể gì về nó.",
  );
});

test("đổi khách hoặc lượt khám xoá draft CSKH trước khi ghi", () => {
  // Draft là state nguy hiểm: nội dung gõ cho khách A mà sống qua lần
  // chọn khách B sẽ được POST với clinic_patient_id của B. Handler chọn
  // ngữ cảnh phải xoá state do cha giữ, còn key theo patient + appointment
  // buộc React tháo các form con (kể cả PhanHoiKhach).
  assert.match(customersView, /function chonKhach\([\s\S]{0,700}setGhiChuChung\(""\)/);
  assert.match(customersView, /function chonKhach\([\s\S]{0,700}setViecDangGhi\(null\)/);
  assert.match(customersView, /function chonKhach\([\s\S]{0,700}setLuotChon\(null\)/);
  assert.doesNotMatch(
    customersView,
    /onClick=\{\(\) => setSelectedId\(/,
    "không được đổi patient bằng setSelectedId trực tiếp vì draft cũ sẽ còn",
  );
  assert.match(
    customersView,
    /<VungLamViecKhach\s+key=\{`\$\{selected\.clinic_patient_id\}-\$\{luotDangXem\?\.id/,
    "vùng làm việc phải remount khi đổi patient hoặc appointment",
  );
  assert.match(
    customersView,
    /<PhanHoiKhach\s+key=\{`\$\{selected\.clinic_patient_id\}-\$\{luotDangXem\?\.id/,
    "form phản hồi phải remount theo đúng ngữ cảnh, không giữ draft khách trước",
  );
  assert.match(
    customersView,
    /<HanhDongTrangThai[\s\S]{0,180}luotDangXem\?\.id/,
    "khối action phải remount khi đổi appointment của cùng một khách",
  );
  assert.match(
    customersView,
    /onXong=\{\(appointmentId\)[\s\S]{0,500}setLuotChon[\s\S]{0,180}setGhiChuChung\(""\)/,
    "đặt lịch xong và tự chuyển lượt cũng phải xoá ghi chú của lượt cũ",
  );
});

test("tệp kết quả được gắn và lọc theo đúng appointment", () => {
  const page = read("../app/(dashboard)/customers/page.tsx");
  const tep = read("../app/(dashboard)/customers/TepKetQua.tsx");

  assert.match(tep, /appointment_id:\s*string\s*\|\s*null/);
  assert.match(page, /id, clinic_patient_id, appointment_id, ten_hien_thi/);
  assert.match(page, /appointment_id:\s*r\.appointment_id/);
  assert.match(
    customersView,
    /\.filter\(\s*\(t\) => t\.appointment_id === \(luotDangXem\?\.id \?\? null\)/,
    "không được truyền toàn bộ file của patient vào một lượt khám",
  );
  assert.doesNotMatch(
    customersView,
    /tepKetQua=\{tepByPatient\[selected\.clinic_patient_id\] \?\? \[\]\}/,
    "panel không được hiện/gửi file của lượt khác",
  );
  assert.match(
    tep,
    /if \(!appointmentId\)[\s\S]{0,180}Chọn một lượt khám/,
    "upload phải từ chối ngữ cảnh không có appointment",
  );
});
