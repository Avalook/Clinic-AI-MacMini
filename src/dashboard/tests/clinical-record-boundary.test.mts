import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string): string =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const routeSource = read("../app/api/clinical-record/route.ts");
const getSource = routeSource.split("export async function POST")[0];
const clinicSessionSource = read("../lib/clinic-session.ts");
const currentStaffSource = read("../lib/current-staff.ts");
const patientListSource = read("../app/(dashboard)/patient-list/page.tsx");
const weeklyAppointmentsSource = read(
  "../app/(dashboard)/home/WeeklyAppointmentsTable.tsx",
);

test("clinical-record GET: backend quyết ai đọc được, trang không tự đọc bảng nhạy cảm", () => {
  // 24/09/2026: cửa đọc (quyền đọc hồ sơ + thư ký chỉ khách của bác sĩ mình)
  // và mọi câu đọc nằm ở backend (`GET /api/v1/clinical-records/doc`,
  // services/ho_so_lam_sang_doc.py). Trang không còn câu `.from(` nào ở GET —
  // nó quay lại là quay lại quyết định ở frontend.
  assert.match(getSource, /\/api\/v1\/clinical-records\/doc/);
  assert.doesNotMatch(getSource, /\.from\(["']/);
  assert.doesNotMatch(getSource, /\.rpc\(["']/);
  // 24/09/2026 (Tuyền chốt): cửa đọc hỏi QUYỀN — có khối khám / kết quả —
  // không hỏi vai; quản lý có đủ khối nên đọc được.
  const py = read("../../clinicai/api/v1/routers/clinical_records.py");
  assert.match(py, /_DOC_HO_SO_GUARD = cua_y_khoa/);
  const svc = read("../../clinicai/services/ho_so_lam_sang_doc.py");
  assert.match(svc, /khach_duoc_xem/);
});

test("the clinical role authority comes from clinic_membership, not department or cookies", () => {
  assert.match(
    clinicSessionSource,
    /getCurrentStaff\(\)[\s\S]*departmentToRole\(staff\.clinic_role\)/,
  );
  // Điều cần canh là NGUỒN quyền, không phải cách viết truy vấn.
  //
  // Bản đầu đòi thấy đúng `.from("clinic_membership")`; bản sau đòi thấy
  // `membership.role` sau khi truy vấn ấy được nhúng vào cùng lượt với `staff`.
  // Cả hai đều ghim vào CÁCH VIẾT, nên cả hai đều đỏ mỗi lần tối ưu dù luật y
  // nguyên. Nguồn quyền nay là backend: getCurrentStaff hỏi GET /api/v1/me,
  // nơi get_current_identity xác thực token rồi tra chính clinic_membership ấy.
  assert.match(
    currentStaffSource,
    /fetchFromBackend<MeResponse>\("\/api\/v1\/me"\)/,
  );
  assert.match(currentStaffSource, /clinic_role:\s*me\.role/);
  // Và bản sao thứ hai KHÔNG được mọc lại: file này không tự đọc bảng nào nữa.
  // Hai bản suy vai từng lệch nhau ở mã vai lạ — backend rơi về CSKH, bản này
  // trả null — nên "chỉ thêm một truy vấn nhỏ cho nhanh" là cách nó quay lại.
  assert.doesNotMatch(currentStaffSource, /\.from\(["']staff["']\)/);
});

test("operational roles cannot open a clinical-record popup", () => {
  // 24/09/2026: mở bệnh án theo QUYỀN (docDuocYKhoa), không theo vai. Người
  // chỉ có khối vận hành (check-in, thu tiền, đặt lịch, nhà thuốc) vẫn không
  // mở được: danh sách quyền y khoa không chứa quyền vận hành nào.
  assert.match(patientListSource, /const enablePopup = await docDuocYKhoa\(\)/);
  const home = read("../app/(dashboard)/home/page.tsx");
  assert.match(home, /const writeClinical = await docDuocYKhoa\(\)/);
  // DoctorWorkBoard (/tasks) và HomeCheckin đã gỡ 18/09/2026 — hai lối mở
  // bệnh án ấy không còn tồn tại (xem man-da-gop-boundary.test.mts).
  assert.match(
    weeklyAppointmentsSource,
    /\{canWriteClinical && selAppt && \(/,
  );
  // CHỈ danh sách QUYEN_Y_KHOA (mở bệnh án). Từ 27/09/2026 cùng file có thêm
  // QUYEN_IN_PHIEU — quầy ĐỌC để IN phiếu cho khách (Tuyền "in ở mọi khâu") —
  // danh sách riêng, không bao giờ mở popup bệnh án / ghi y khoa.
  const khoi = (src: string) => {
    const i = src.indexOf("QUYEN_Y_KHOA");
    return src.slice(i, src.indexOf("]", i) + 1) || src.slice(i, src.indexOf(")", i) + 1);
  };
  const fe = khoi(read("../lib/quyen-cua-toi.ts"));
  const pyGoc = read("../../clinicai/permissions/y_khoa.py");
  const py = pyGoc.slice(pyGoc.indexOf("QUYEN_Y_KHOA"), pyGoc.indexOf(")", pyGoc.indexOf("QUYEN_Y_KHOA")) + 1);
  assert.match(fe, /clinical\.record\.write/, "bắt được đúng khối QUYEN_Y_KHOA");
  assert.match(py, /clinical\.record\.write/, "bắt được đúng khối QUYEN_Y_KHOA");
  for (const src of [fe, py]) {
    for (const vanHanh of [
      "reception.checkin.perform",
      "payment.service.collect",
      "payment.medicine.collect",
      "booking.create",
      "pharmacy.dispense",
      "service.routing.assign",
    ]) {
      assert.ok(!src.includes(`"${vanHanh}"`), `quyền vận hành ${vanHanh} không được mở y khoa`);
    }
  }
  // Hai bản danh sách (giao diện / backend) phải khớp nhau.
  const lay = (src: string) =>
    [...src.matchAll(/"((?:clinical|result)\.[a-z_.]+)"/g)].map((m) => m[1]).sort();
  assert.deepEqual(lay(fe), lay(py.slice(py.indexOf("QUYEN_Y_KHOA"), py.indexOf("QUYEN_GHI_Y_KHOA"))));
});
