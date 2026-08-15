// Lịch của khách vừa MẤT bác sĩ — hai chỗ dễ làm sai, và cả hai đều im lặng.
//
// Tình huống số 9 trong bảng "tình huống phát sinh" khách gửi: *"Lịch bác sĩ
// thay đổi sau khi khách đã đặt → hệ thống giúp nhận biết các lịch khách bị ảnh
// hưởng để CSKH chủ động xử lý"*. Trước 13/08/2026 không có gì làm việc ấy:
// quản lý gỡ một ca trực, lịch của khách nằm im dưới tên một bác sĩ hôm đó
// không đi làm, và đường duy nhất để biết là khách tới quầy rồi mới vỡ lẽ.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { ngayVN } from "../lib/datetime.ts";

const page = readFileSync(
  new URL("../app/(dashboard)/customers/page.tsx", import.meta.url),
  "utf8",
);

test("ngayVN trả ngày theo giờ Việt Nam, không theo giờ quốc tế", () => {
  // ĐÂY LÀ CÁI BẪY THẬT. `work_roster.work_date` là ngày làm việc theo lịch Việt
  // Nam. Dùng `toISOString().slice(0,10)` để tra nó thì một lịch hẹn 06:30 sáng
  // (23:30 UTC HÔM TRƯỚC) sẽ hỏi ca trực của NGÀY HÔM TRƯỚC — và hôm trước bác
  // sĩ có trực, nên hệ thống kết luận "vẫn có người" trong khi hôm nay thì không.
  //
  // Giờ mở cửa vừa đổi thành 07:00 cả tuần (13/08), nên vùng sát ranh giới này
  // giờ có lịch thật chứ không còn là chuyện lý thuyết.
  assert.equal(ngayVN("2026-08-14T23:30:00Z"), "2026-08-15", "06:30 sáng 15/08 giờ VN");
  assert.equal(ngayVN("2026-08-15T00:30:00Z"), "2026-08-15", "07:30 sáng 15/08 giờ VN");
  assert.equal(ngayVN("2026-08-15T16:00:00Z"), "2026-08-15", "23:00 tối 15/08 giờ VN");
  assert.equal(ngayVN("2026-08-15T17:00:00Z"), "2026-08-16", "00:00 ngày 16/08 giờ VN");
  assert.equal(ngayVN(null), "", "không có giờ thì trả rỗng, không nổ");
});

