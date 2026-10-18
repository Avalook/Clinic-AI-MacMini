import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (path: string) =>
  readFileSync(new URL(`../${path}`, import.meta.url), "utf8");

const markedCopy = [
  ["bàn tư vấn", "app/(dashboard)/ban-kham/BanKham.tsx", /Hàng tư vấn chung/],
  ["hành trình khách", "app/(dashboard)/hanh-trinh/BangHanhTrinh.tsx", />\s*Tải lại\s*</],
  ["thu ngân dịch vụ", "app/(dashboard)/thu-ngan/dich-vu/page.tsx", /Khách đã khám xong, chờ trả tiền dịch vụ\./],
  ["thu ngân thuốc", "app/(dashboard)/thu-ngan/thuoc/page.tsx", /Khách có đơn thuốc, chờ trả tiền thuốc\./],
  ["lịch sử hai quầy thu", "app/(dashboard)/thu-ngan/TabThuNgan.tsx", /Chỉ xem lịch sử ca đã trực\./],
  ["bảng giá dịch vụ", "app/(dashboard)/cashier/dich-vu/page.tsx", /Mọi dịch vụ phòng khám bán:/],
  ["báo cáo vận hành", "app/(dashboard)/reports/page.tsx", /KPI vận hành phòng khám ·/],
  ["xuất hoá đơn", "app/(dashboard)/xuat-hoa-don/page.tsx", /File Excel đúng mẫu nhập hoá đơn GTGT/],
  ["kế toán", "app/(dashboard)/ke-toan/page.tsx", /Thống kê theo hàng hoá trong kỳ/],
  ["lịch đổ về", "app/(dashboard)/lich-do-ve/page.tsx", /Toàn bộ lịch hẹn của tuần, thống kê theo mốc khung giờ · chỉ đọc/],
] as const;

for (const [screen, path, copy] of markedCopy) {
  test(`${screen} bỏ dòng chữ được đánh dấu`, () => {
    assert.doesNotMatch(doc(path), copy);
  });
}
