import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const ROOT = new URL("../", import.meta.url);
const read = (path: string) => readFileSync(new URL(path, ROOT), "utf8");

const hangChoSource = read("app/(dashboard)/xac-nhan-ket-qua/HangChoXacNhanKetQua.tsx");
const xacNhanPageSource = read("app/(dashboard)/xac-nhan-ket-qua/page.tsx");
const tepKetQuaSource = read("app/(dashboard)/customers/TepKetQua.tsx");
const rolesSource = read("lib/roles.ts");

test("màn xác nhận kết quả: tách riêng route /xac-nhan-ket-qua và có gác phân quyền", () => {
  assert.match(
    xacNhanPageSource,
    /requireNavAccess\("\/xac-nhan-ket-qua"\)/,
    "Trang /xac-nhan-ket-qua thiếu requireNavAccess",
  );
  assert.match(
    rolesSource,
    /"\/xac-nhan-ket-qua":/,
    "roles.ts chưa đăng ký route /xac-nhan-ket-qua trong NAV_ROLES",
  );
  assert.doesNotMatch(
    hangChoSource,
    /primary_department/,
    "Không được dùng staff.primary_department để hiện vai người tải",
  );
});

test("màn xác nhận kết quả: đúng câu chữ xác nhận hợp lệ", () => {
  assert.match(
    hangChoSource,
    /Đã xác nhận tệp đúng người\/đúng chỉ định\./,
    "Thiếu câu chữ chuẩn xác nhận vận hành: 'Đã xác nhận tệp đúng người/đúng chỉ định.'",
  );
  assert.doesNotMatch(
    hangChoSource,
    /Đã duyệt kết quả/,
    "Không được nhầm lẫn giữa xác nhận tệp (CSKH/vận hành) và duyệt kết quả chuyên môn (Bác sĩ)",
  );
});

test("màn xác nhận kết quả: từ chối bắt buộc lý do", () => {
  assert.match(
    hangChoSource,
    /Vui lòng nhập lý do từ chối tệp\./,
    "Thiếu kiểm tra bắt buộc lý do khi từ chối tệp",
  );
  assert.match(
    hangChoSource,
    /payload\.ly_do\s*=\s*\(lyDo\s*\?\?\s*""\)\.trim\(\)/,
    "Payload từ chối phải trim lý do gửi lên backend",
  );
});

test("màn xác nhận kết quả: chặn tự xác nhận tệp chính mình tải lên", () => {
  assert.match(
    hangChoSource,
    /Bạn là người tải tệp này — cần người khác xác nhận\./,
    "Thiếu thông báo chặn tự xác nhận tệp do chính mình tải",
  );
});

test("màn xác nhận kết quả: hiển thị người tải đối tác chuẩn xác", () => {
  assert.match(
    hangChoSource,
    /t\.tai_len_boi_vai === "PARTNER"/,
    "Thiếu nhánh kiểm tra role PARTNER từ clinic_membership",
  );
  assert.match(
    hangChoSource,
    /· Đối tác/,
    "Thiếu hiển thị nhãn '· Đối tác' cho uploader đối tác",
  );
});

test("hồ sơ khách TepKetQua.tsx: hiển thị badge Chờ xác nhận đúng người/chỉ định", () => {
  assert.match(
    tepKetQuaSource,
    /t\.xac_nhan_trang_thai === "CHO_XAC_NHAN"/,
    "TepKetQua.tsx chưa kiểm tra xac_nhan_trang_thai === 'CHO_XAC_NHAN'",
  );
  assert.match(
    tepKetQuaSource,
    /Chờ xác nhận đúng người\/chỉ định/,
    "TepKetQua.tsx thiếu badge 'Chờ xác nhận đúng người/chỉ định'",
  );
});
