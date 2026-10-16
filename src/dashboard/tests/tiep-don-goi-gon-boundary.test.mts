// Màn Tiếp đón chỉ cần BẢNG LỊCH HẸN TUẦN — không được kéo cả gói Trang chủ.
//
// Đo 16/10/2026 (DB thử ~9.000 khách / 36.000 lịch): `/home/bang-dieu-khien`
// ~1,15s, trong đó màn Tiếp đón chỉ dùng `tuan_hen` + `truc_ca` + `tien_trinh`.
// Lỗi lùi kiểu này KHÔNG có triệu chứng chức năng — gọi lại cả gói thì màn vẫn
// đúng, chỉ chậm đi gấp ~4 lần — nên phải có bài canh.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const page = readFileSync(
  new URL("../app/(dashboard)/reception/queue/page.tsx", import.meta.url),
  "utf8",
);
const kieu = readFileSync(
  new URL("../app/(dashboard)/home/lich-hen-ngay.ts", import.meta.url),
  "utf8",
);

test("màn Tiếp đón gọi gói gọn lich-hen-tuan, không gọi bang-dieu-khien", () => {
  assert.match(
    page,
    /\/api\/v1\/home\/lich-hen-tuan\?week_appt=/,
    "phải gọi gói gọn của bảng lịch hẹn",
  );
  assert.ok(
    !page.includes("bang-dieu-khien"),
    "không kéo cả gói Trang chủ — màn này chỉ dùng bảng lịch hẹn tuần",
  );
});

test("kiểu GoiLichHen chỉ đòi đúng ba khối gói gọn trả về", () => {
  const khoi = kieu.match(/export interface GoiLichHen \{([\s\S]*?)\n\}/);
  assert.ok(khoi, "không tìm thấy interface GoiLichHen");
  const cacKhoa = [...khoi[1].matchAll(/^\s*(\w+)\??:/gm)].map((m) => m[1]).sort();
  assert.deepEqual(
    cacKhoa,
    ["tien_trinh", "truc_ca", "tuan_hen"],
    "thêm khối vào GoiLichHen thì gói gọn phía máy chủ (goi_lich_hen_tuan) phải trả khối ấy",
  );
});

test("các lời gọi của trang vẫn chạy song song một vòng Promise.all", () => {
  const tp = page.match(/await Promise\.all\(\[([\s\S]*?)\]\);/);
  assert.ok(tp, "trang phải gom các lời gọi vào Promise.all");
  assert.match(tp[1], /reception\/danh-sach/);
  assert.match(tp[1], /lich-hen-tuan/);
});