test("cảnh báo mất bác sĩ dùng ngày giờ VN, không dùng toISOString", () => {
  const ma = page.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
  const dong = ma.split("\n").find((d) => d.includes("coCaTruc.has("));
  assert.ok(dong, "không còn chỗ nào tra ca trực?");
  assert.match(dong!, /ngayVN\(/, "phải tra bằng ngày giờ Việt Nam");
  assert.doesNotMatch(
    dong!,
    /toISOString/,
    "dùng toISOString ở đây là hỏi ca trực của ngày hôm trước cho mọi lịch sáng sớm",
  );
});

test("tập ca trực RỖNG không được hiểu là mọi bác sĩ đều nghỉ", () => {
  // Chốt an toàn quan trọng nhất của tính năng này. Truy vấn ca trực hỏng, hoặc
  // tuần chưa được quản lý xếp, thì tập tra cứu rỗng — và nếu cứ thế suy ra
  // "không thấy ca trực nào ⇒ mất bác sĩ" thì MỌI lịch sắp tới đều bị tô cảnh
  // báo cùng lúc.
  //
  // Người trực sẽ gọi cho hàng chục khách để nói một chuyện không xảy ra. Báo
  // nhầm hàng loạt tệ hơn không báo: sau một lần như thế thì không ai tin cảnh
  // báo ấy nữa, kể cả lần nó đúng.
  const ma = page.replace(/\/\/.*$/gm, "");
  assert.match(ma, /doCaTruc\s*=\s*coCaTruc\.size\s*>\s*0/, "phải có cờ 'đã đọc được ca trực'");
  const khoi = /mat_bac_si:[\s\S]{0,400}?,\n/.exec(ma);
  assert.ok(khoi, "không tìm thấy chỗ tính mat_bac_si");
  assert.match(khoi![0], /doCaTruc/, "phải kiểm cờ ấy TRƯỚC khi kết luận mất bác sĩ");
});

test("chỉ cảnh báo cho lịch còn cứu được", () => {
  // Lịch đã qua giờ mà mất bác sĩ thì không đổi lại được nữa. Tô đỏ ở đó chỉ làm
  // ngập màn hình và dạy người trực bỏ qua màu đỏ — cùng lý do `qua_gio_hen`
  // cũng chỉ tính cho lịch chưa check-in.
  const ma = page.replace(/\/\/.*$/gm, "");
  const khoi = /mat_bac_si:[\s\S]{0,400}?,\n/.exec(ma);
  assert.ok(khoi);
  assert.match(khoi![0], /!daQua\(/, "lịch đã qua giờ thì thôi");
  assert.match(khoi![0], /SCHEDULED/, "chỉ những trạng thái khách chưa tới nơi");
});


test("cờ mất bác sĩ tính THEO TỪNG LƯỢT, không chỉ cho lịch đại diện", () => {
  // VÌ SAO CẢNH BÁO KHÔNG NỔ SUỐT (Tuyền báo lại 14/08/2026, lần thứ hai).
  //
  // Dữ liệu đúng: lịch 07:00 15/08 của một khách gắn BS Vũ Trọng Hùng, mà ông
  // ấy có 0 ca LICH_KHAM hôm đó — đo trên prod. Truy vấn đúng, bản deploy đúng.
  //
  // Chỗ hỏng là ĐIỀU KIỆN VẼ: `selectedAppt?.mat_bac_si && luotDangXem?.id ===
  // selectedAppt.id`. Cờ chỉ được tính cho "lịch đại diện" (apptByPatient), còn
  // màn hình vẽ theo "lượt đang xem" (dựng từ lịch sử khám) — hai nguồn dựng
  // riêng. Lệch một cái là cảnh báo biến mất, và KHÔNG có gì báo rằng nó biến
  // mất. Người trực chỉ thấy một ô giờ hẹn bình thường.
  //
  // Nay cờ đi theo chính lượt, nên không còn phép so giữa hai nguồn nào cả.
  const khoiLuot = /mat_bac_si:[\s\S]{0,600}?ngayVN\(a\.slot_start\)/.exec(page);
  assert.ok(khoiLuot, "phải tính cờ cho từng lượt trong lịch sử khám");
  assert.match(khoiLuot![0], /doCaTruc/, "vẫn phải có chốt an toàn tập ca trực");
  assert.match(
    khoiLuot![0],
    /a\.bac_si_da_go_id/,
    "và phải bật cả khi bác sĩ ĐÃ bị gỡ — lúc ấy doctor_id đã về null nên " +
      "điều kiện 'có bác sĩ mà không có ca' không còn đúng",
  );
  const view = readFileSync(
    new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
  assert.match(view, /luotDangXem\?\.mat_bac_si/, "vẽ từ chính lượt đang xem");
  // Chỉ soi KHỐI cảnh báo mất bác sĩ. Cảnh báo "quá giờ hẹn" vẫn dùng phép so
  // id ấy — nó là chuyện khác và chưa được đụng tới ở lần này.
  // Cửa sổ 700: từ 15/08 khối này chứa câu rẽ nhánh hai tình huống nên dài ra.
  const khoi = /mat_bac_si[\s\S]{0,700}?\)\}/.exec(view);
  assert.ok(khoi, "không tìm thấy khối cảnh báo mất bác sĩ");
  assert.doesNotMatch(
    khoi![0],
    /selectedAppt/,
    "khối này không được đọc lịch đại diện nữa",
  );
});

test("tập ca trực dùng CHUNG cho cả hai chỗ, không hỏi database hai lần", () => {
  // Hai phép tính cùng một câu hỏi mà đọc hai lần thì có lúc chúng đọc hai
  // trạng thái khác nhau — và khi ấy lịch đại diện nói một đằng, lượt nói một nẻo.
  const soLanTruyVan = (page.match(/from\("work_roster"\)/g) ?? []).length;
  assert.equal(soLanTruyVan, 1, "chỉ được hỏi work_roster một lần cho cả màn");
});


test("CẢ HAI khối lịch hẹn đều hiện cảnh báo", () => {
  // Màn khách hàng có HAI khối vẽ giờ hẹn: một ô BẤM ĐƯỢC (lịch còn đổi/huỷ
  // được) và một khối chỉ-đọc (lịch đã đóng). Bản trước chỉ đặt cảnh báo ở khối
  // chỉ-đọc — tức là nó im lặng đúng lúc CSKH CÒN LÀM ĐƯỢC gì đó.
  //
  // Cùng kiểu sót với ba lưới đặt chỗ cùng ngày: vá một chỗ trong nhiều chỗ,
  // test xanh, deploy xanh, màn hình vẫn thiếu. Nên bài kiểm này ĐẾM.
  const view = readFileSync(
    new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
  const soKhoiVeGioHen = (view.match(/nhanLuot\(luotDangXem\)/g) ?? []).length;
  const soCanhBao = (view.match(/luotDangXem\?\.mat_bac_si/g) ?? []).length;
  assert.ok(soKhoiVeGioHen >= 2, "không tìm thấy đủ hai khối giờ hẹn");
  assert.equal(
    soCanhBao,
    soKhoiVeGioHen,
    `${soKhoiVeGioHen} khối vẽ giờ hẹn nhưng chỉ ${soCanhBao} khối cảnh báo — ` +
      "khối thiếu sẽ im lặng đúng lúc người trực còn đổi được lịch",
  );
});

test("hai tình huống mất bác sĩ có HAI câu — ở cả hai màn", () => {
  // "Đã nghỉ" = gọi KHÁCH đổi lịch; "ca đã xếp lại" = việc NỘI BỘ (gán lại
  // bác sĩ — add_shift 15/08 tự gắn phần còn ghế, nhánh này chỉ còn khi khung
  // cũ đã kín). Một câu chung thì hoặc khách bị gọi oan, hoặc lịch chờ mãi.
  const tuan = readFileSync(
    new URL("../app/(dashboard)/home/WeeklyAppointmentsTable.tsx", import.meta.url),
    "utf8",
  );
  assert.match(
    tuan,
    /bac_si_da_go_co_ca_lai\s*\?/,
    "bảng tuần phải rẽ nhánh câu theo cờ 'đã có ca lại'",
  );
  // 15/08 chiều: remove() nay HUỶ HẲN lịch (Tuyền: "slot đó thực sự bị xoá
  // đi… chỉ có đặt lịch slot mới") — câu phải nói "đã huỷ", không còn "gán
  // lại" vì không còn lịch sống để gán.
  assert.match(tuan, /lịch (cũ )?đã huỷ/, "câu phải nói rõ lịch cũ đã huỷ");

  const view = readFileSync(
    new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
    "utf8",
  );
  const soReNhanh = (view.match(/luotDangXem\?\.bs_go_co_ca_lai\s*\?/g) ?? []).length;
  assert.equal(
    soReNhanh,
    2,
    "CẢ HAI khối lịch hẹn (bấm được + chỉ-đọc) phải rẽ nhánh — vá một trong " +
      "hai là đúng lỗi 'ba lưới đặt chỗ' lặp lại",
  );
  assert.match(
    view,
    /đã huỷ[\s\S]{0,80}?đặt (lại|lịch)/,
    "câu phải nói lịch đã huỷ và việc tiếp theo là đặt lại",
  );
});

test("chip danh sách bám LƯỢT người trực tự chọn — đổi lượt là đổi ngay", () => {
  // Tuyền 15/08/2026: chuyển giữa các lượt trong "Lịch sử các lần khám" mà
  // chip bên danh sách không đổi theo. Cú chọn lượt là state trình duyệt —
  // không có sự kiện database nào để realtime mang về — nên đường đúng là
  // customerStatus đọc thẳng lượt đang xem, cùng lượt vẽ, 0ms.
  const view = readFileSync(
    new URL("../app/(dashboard)/customers/CustomersView.tsx", import.meta.url),
    "utf8",
  ).replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
  const dau = view.indexOf("function customerStatus");
  assert.ok(dau >= 0, "không tìm thấy customerStatus");
  const than = view.slice(dau, dau + 1500);
  assert.match(
    than,
    /luotChon\?\.pid/,
    "customerStatus phải hỏi luotChon ngay ĐẦU hàm — lượt tự chọn thắng mọi suy luận",
  );
  assert.match(
    than,
    /luotDangXem\?\.status/,
    "nhãn phải đọc từ CHÍNH lượt đang xem",
  );
});
