import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// Báo cáo hàng hoá → link "Xem bảng kiểm kê đầu – cuối ca" (Notion 16/10/2026):
// link phải tồn tại, mở ĐÚNG tab Kiểm kê ca (kèm ngày + ca đang xem), và chỉ hiện
// khi người xem mở được `/pharmacy/inventory` (cùng cửa trang đích — không link chết).

const doc = (p: string) => readFileSync(new URL(`../${p}`, import.meta.url), "utf8");

const BAO_CAO = "app/(dashboard)/reports/BaoCaoHangHoa.tsx";
const TRANG_BAO_CAO = "app/(dashboard)/reports/page.tsx";
const TRANG_KHO = "app/(dashboard)/pharmacy/inventory/page.tsx";
const KHO = "app/(dashboard)/pharmacy/inventory/KhoThuoc.tsx";
const KIEM_KE = "app/(dashboard)/pharmacy/inventory/KiemKeCa.tsx";

test("BangHangHoa/BaoCaoHangHoa: có link tới tab Kiểm kê ca của kho thuốc", () => {
  const s = doc(BAO_CAO);
  assert.match(s, /Xem bảng kiểm kê đầu – cuối ca/);
  assert.match(s, /href=\{`\/pharmacy\/inventory\?\$\{linkKiemKe\}`\}/);
  assert.match(s, /tab: "kiem-ke-ca"/);
  // mang theo ngày + ca đang xem, chỉ khi xem MỘT ngày
  assert.match(s, /\.\.\.\(motNgay \? \{ ngay: khoang\.tu \} : \{\}\)/);
  assert.match(s, /\.\.\.\(motNgay && ca \? \{ ca \} : \{\}\)/);
  // dùng thành phần có sẵn, không màu / cỡ tự chế
  assert.match(s, /buttonClass\("secondary", "sm"\)/);
});

test("link chỉ hiện khi có quyền mở màn kho và chỉ ở bảng Thuốc", () => {
  const s = doc(BAO_CAO);
  assert.match(s, /moKiemKe && loai === "thuoc"/);
  assert.match(s, /moKiemKe = false/);
  const t = doc(TRANG_BAO_CAO);
  assert.match(t, /await moDuocMan\("\/pharmacy\/inventory"\)/);
  assert.match(t, /moKiemKe=\{moKiemKe\}/);
});

test("/pharmacy/inventory đọc ?tab= ?ngay= ?ca= và truyền xuống, tham số lạ bị bỏ", () => {
  const p = doc(TRANG_KHO);
  assert.match(p, /searchParams/);
  assert.match(p, /NGAY_HOP_LE\.test\(ngay\)/);
  assert.match(p, /CA_HOP_LE\.find\(\(c\) => c === ca\)/);
  assert.match(p, /tabDau=\{tab\}/);
  const k = doc(KHO);
  assert.match(k, /useState<Tab>\(\(\) => tabTuUrl\(tabDau\)\)/);
  assert.match(k, /replace\(\/-\/g, "_"\)/); // kiem-ke-ca → kiem_ke_ca
  assert.match(k, /"kiem_ke_ca": "kiem_cuoi"/); // link cũ → tab Kiểm cuối ca (16/10)
  assert.match(k, /ngayDau=\{ngayKiemKe\} caDau=\{caKiemKe\}/);
});

test("KiemKeCa: ngày / ca từ link không bị 'ca hiện tại' của máy chủ đè", () => {
  const s = doc(KIEM_KE);
  assert.match(s, /useState\(\(\) => ngayDau \?\? homNayVn\(\)\)/);
  assert.match(s, /useState<Ca>\(caDau \?\? "SANG"\)/);
  assert.match(s, /if \(!giuCaDau\.current\) setCa\(n\.data\.ca\)/);
  // đổi ngày bằng tay thì trở về luật cũ (ca máy chủ nhắc)
  assert.match(s, /giuCaDau\.current = false/);
});
