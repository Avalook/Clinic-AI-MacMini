// Ô tìm khách màn Đặt lịch tìm trên TOÀN BỘ hồ sơ (06/10/2026).
//
// Sáng 06/10 nạp ~8.600 khách cũ từ Notion; màn Đặt lịch chỉ nạp 200 khách mới
// tạo gần nhất rồi lọc trên trình duyệt → lễ tân gõ tên / số khách cũ không ra
// và tạo hồ sơ trùng. Canh ở đây: ô tìm hỏi máy chủ, route Next chỉ chuyển
// tiếp, máy chủ tìm bằng ĐÚNG hàm của Danh sách bệnh nhân (PR #330).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) =>
  readFileSync(new URL(p, import.meta.url), "utf8")
    .replace(/\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");

test("ô tìm màn Đặt lịch hỏi máy chủ, đợi ngừng gõ, từ 2 ký tự", () => {
  const hub = doc("../app/(dashboard)/appointments/BookingHub.tsx");
  assert.match(hub, /\/api\/appointments\/tim-khach\?q=\$\{encodeURIComponent\(q\)\}/);
  assert.match(hub, /setTimeout\([\s\S]*?\},\s*300\)/, "debounce 300 ms");
  assert.match(hub, /clearTimeout\(hen\)/, "gõ tiếp phải huỷ lần hỏi cũ");
  assert.match(hub, /const TIM_TOI_THIEU = 2;/);
  // Kết quả chỉ hiện khi đúng chuỗi đang gõ — câu trả lời về muộn không đè.
  assert.match(hub, /ketQuaTim\?\.q === qTim/);
  // Danh sách hiện ra là kết quả máy chủ, không còn chỉ là lọc 200 khách.
  assert.match(hub, /danhSachKhach\.map\(/);
  assert.doesNotMatch(hub, /filteredPatients\.map\(/);
  // Khách chọn từ kết quả tìm (ngoài 200 khách) vẫn là khách đang chọn.
  assert.match(hub, /khachTuTim\[selectedPatientId\]/);
  assert.match(hub, /nhoKhachTuTim\(p\);\s*chonKhach\(p\.clinic_patient_id\)/);
  // Máy chủ hỏng phải nói ra, không im như "không có khách".
  assert.match(hub, /Không tìm được trên toàn bộ hồ sơ/);
});

test("route Next tim-khach chỉ chuyển tiếp", () => {
  const route = doc("../app/api/appointments/tim-khach/route.ts");
  assert.match(route, /proxyJsonToBackend\(\s*"GET",\s*`\/api\/v1\/appointments\/tim-khach\?/);
  assert.doesNotMatch(route, /supabase|createClient|from\(/i, "không chạm thẳng database");
});

test("máy chủ tìm bằng đúng hàm của Danh sách bệnh nhân, trên mọi hồ sơ", () => {
  const sv = doc("../../clinicai/services/man_dat_lich_doc.py");
  assert.match(
    sv,
    /from clinicai\.services\.danh_sach_benh_nhan_service import chuoi_tim, mau_so/,
  );
  const tim = sv.slice(sv.indexOf("_TIM_SQL = "));
  assert.match(tim, /p\.full_name_unaccent ILIKE/, "tìm tên không dấu");
  assert.match(tim, /p\.sdt_tim_kiem LIKE \$5/, "một phần SĐT qua cột gộp");
  assert.doesNotMatch(tim.slice(0, tim.indexOf('"""\n', 15)), /nguon_nhap/, "không giấu hồ sơ Notion");
  assert.match(sv, /TRAN_TIM = 20/);
});
