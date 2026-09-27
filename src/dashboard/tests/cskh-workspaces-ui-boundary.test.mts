// HAI MÀN ĐÃ BỊ XOÁ, và hai bài kiểm của chúng đi theo:
//
//   cskh-today/*                    → thay bằng /cskh-tasks
//   appointments/AppointmentsWorkspace + AppointmentsKanban
//                                   → không file nào import; /appointments dùng
//                                     BookingHub. Xoá 04/08/2026.
//
//   episodes/EpisodesBoard          → /episodes chuyển hướng về /customers
//                                     (0 đợt PENDING_CLOSE trên prod, không
//                                     code nào còn tạo ra). Xoá 18/09/2026.
//
//   appointments/AppointmentsRealtime → không file nào import; nó chỉ mở một
//                                     kênh Supabase Realtime rỗng để đọc tình
//                                     trạng websocket. Xoá 27/09/2026 cùng đợt
//                                     bỏ Realtime (xem dong-su-kien-boundary).
//
// Các màn còn lại trong file này vẫn được canh nguyên: customers,
// AppointmentEditModal, StatCard.
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
const appointmentEdit = read("../app/(dashboard)/customers/AppointmentEditModal.tsx");
const statCard = read("../components/ui/StatCard.tsx");

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
  // CSKH vẫn lọc được ra nhóm cần làm hôm nay — canh theo KHOÁ, không theo chữ
  // hiển thị. Nhãn đã đổi vài lần ("Có lịch sắp tới" → "Cần theo dõi"), và đổi
  // chữ trên nút là quyết định sản phẩm.
  assert.match(customers, /"upcoming"/);

  // BỐN Ô SỐ PHẢI ĐỌC CÙNG NGUỒN VỚI BẢNG BÊN DƯỚI (08/08/2026).
  //
  // Bản trước canh `appointment?.upcoming` — tức canh cho ĐÚNG cái bug: hai ô
  // "Quá SLA" và "Chờ xác nhận" đọc `cskh_action` (bảng 0 dòng) và
  // `status = 'SCHEDULED'` (không lịch nào ở đó), nên chúng hiện 0 vĩnh viễn
  // trong khi bảng ngay dưới đang có việc quá hạn.
  //
  // Tính chất thật cần giữ: phép lọc của ô số suy từ `trangThaiByPatient` —
  // cùng view mà cột "Trạng thái" và "Hạn xử lý" đọc.
  // ĐẾM THEO `co_viec_qua_han` chứ không theo việc ĐẠI DIỆN: view trả một dòng
  // cho mỗi khách, nên một người có ba việc mở chỉ hiện một. Đếm việc hiện ra
  // là đếm hụt — đo được trên bản thật: một hẹn gọi lại trễ ba ngày nằm im sau
  // một việc chưa tới hạn, và ô "Quá SLA" vẫn hiện 0.
  assert.match(customers, /qua_sla"\) \{[\s\S]{0,220}?co_viec_qua_han/);
  assert.match(customers, /cho_xac_nhan"\)\s*return tt\?\.trang_thai/);
  assert.doesNotMatch(
    customers,
    /cskhByPatient\[row\.clinic_patient_id\]\?\.deadline/,
    "ô số lại đọc cskh_action — bảng đó 0 dòng, ô sẽ hiện 0 vĩnh viễn",
  );

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
  // một con số ai đó từng chọn.
  //
  // BA VÙNG từ 08/08/2026: danh sách — VÙNG LÀM VIỆC — hồ sơ. Quang: *"tôi
  // muốn vùng làm việc của mỗi khách hàng to như này"*. Tính chất phải giữ:
  // ba vùng đứng cạnh nhau ở màn rộng, và vùng GIỮA là vùng rộng nhất — nếu ai
  // đó đảo lại thì chuỗi bước co về một cột hẹp và cả thay đổi này thành vô ích.
  const luoi = customers.match(
    /xl:grid-cols-\[minmax\((\d+)px,([\d.]+)fr\)_minmax\(0,([\d.]+)fr\)_minmax\((\d+)px,(\d+)px\)\]/,
  );
  assert.ok(luoi, "màn khách hàng phải có bố cục ba vùng khi đang chọn một khách");
  assert.ok(
    Number(luoi[3]) > Number(luoi[2]),
    `vùng làm việc (${luoi[3]}fr) phải rộng hơn danh sách (${luoi[2]}fr)`,
  );

  // Chuỗi bước phải NỐI TIẾP và GIỮ LẠI bước đã xong. Quang: *"xong rồi thì
  // tích xanh để đó không ẩn… để CSKH còn biết họ đã thao tác gì, mấy giờ."*
  const vung = readFileSync(
    new URL("../app/(dashboard)/customers/VungLamViecKhach.tsx", import.meta.url),
    "utf8",
  );
  assert.match(vung, /<Check /); // dấu tích cho bước đã xong
  // 16/09/2026 (Tuyền): bỏ nút "Làm bước này" — VÒNG TRÒN là nút. Ô CSKH bấm
  // vòng tròn để ghi / bấm lại để hoàn tác; ô của lễ tân, bác sĩ, đối tác KHOÁ.
  assert.match(vung, /onBam=\{/); // ô CSKH bấm được
  assert.match(vung, /nguon="lễ tân"/); // ô khoá, nói rõ nguồn
  assert.doesNotMatch(
    vung.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, ""),
    /Làm bước này/,
  );
  assert.match(customers, /<AppointmentEditModal/);
  // `QuickBookingModal` đã bị bỏ: nó render một màn DỰNG SẴN (tên giả, khung
  // giờ viết cứng) nên bấm "Đặt lịch hẹn" trong đó không lưu gì cả. Nay nút đi
  // thẳng sang màn đặt lịch THẬT, mang mã bệnh nhân theo. Canh cái đó.
  assert.match(customers, /router\.push\(\s*`\/appointments\?bn=/);
  assert.match(customersPage, /requireNavAccess\("\/customers"\)/);
});

test("cột danh sách hẹp chỉ nói AI, trạng thái nằm ở vùng làm việc", () => {
  // Tuyền 16/09/2026: *"chỗ trạng thái đã check-in đang chờ khám nên được cho
  // vào bên dưới dòng trạng thái khách hàng… bị thừa dòng mất tiêu rồi bị xấu"*.
  //
  // Đo được: khi đã chọn một khách, cột danh sách còn ~210px, còn chip
  // "Đã check-in — đang chờ khám" rộng 191px — nó rơi xuống một dòng riêng dưới
  // TỪNG tên, danh sách 46 khách thành một cột chữ vỡ.
  //
  // Tính chất phải giữ (không canh pixel): ở cột HẸP chỉ có nhãn mới/cũ, chip
  // trạng thái đi sang vùng "Trạng thái khách hàng — <tên>".
  assert.match(
    customers,
    /\{selected \? \([\s\S]{0,400}?<Chip[\s\S]{0,300}?moiCu\.dong1[\s\S]{0,200}?\) : \([\s\S]{0,120}?<StatusChip/,
    "cột danh sách hẹp phải là nhãn mới/cũ, không phải chip trạng thái dài",
  );
  assert.match(customers, /chipTrangThai=\{/);
  const vung = read("../app/(dashboard)/customers/VungLamViecKhach.tsx");
  assert.match(vung, /\{chipTrangThai\}/);
  // Và chỉ MỘT chỗ dựng chip ấy — hai chỗ là hẹn ngày chúng kể hai chuyện khác
  // nhau về cùng một khách.
  assert.equal((customers.match(/<StatusChip /g) ?? []).length, 2);
});

test("CSKH redesign uses the shared ClinicAI tokens instead of an extra palette", () => {
  // Năm màn đã xoá được bỏ khỏi danh sách (cskh-today ×3, AppointmentsWorkspace,
  // AppointmentsKanban). Bảy màn còn lại vẫn bị canh: không mã màu cứng, không
  // bảng màu thứ hai ngoài bộ token chung.
  for (const source of [
    customersPage,
    customers,
    appointmentsPage,
    appointmentEdit,
  ]) {
    assert.doesNotMatch(source, /#[0-9a-f]{3,8}/iu);
    assert.doesNotMatch(source, /pink|rose|fuchsia/iu);
  }
  assert.match(statCard, /bg-warning-bg/);
  assert.match(statCard, /text-warning/);
  assert.doesNotMatch(statCard, /status-on-hold/);
});

test("uploading a result file forwards the multipart boundary", () => {
  // BOUNDARY NẰM TRONG Content-Type. Bỏ header ấy đi thì FastAPI nhận một thân
  // multipart không phân tích được, và trả 422 "clinic_patient_id: Field
  // required" — nghe như client quên gửi trường, trong khi trường ấy nằm ngay
  // trong thân không đọc được.
  //
  // Đã sai đúng như vậy ngày 08/08. Gọi thẳng API bằng script thì chạy (script
  // tự đặt Content-Type), nên lỗi chỉ lộ khi bấm nút thật trên trình duyệt.
  const route = readFileSync(
    new URL("../app/api/cskh/ket-qua/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(route, /headers\["Content-Type"\] = ctIn/);
  // Và thân phải là LUỒNG: đọc cả tệp vào RAM của tiến trình Next là 80MB mỗi
  // lượt tải video, trên cùng cái máy đang chạy database.
  // Chuyển qua `chuyenTiepTaiLen` (node:http, không thời hạn — fetch/undici cắt
  // sau 5 phút chờ, mà tệp không giới hạn dung lượng thì chép lâu hơn thế).
  assert.match(route, /chuyenTiepTaiLen\(`\$\{API_BASE\}[^`]*`, request, headers\)/);
  const chuyen = readFileSync(
    new URL("../lib/chuyen-tiep-tai-len.ts", import.meta.url),
    "utf8",
  );
  assert.match(chuyen, /Readable\.fromWeb\(/);
  assert.match(chuyen, /\.pipe\(req\)/);
  assert.match(chuyen, /timeout: 0/);
  assert.doesNotMatch(route, /82 \* 1024 \* 1024/);
  assert.doesNotMatch(route, /await request\.formData\(\)/);

  // Đường ĐỌC phải chuyển tiếp Range, nếu không video không tua được.
  const doc = readFileSync(
    new URL("../app/api/cskh/ket-qua/[tepId]/noi-dung/route.ts", import.meta.url),
    "utf8",
  );
  assert.match(doc, /headers\["Range"\] = rng/);
  assert.match(doc, /content-range/);
  assert.match(doc, /new Response\(res\.body/);
});
