// Chip trạng thái ở danh sách khách phải kể CHUYỆN MỚI NHẤT.
//
// Tuyền 14/08/2026: bấm "Đặt lịch khám mới" xong, vùng làm việc đã chuyển sang
// lượt mới (chưa check-in) nhưng chip vẫn nói "Đã khám xong" — nó đang kể lượt
// TRƯỚC.
//
// GỐC: chip được thiết kế để kể "lần chạm cuối trong SỔ CHĂM SÓC". Nhưng có
// những việc KHÔNG đi qua sổ ấy — chúng ghi thẳng vào `appointment`:
//
//     huỷ lịch      `cancelled_at`   ← đã vá trước đó
//     đặt lịch mới  `created_at`     ← lỗ hổng cùng họ, vá ở đây
//
// Cả hai được xử bằng CÙNG một phép: so mốc thời gian với lần chạm cuối, cái
// nào xảy ra sau thì cái ấy là chuyện của khách bây giờ. Không xếp thứ tự cứng
// — nếu không thì một cuộc gọi xác nhận SAU khi đặt lịch sẽ không thắng lại
// được, và chip đứng mãi ở "Đã đặt lịch".

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const nguon = readFileSync(
  new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
  "utf8",
);
const ma = nguon.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");

const than = /function customerStatus\([\s\S]*?\n  \}/.exec(ma);

test("tìm được hàm dựng chip", () => {
  assert.ok(than, "customerStatus đã đổi hình dạng");
});

test("ĐẶT LỊCH MỚI thắng lần chạm cuối nếu nó xảy ra sau", () => {
  const k = than![0];
  assert.match(k, /created_at/, "chip phải biết lịch được tạo lúc nào");
  assert.match(
    k,
    /mocMs\(datLuc\) >= mocMs\(chamCuoiRow\.xay_ra_luc\)/,
    "phải SO MỐC với lần chạm cuối, không xếp thứ tự cứng",
  );
  assert.match(k, /"Đã đặt lịch"/, "thiếu nhãn cho lượt vừa đặt");
});

test("chỉ tính lịch CÒN SỐNG — lịch đã đóng không được kể là vừa đặt", () => {
  // Không lọc trạng thái thì một lịch đã huỷ/đã khám xong (created_at vẫn còn
  // đó) cũng kéo chip về "Đã đặt lịch", tức là đúng lỗi cũ theo chiều ngược.
  const k = than![0];
  assert.match(
    k,
    /LUOT_CHUA_DONG\.includes\(apptRow\.status\)/,
    "phải lọc theo trạng thái lượt còn sống",
  );
});

test("HUỶ LỊCH vẫn giữ phép so mốc của nó", () => {
  // Bản vá mới không được làm hỏng bản vá cũ: hai nhánh dùng chung một luật.
  const k = than![0];
  assert.match(k, /cancelled_at/);
  assert.match(
    k,
    /mocMs\(huyLuc\) >= mocMs\(chamCuoiRow\.xay_ra_luc\)/,
    "nhánh huỷ lịch phải giữ nguyên phép so mốc",
  );
});

