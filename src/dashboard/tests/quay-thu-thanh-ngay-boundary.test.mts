import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const tab = read("../app/(dashboard)/thu-ngan/TabThuNgan.tsx");
const quay = read("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
const giaoDich = read("../app/(dashboard)/thu-ngan/GiaoDich.tsx");
const lichSu = read("../app/(dashboard)/thu-ngan/LichSuThu.tsx");
const proxy = read("../app/api/cashier/route.ts");

test("thanh ngày dùng chung (ThanhNgay một ngày) cho cả ba tab, ngày ở URL", () => {
  assert.match(tab, /from "@\/components\/ui\/ThanhNgay"/);
  assert.match(tab, /<ThanhNgay\s+motNgay/);
  // Ngày nằm trên URL qua hook dùng chung với phòng dịch vụ / Bàn khám.
  assert.match(tab, /useNgayXem\(\)/);
  assert.match(tab, /<QuayThuNgan quay=\{quay\} ngay=\{ngay\} \/>/);
  assert.match(tab, /<LichSuThu key=\{ngay\} ngay=\{ngay\} \/>/);
  assert.match(tab, /<GiaoDich key=\{`\$\{tab\}:\$\{ngay\}`\} lichSu=\{tab === "lich_su"\} quay=\{quay\} ngay=\{ngay\} \/>/);
  assert.match(tab, /Đã thanh toán ngày \$\{ngayNgan\(ngay\)\}/);
});

test("ngày đi tới máy chủ: bảng thu, sổ giao dịch, lịch sử — không tự cắt ngày ở TSX", () => {
  assert.match(quay, /&ngay=\$\{ngay\}/);
  assert.match(quay, /\[quay, ngay\]/);
  assert.match(giaoDich, /ngay \?\? homNay\(\)/);
  assert.match(lichSu, /ngay \?\? todayVn\(\)/);
  assert.match(proxy, /\$\{duoiNgay\}/);
  assert.match(proxy, /NGAY_RE\.test\(ngay\)/);
});
