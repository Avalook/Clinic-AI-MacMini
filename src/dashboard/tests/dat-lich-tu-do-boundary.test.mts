// "ĐẶT TỰ DO" KHÔNG ĐƯỢC HIỆN NHƯ MỘT HẠN MỨC.
//
// Tuần chưa công bố lịch trực thì phòng khám đặt thoải mái (luật Tuyền chốt
// 15/09/2026) — KHÔNG có trần nào để so. Nhưng màn vẫn kể kèm một con số:
//
//     ô ngày   "Tự do · 3"          ← 3 là số đã đặt, đọc như "còn 3"
//     panel    "0 đã đặt · đặt tự do"  ← đọc như một hạn mức đang đếm dần
//
// Tuyền 16/09/2026: *"nếu là tự do đặt thì sức chứa chỉ cần ghi đặt tự do là
// được"*. Con số ấy không sai, nó chỉ trả lời một câu không ai hỏi — và người
// trực nhìn quen mắt sẽ đọc nó thành chỗ còn lại.
//
// Cùng file canh luôn HAI Ô ĐÃ BỎ khỏi hàng lọc màn Đặt lịch, vì chúng có điểm
// neo bằng chú thích: ai bỏ chú thích đi thì cũng mất luôn đường quay lại.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { chuKhung, chuONgay, type KhungQuote, type ONgay } from "../app/(dashboard)/appointments/cho-trong.ts";

const hub = readFileSync(
  new URL("../app/(dashboard)/appointments/BookingHub.tsx", import.meta.url),
  "utf8",
);

const oNgay = (t: ONgay["trang_thai"], daDat: number, conCho: number | null): ONgay => ({
  date: "2026-09-16",
  trang_thai: t,
  da_dat: daDat,
  con_cho: conCho,
  tong_cho: conCho === null ? null : conCho + daDat,
});

const khung = (used: number, conLai: number): KhungQuote => ({
  time: "08:15",
  minute_of_day: 495,
  slot_minutes: 15,
  regular_cap: used + conLai,
  regular_used: used,
  con_lai: conLai,
  state: "free",
});

test("ô ngày tự do không in ra một trần không tồn tại", () => {
  assert.equal(chuONgay(oNgay("TU_DO", 0, null)), "Tự do");
  // Đã có người đặt thì vẫn nói ra, nhưng KHÔNG kèm "/N".
  assert.doesNotMatch(chuONgay(oNgay("TU_DO", 3, null)), /\//);
  // Ngày có trần thật thì ngược lại: phải nói còn bao nhiêu.
  assert.equal(chuONgay(oNgay("CON_CHO", 1, 2)), "Còn 2");
});

test("khung giờ tự do bấm được và không đếm chỗ còn lại", () => {
  const tuDo = chuKhung(khung(0, 0), true, false);
  assert.equal(tuDo.khoa, false, "tự do mà khoá thì cả tuần không đặt được");
  assert.doesNotMatch(tuDo.chu, /chỗ/);
  // Còn khi có trần: hết chỗ là khoá.
  assert.equal(chuKhung(khung(2, 0), false, false).khoa, true);
  assert.match(chuKhung(khung(1, 1), false, false).chu, /Còn 1 chỗ/);
});

test("ô có người khác giữ thì VÀNG và vẫn bấm được; đầy mới đỏ và khoá", () => {
  // Tuyền 16/09/2026: *"ô nào đang có người giữ thì màu vàng còn đầy màu đỏ"*.
  // Giữ chỗ là TƯ VẤN, không phải khoá — chốt chặn thật nằm ở trigger lúc
  // INSERT, nên khoá ô ở đây là tự cấm mình đặt vào một chỗ vẫn còn trống.
  const giu = chuKhung(khung(1, 1), false, false, true);
  assert.equal(giu.chu, "Đang giữ");
  assert.match(giu.mau, /warning/);
  assert.equal(giu.khoa, false);

  // ĐẦY THẮNG ĐANG GIỮ: đặt vào ô đầy là máy chủ từ chối, dù ai đang giữ.
  const day = chuKhung(khung(2, 0), false, false, true);
  assert.equal(day.chu, "Đã đầy");
  assert.match(day.mau, /danger/);
  assert.equal(day.khoa, true);

  // Tuần tự do cũng phải thấy người bên cạnh đang giữ.
  assert.equal(chuKhung(khung(0, 0), true, false, true).chu, "Đang giữ");
  // Khung đã qua thì không còn chuyện tranh chỗ.
  assert.equal(chuKhung(khung(1, 1), false, true, true).chu, "Đã qua");
});

test("panel Thông tin đặt lịch: tự do thì chỉ ghi 'đặt tự do'", () => {
  const nhanh = /datTuDo[\s\S]{0,120}?\?\s*("[^"]*"|`[^`]*`)/.exec(hub);
  assert.ok(nhanh, "không tìm thấy nhánh `datTuDo` của dòng Sức chứa");
  assert.equal(nhanh![1], '"đặt tự do"');
  assert.doesNotMatch(hub, /đã đặt · đặt tự do/);
});

test("lọc bác sĩ nằm TRÊN CỘT nó lọc, và sống qua việc đổi khách", () => {
  // Tuyền 16/09/2026: bỏ ô lọc khỏi hàng lọc, rồi *"khi ấn vào vùng bác sĩ này,
  // sổ ra loạt tên bác sĩ, trên đầu là thanh tìm kiếm… dụng ý của tôi là có thể
  // dùng nó để đặt 1 khung giờ cho nhiều bệnh nhân luôn"*.
  const ma = hub.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "");
  assert.doesNotMatch(ma, /<option value="all">Tất cả bác sĩ/);
  assert.doesNotMatch(ma, /href="\/schedule"/);
  // Nút "Lịch làm việc" bỏ hẳn thì phải còn chú thích nói đường quay lại.
  assert.match(hub, /Lịch làm việc[\s\S]{0,200}?dựng lại/);

  // BỘ LỌC PHẢI Ở TRONG BẢNG. Màn ngoài giữ hộ thì hai màn hiểu khác nhau —
  // và đổi khách ở BookingHub sẽ kéo theo mất lọc, đúng thứ Tuyền muốn giữ.
  const bang = readFileSync(
    new URL("../app/(dashboard)/appointments/BangBacSiTuan.tsx", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(bang, /locBacSi/, "lọc bác sĩ không được nhận từ ngoài nữa");
  assert.match(bang, /const \[loc, setLoc\] = useState<string>\("all"\)/);
  assert.match(bang, /Tất cả bác sĩ/);
  assert.match(
    bang,
    /if \(moLoc\) oTim\.current\?\.focus\(\)/,
    "ô tìm phải tự nhận con trỏ — gõ được ngay, không bấm thêm nhát nữa",
  );
  assert.match(bang, /unaccentVi\(b\.full_name\)/, "tìm tên phải bỏ dấu");
  // `chonKhach` của BookingHub không được đụng tới bộ lọc — nó ở màn khác hẳn.
  assert.doesNotMatch(ma, /setLoc\(/);
});
