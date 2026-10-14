import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const MAN = "../app/(dashboard)/xuat-hoa-don/XuatHoaDon.tsx";
const LAN = "../app/(dashboard)/xuat-hoa-don/LanXuatMisa.tsx";

test("đánh dấu đã xuất MISA: route Next chỉ chuyển tiếp, kiểm mã lần xuất", () => {
  const goc = read("../app/api/xuat-hoa-don/misa/route.ts");
  assert.match(goc, /proxyJsonToBackend\("GET", "\/api\/v1\/hoa-don\/misa-xuat"/);
  assert.match(goc, /proxyJsonToBackend\("POST", "\/api\/v1\/hoa-don\/misa-xuat"/);
  const mot = read("../app/api/xuat-hoa-don/misa/[id]/route.ts");
  for (const m of ["GET", "DELETE", "PUT"]) {
    assert.match(mot, new RegExp(`export async function ${m}\\(`));
    assert.match(mot, new RegExp(`proxyJsonToBackend\\("${m}", \`/api/v1/hoa-don/misa-xuat/`));
  }
  assert.match(mot, /UUID_RE\.test\(id\)/);
});

test("màn xuất: nút đánh dấu gửi KHOẢNG NGÀY, không gửi danh sách hoá đơn", () => {
  const ui = read(MAN);
  assert.match(ui, /fetch\("\/api\/xuat-hoa-don\/misa", \{/);
  assert.match(ui, /JSON\.stringify\(\{ tu: khoang\.tu, den: khoang\.den/);
  // Danh sách hoá đơn do máy chủ dựng lại — trình duyệt không được gửi lên.
  assert.doesNotMatch(ui, /JSON\.stringify\(\{[^}]*hoa_don/);
  assert.match(ui, /Hoàn tác/);
  assert.doesNotMatch(ui, /window\.confirm|\.reduce\(/);
});

test("trạng thái MISA do máy chủ so: màn chỉ vẽ misa.co_thay_doi / ly_do", () => {
  const ui = read(MAN);
  assert.match(ui, /h\.misa\.co_thay_doi/);
  assert.match(ui, /h\.misa\.ly_do\.join/);
  // Không tự so tiền / công ty ở TSX.
  assert.doesNotMatch(ui, /dau_van_tay|dau_nguoi_mua|dau_noi_dung/);
  // "Có thay đổi" là việc kế toán cần làm, không phải lỗi: màu thông tin, không vàng/đỏ.
  assert.match(ui, /bg-info-bg[^"]*text-info">\s*\n?\s*Có thay đổi sau khi xuất/);
});

test("danh sách các lần xuất: xem thay đổi, bỏ đánh dấu và khôi phục (hoàn tác)", () => {
  const ui = read(LAN);
  assert.match(ui, /method: "DELETE"/);
  assert.match(ui, /"PUT"/);
  assert.match(ui, /Khôi phục/);
  assert.match(ui, /r\.status === 403/); // không có quyền kế toán → ẩn khối
  assert.doesNotMatch(ui, /window\.confirm|\.reduce\(/);
  assert.doesNotMatch(ui, /<button(?![^>]*type=)/);
});