test("`created_at` thật sự được nạp vào dữ liệu chip", () => {
  // Ranh giới quan trọng nhất, và là chỗ dễ hỏng im lặng nhất: trường này khai
  // là TUỲ CHỌN trong kiểu, nên quên nạp thì TypeScript không nói gì và bản vá
  // đứng im — chip vẫn kể chuyện cũ, không lỗi nào hiện ra.
  const page = readFileSync(
    new URL("../app/(dashboard)/customers/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(
    page,
    /created_at:\s*repr\.created_at/,
    "apptByPatient phải mang theo created_at của lịch đại diện",
  );
  assert.match(
    page,
    /slot_start,\s*status,\s*created_at/,
    "truy vấn lịch hẹn phải chọn cả cột created_at",
  );
});

test("Lễ tân check-in là chip nhảy 'Đã check-in' — cùng phép so mốc thời gian", () => {
  // Check-in không đi qua sổ chăm sóc (Lễ tân bấm ở màn khác), nên trước
  // 17/08 chip vẫn kể cuộc gọi hôm kia trong khi khách ngồi phòng chờ.
  // Nhánh mới phải (1) đứng TRƯỚC nhánh đặt-lịch — CHECKED_IN cũng nằm trong
  // LUOT_CHUA_DONG nên đứng sau là bị "Đã đặt lịch" nuốt; (2) so mốc
  // checked_in_at với lần chạm cuối như hai nhánh huỷ/đặt.
  const view = readFileSync(
    new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "");
  const denLuc = view.indexOf("const denLuc");
  const datLuc = view.indexOf("const datLuc");
  assert.ok(denLuc > 0 && datLuc > 0, "thiếu một trong hai nhánh");
  assert.ok(denLuc < datLuc, "nhánh check-in phải đứng TRƯỚC nhánh đặt lịch");
  const khoi = view.slice(denLuc, denLuc + 500);
  assert.match(khoi, /mocMs\(denLuc\) >= mocMs\(chamCuoiRow\.xay_ra_luc\)/);
  assert.match(khoi, /Đã check-in/);

  // Nguồn mốc: page.tsx phải đắp checked_in_at từ visit vào lịch đại diện.
  const page = readFileSync(
    new URL("../app/(dashboard)/customers/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(page, /ap\.checked_in_at = visitTheoLich\[ap\.id\]\?\.batDau/);
});

test("đếm ngược tới giờ khám: có luật DỪNG, và đứng ở CẢ HAI khối lịch hẹn", () => {
  // Tuyền 17/08: "có bị vô hạn thời gian không, có logic dừng khi đến hạn
  // không?" — ba chốt: chỉ đếm trạng thái chưa-tới, interval tự tắt khi chạm
  // mốc (không đếm âm), tới giờ thì im để dòng ⚠ quá-giờ của server tiếp quản.
  const dem = readFileSync(
    new URL("../app/(dashboard)/customers/DemNguocKham.tsx", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
  assert.match(dem, /\["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED"\]/);
  assert.match(
    dem,
    /Date\.now\(\) >= moc[\s\S]{0,120}?clearInterval/,
    "chạm mốc là interval phải tự tắt — không đếm âm vô hạn",
  );
  assert.match(dem, /if \(conMs <= 0\) return null/);

  const view = readFileSync(
    new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
    "utf8",
  );
  assert.equal(
    (view.match(/<DemNguocKham/g) ?? []).length,
    2,
    "khối bấm-được và khối chỉ-đọc đều phải có — vá một trong hai là bài ba lưới",
  );
});

test("ô Quá SLA cùng thước đo với chip đỏ — quá GIỜ hẹn cũng được đếm", () => {
  // Tuyền 17/08: khách "Đã quá giờ hẹn — chưa check-in" đỏ rực mà ô Quá SLA
  // trên đầu vẫn 0. Nguyên nhân: view đo theo NGÀY, chip đo theo PHÚT — ô số
  // phải cộng cả hai, không thì "ô 0 mà dòng dưới đang đỏ" (đúng bệnh tab
  // Ưu tiên đã chữa 08/08, được chú thích ngay trong hopVoiTab).
  const view = readFileSync(
    new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "");
  const khoi = /if \(key === "qua_sla"\) \{[\s\S]{0,220}?\}/.exec(view);
  assert.ok(khoi, "không tìm thấy nhánh qua_sla trong hopVoiTab");
  assert.match(khoi![0], /co_viec_qua_han/, "thước NGÀY của view vẫn giữ");
  assert.match(
    khoi![0],
    /qua_gio_hen/,
    "thước PHÚT phải được cộng — ô số cùng thước với chip đỏ dưới nó",
  );
});

test("hoàn tác là chip quên ngay dòng đã rút — đủ 6 chỗ bỏ qua huy_luc", () => {
  // Tuyền 17/08: "khi click nút tròn hoàn tác, trạng thái ở danh sách khách
  // hàng cũng phải đồng bộ, không được delay". Lỗi thật không phải delay:
  // các overlay frontend đọc dòng MỚI NHẤT của sổ mà không né dòng đã hoàn
  // tác (`huy_luc`), nên chip kể tiếp câu chuyện vừa bị rút lại — kẹt cho tới
  // khi có chạm mới. View DB đã lọc `huy_luc IS NULL` từ 20260810000009;
  // đây là phía frontend của cùng luật. ĐẾM đủ các chỗ (Luật 12):
  //   CustomersView: chamCuoiRow, nhanChiTiet, tomTatTuongTac,
  //                  cột "ai xử lý", cảnh báo QUAN_LY_DOI_GIO  → 5
  //   page.tsx:      bước của lượt (mốc CHECK_OUT)             → 1
  const view = readFileSync(
    new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "");
  const page = readFileSync(
    new URL("../app/(dashboard)/customers/page.tsx", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "");
  const demView = (view.match(/!(?:d|x)\.huy_luc/g) ?? []).length;
  assert.ok(
    demView >= 5,
    `CustomersView phải né huy_luc ở đủ 5 overlay, đang thấy ${demView}`,
  );
  assert.match(
    page,
    /d\.appointment_id === a\.id && !d\.huy_luc/,
    "bước của lượt (page.tsx) phải lọc dòng đã hoàn tác — CHECK_OUT rút lại là mốc kết thúc biến mất",
  );
  // Chiều ngược: dòng thời gian trong hồ sơ VẪN nhận đủ cả dòng đã hoàn tác
  // (để vẽ gạch ngang) — không ai được lọc trước khi đưa vào lichSu.
  assert.match(
    view,
    /lichSu=\{tuongTacByPatient\[selected\.clinic_patient_id\] \?\? \[\]\}/,
    "dòng thời gian phải nhận NGUYÊN sổ, kể cả dòng đã hoàn tác",
  );
});
