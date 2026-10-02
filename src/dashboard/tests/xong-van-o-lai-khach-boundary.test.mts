// BẤM XONG VẪN Ở LẠI KHÁCH ĐÓ + NÚT IN LUÔN CÓ (Tuyền 02/10/2026).
//
// Phòng khám báo: bấm Xong (hay Hoàn tất phiếu, Đã lấy mẫu…) thì khách sang nhóm
// "Đã xong" — đúng — nhưng khung bên phải nhảy sang khách chờ kế tiếp. Tải nhầm
// tệp là phải đi tìm lại khách trong "Đã xong", rất mệt. Gốc: khung chỉ ghim
// khách khi người dùng bấm dòng; khách tự chọn (mặc định) thì Xong xong đổi theo
// mặc định mới. Và nút In phiếu chỉ nằm trong phiếu kết quả — lấy mẫu, dịch vụ
// không phiếu, hay lúc phiếu chưa mở thì không có nút In.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const phong = doc("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
const banKham = doc("../app/(dashboard)/ban-kham/BanKham.tsx");

test("phòng dịch vụ + bàn khám ghim khách đang hiện (không tự nhảy khi Xong)", () => {
  const ghim = /if \(chon && chon\.id !== chonId\) setChonId\(chon\.id\);/;
  assert.match(phong, ghim, "PhongDichVu.tsx");
  assert.match(banKham, ghim, "BanKham.tsx");
});

test("khách đã xong có lối sang khách kế tiếp — bấm tay, không tự nhảy", () => {
  assert.match(phong, /chon\?\.trang_thai === "done"/);
  assert.match(phong, /Sang khách kế tiếp/);
});

test("nút In phiếu nằm ở đầu khung khách, ngoài mọi điều kiện trạng thái", () => {
  const dau = phong.indexOf('<div className="flex flex-wrap items-center gap-2">');
  const nutIn = phong.indexOf("<NutInPhieu href={`/print/ket-qua/${dong.ref_id}`}");
  const batDau = phong.indexOf("{chuaLam && th ? (", dau);
  assert.ok(dau > 0 && nutIn > dau, "NutInPhieu phải nằm trong hàng nút đầu khung");
  assert.ok(nutIn < batDau, "NutInPhieu đứng trước mọi nút có điều kiện");
});
