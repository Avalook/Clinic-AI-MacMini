import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const dauDo = read("../app/(dashboard)/_lam-viec/phieu-kham/DauDoChiDinh.tsx");
const ketQua = read("../app/(dashboard)/_lam-viec/phieu-kham/KetQuaChiDinh.tsx");
const phieuLuot = read("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
const phieu = read("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKham.tsx");
const vatTuQuay = read("../app/(dashboard)/thu-ngan/VatTuQuay.tsx");
const proxy = read("../app/api/luot-kham/route.ts");

test("đầu dò theo chỉ định: chọn MỘT (radio), dùng thành phần chung, không tự chế giao diện", () => {
  assert.doesNotMatch(dauDo, /<button/);
  assert.doesNotMatch(dauDo, /style=\{\{/);
  assert.doesNotMatch(dauDo, /#[0-9a-fA-F]{3,8}\b/);
  assert.doesNotMatch(dauDo, /window\.confirm/);
  assert.match(dauDo, /import ChipChon from "@\/components\/ui\/ChipChon"/);
  assert.match(dauDo, /role="radiogroup"/);
  // "Không dùng đầu dò" là một lựa chọn thật (bỏ chọn = gửi service_price_id null).
  assert.match(dauDo, /Không dùng đầu dò/);
  assert.match(dauDo, /service_price_id: servicePriceId/);
  // Đã thu → khoá, nói cách đổi; việc bình thường dùng chữ trung tính, không vàng/đỏ.
  assert.match(dauDo, /da_thu/);
  assert.match(dauDo, /Hoàn tác lần thu/);
  assert.doesNotMatch(dauDo, /tone="(warning|danger)"/);
});

test("đầu dò theo chỉ định: máy chủ quyết, màn nghe sự kiện và gắn vào thẻ CLS", () => {
  // Nghe bảng đầu dò + chỉ định: quầy bỏ / bỏ chỉ định thì cập nhật liền.
  assert.match(dauDo, /useNgheBang\(\["luot_vat_tu", "service_order"\]/);
  assert.match(dauDo, /guiThaoTac\("dau-do-chon", orderId/);
  assert.match(dauDo, /docBang<DauDoChiDinhGoi>\("dau-do"/);
  // Chỉ vẽ cho đúng chỉ định đang hiện, không ở thẻ điều trị / lần cũ chỉ xem.
  assert.match(ketQua, /dauDoLuot && !dieuTri && !chiXem/);
  assert.match(ketQua, /orderIds=\{dsHien\.map/);
  // Cả hai lối vào phiếu (hồ sơ tối giản + phiếu đầy đủ) truyền cùng một thuộc tính.
  assert.match(phieuLuot, /dauDoLuot: visitId/);
  assert.match(phieu, /dauDoLuot\?: string/);
});

test("proxy: thao tác dau-do-chon và bảng đọc dau-do đều đi qua danh sách trắng", () => {
  assert.match(proxy, /"dau-do-chon": \(id\) => `\/api\/v1\/luot-kham\/orders\/\$\{id\}\/dau-do`/);
  assert.match(proxy, /xem === "dau-do"/);
  assert.match(proxy, /\/api\/v1\/luot-kham\/visits\/\$\{luot\}\/dau-do/);
});

test("quầy thu: dòng đầu dò của chỉ định hiện nguồn, bỏ thì BẮT ghi lý do", () => {
  assert.match(vatTuQuay, /Bác sĩ chọn ở chỉ định/);
  assert.match(vatTuQuay, /d\.order_id \? setBoMo\(\{ id: d\.id, lyDo: "" \}\)/);
  assert.match(vatTuQuay, /gui\("vat-tu-bo", d\.id, \{ ly_do: boMo\.lyDo\.trim\(\) \}\)/);
  // Nút xác nhận khoá tới khi lý do đủ 5 ký tự (máy chủ vẫn ép lại).
  assert.match(vatTuQuay, /boMo\.lyDo\.trim\(\)\.length < 5/);
  // Dòng quầy tự thêm bỏ như cũ — không đòi lý do.
  assert.match(vatTuQuay, /void gui\("vat-tu-bo", d\.id, \{\}\)/);
});
