// HAI MÀN ĐÃ BỊ XOÁ, và hai bài kiểm của chúng đi theo:
//
//   cskh-today/*                    → thay bằng /cskh-tasks
//   appointments/AppointmentsWorkspace + AppointmentsKanban
//                                   → không file nào import; /appointments dùng
//                                     BookingHub. Xoá 04/08/2026.
//
// Tám màn còn lại trong file này vẫn được canh nguyên: customers, episodes,
// AppointmentsRealtime, AppointmentEditModal, StatCard.
//
// Bỏ một bài kiểm an ninh phải là quyết định có chủ ý. Ở đây nó canh MỘT MÀN
// KHÔNG CÒN TỒN TẠI — giữ lại thì nó chỉ đọc chuỗi rỗng rồi báo đỏ mãi, và một
// bài kiểm luôn đỏ là một bài kiểm không ai đọc nữa.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const customersPage = read("../app/(dashboard)/customers/page.tsx");
const customers = read("../app/(dashboard)/customers/CustomersView.tsx");
const appointmentsPage = read("../app/(dashboard)/appointments/page.tsx");
const realtime = read("../app/(dashboard)/appointments/AppointmentsRealtime.tsx");
const appointmentEdit = read("../app/(dashboard)/customers/AppointmentEditModal.tsx");
const statCard = read("../components/ui/StatCard.tsx");
const episodesPage = read("../app/(dashboard)/episodes/page.tsx");
const episodes = read("../app/(dashboard)/episodes/EpisodesBoard.tsx");

test("CSKH customer directory uses the catalogue-style table and a real detail panel", () => {
  for (const label of [
    "Danh sách khách hàng",
    "Chi tiết khách hàng",
    "Tất cả khách hàng",
    "Chưa có lịch",
    // Bốn thẻ số liệu của bản thiết kế hiện tại. Bản cũ chỉ có một thẻ
    // "Khách hiển thị"; màn được vẽ lại nên bài kiểm đi theo màn.
    "Cần xử lý hôm nay",
    "Quá SLA",
    "Đã hoàn thành",
  ]) {
    assert.match(customers, new RegExp(label));
  }
  // CSKH vẫn lọc được ra nhóm khách sắp đến — canh theo KHOÁ, không theo chữ
  // hiển thị. Nhãn đã đổi vài lần ("Có lịch sắp tới" → "Cần theo dõi"), và đổi
  // chữ trên nút là quyết định sản phẩm.
  assert.match(customers, /"upcoming"/);
  assert.match(customers, /appointment\?\.upcoming/);

  // HÀNG TAB ĐÃ BỎ: bốn ô số ở trên CHÍNH LÀ bộ lọc.
  //
  // Trước đây màn này có cả hai, và bốn nhãn tab không khớp bốn con số — tab
  // ghi "Quá SLA" nhưng lọc `without_appointment` (khách chưa có lịch hẹn).
  // Bấm tab rồi so với con số ở trên là ra hai kết quả khác nhau.
  assert.doesNotMatch(customers, /CUSTOMER_TABS/);
  assert.match(customers, /onSelect=\{\(\) => chonLoc\(/);

  // Con số trên ô VÀ phép lọc phải dùng CHUNG một vị từ. Đây là tính chất thật
  // sự cần giữ: bấm ô đang hiện 29 thì thấy đúng 29 dòng ấy.
  assert.match(customers, /hopVoiTab\(r, "upcoming"\)/);
  assert.match(customers, /searchedRows\.filter\(\(row\) => hopVoiTab\(row, tab\)\)/);
  // Canh CẤU TRÚC, không canh số pixel.
  //
  // Bản cũ ghim đúng `minmax(300px,380px)`. Thiết kế chỉnh panel chi tiết rộng
  // thêm 20px là bài kiểm đỏ — trong khi nó chẳng canh gì về đúng/sai, chỉ canh
  // một con số ai đó từng chọn. Điều thật sự cần giữ: danh sách và panel chi
  // tiết nằm cạnh nhau ở màn rộng, và panel có bề rộng có giới hạn (không co
  // giãn nuốt hết danh sách).
  assert.match(customers, /xl:grid-cols-\[minmax\(0,1fr\)_minmax\(\d+px,\d+px\)\]/);
  assert.match(customers, /<AppointmentEditModal/);
  assert.match(customers, /<QuickBookingModal/);
  assert.match(customersPage, /requireNavAccess\("\/customers"\)/);
});

test("episode confirmation retains its actual close and reopen contract in a three-region workspace", () => {
  for (const label of [
    "Danh sách đợt chờ xác nhận",
    "Chi tiết đợt khám",
    "Quyết định CSKH",
    "Tìm bệnh nhân hoặc mã hồ sơ",
    "Xác nhận đóng",
    "Còn theo dõi",
  ]) {
    assert.match(episodes, new RegExp(label));
  }
  assert.match(
    episodes,
    /xl:grid-cols-\[minmax\(240px,0\.82fr\)_minmax\(360px,1\.25fr\)_minmax\(250px,0\.86fr\)\]/,
  );
  assert.match(episodes, /fetch\("\/api\/episodes"/);
  assert.match(episodesPage, /requireNavAccess\("\/episodes"\)/);
});

test("CSKH redesign uses the shared ClinicAI tokens instead of an extra palette", () => {
  // Năm màn đã xoá được bỏ khỏi danh sách (cskh-today ×3, AppointmentsWorkspace,
  // AppointmentsKanban). Bảy màn còn lại vẫn bị canh: không mã màu cứng, không
  // bảng màu thứ hai ngoài bộ token chung.
  for (const source of [
    customersPage,
    customers,
    appointmentsPage,
    realtime,
    appointmentEdit,
    episodesPage,
    episodes,
  ]) {
    assert.doesNotMatch(source, /#[0-9a-f]{3,8}/iu);
    assert.doesNotMatch(source, /pink|rose|fuchsia/iu);
  }
  assert.match(statCard, /bg-warning-bg/);
  assert.match(statCard, /text-warning/);
  assert.doesNotMatch(statCard, /status-on-hold/);
});
