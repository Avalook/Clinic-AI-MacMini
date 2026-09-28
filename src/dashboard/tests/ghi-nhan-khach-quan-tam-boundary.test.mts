// Khách chỉ hỏi thông tin, chưa chốt ngày — phải có LỐI VÀO để ghi lại.
//
// TÌM ĐƯỢC KHI NGHIỆM THU 11/08/2026, tình huống nghiệp vụ số 2 trong 15 tình
// huống — và là tình huống DUY NHẤT có lỗ hổng.
//
// Ghi được người đó thì hệ thống LÀM ĐƯỢC: `NewPatientForm` bỏ hẳn bước đặt lịch
// khi chưa chọn dịch vụ/ngày/giờ (`if (!wantsAppointment) return true`). Cái
// thiếu là LỐI VÀO. Nút "Thêm khách hàng" đã bị gỡ có chủ ý ngày 09/08 vì khách
// mới của CSKH sinh ra ở màn Đặt lịch — hợp lý cho luồng chính, nhưng nó bỏ rơi
// đúng ca này. Lối duy nhất còn lại là bấm một ô giờ trên bảng tuần, mà làm thế
// là đã gán sẵn ngày giờ, tức không còn là "chưa chốt ngày" nữa.
//
// Người trực đang nghe điện thoại thì không ai đi gõ URL bằng tay. Không có nút
// nghĩa là khách ấy KHÔNG được ghi lại — và một khách đã gọi tới mà phòng khám
// không có số để gọi lại là một khách bị mất.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const view = readFileSync(
  new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
  "utf8",
);

/** Bỏ chú thích JSX và dòng — bài kiểm phải dò MÃ, không dò lời kể về mã. */
const ma = view
  .replace(/\{\/\*[\s\S]*?\*\/\}/g, "")
  .replace(/\/\*[\s\S]*?\*\//g, "")
  .replace(/\/\/.*$/gm, "");

test("màn CSKH có lối vào ghi khách chưa chốt lịch", () => {
  assert.match(
    ma,
    /href="\/patients\/new"/,
    "không còn nút nào dẫn tới trang tạo hồ sơ",
  );
  // Tên đổi 13/08/2026 sang "Thêm khách hàng mới" — bài kiểm đi theo. Điều nó
  // canh không phải một câu chữ cụ thể mà là: MÀN NÀY CÒN LỐI VÀO, và lối ấy
  // đọc là hiểu. Nên chấp nhận cả tên cũ lẫn tên mới, và chỉ đỏ khi nút biến mất.
  assert.match(
    ma,
    /Thêm khách hàng mới|Ghi nhận khách quan tâm/,
    "nút phải nói rõ nó làm gì",
  );
});

test("lối vào KHÔNG được gán sẵn ngày giờ", () => {
  // Đây là toàn bộ lý do nút này tồn tại. Gán ?date=/?time= là biến nó thành
  // luồng ĐẶT LỊCH — đúng thứ đã có rồi, và đúng thứ KHÔNG giải được ca này.
  assert.doesNotMatch(
    ma,
    /href="\/patients\/new\?(date|time)/,
    "nút gán sẵn ngày/giờ thì lại thành luồng đặt lịch, không phải ghi nhận",
  );
});

test("gác bằng ĐÚNG cửa của trang đích /patients/new", () => {
  // Đợt 3 (27/09/2026): /patients/new gác bằng lego 11 `patient.create`
  // (`requireNavAccess`). Nút phải hỏi cùng luật đó — `moDuocMan("/patients/new")`
  // ở máy chủ — không phải vai canWriteIntake (cờ `canEdit`). Lệch một cái là
  // người có lego không thấy nút, hoặc thấy nút rồi bị đá về /home.
  const khoi = /\{canThemKhach && \([\s\S]{0,600}?patients\/new/.exec(ma);
  assert.ok(khoi, "nút phải nằm trong nhánh `canThemKhach`");
  assert.doesNotMatch(
    ma,
    /\{canEdit && \([\s\S]{0,600}?href="\/patients\/new"/,
    "nút không được gác bằng vai (canEdit) nữa",
  );
  const trang = readFileSync(
    new URL("../app/(dashboard)/customers/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(
    trang,
    /canThemKhach = await moDuocMan\("\/patients\/new"\)/,
    "cờ phải do máy chủ tính bằng đúng luật cửa của trang đích",
  );
});

test("trang đích vẫn cho lưu khi KHÔNG chọn dịch vụ/ngày/giờ", () => {
  // Nếu ai đó bắt buộc dịch vụ+ngày+giờ ở form, nút này thành vô dụng ngay mà
  // không ai biết — bài kiểm ở trên vẫn xanh vì nút vẫn còn đó.
  const form = readFileSync(
    new URL(
      "../app/(dashboard)/patients/new/NewPatientForm.tsx",
      import.meta.url,
    ),
    "utf8",
  ).replace(/\/\/.*$/gm, "");
  assert.match(
    form,
    /if \(!wantsAppointment\) return true;/,
    "form không còn bỏ qua bước đặt lịch ⇒ không ghi được khách chưa chốt ngày",
  );
});
