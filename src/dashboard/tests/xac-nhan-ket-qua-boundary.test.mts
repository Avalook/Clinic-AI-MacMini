import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const ROOT = new URL("../", import.meta.url);
const read = (path: string) => readFileSync(new URL(path, ROOT), "utf8");

const xacNhanPageSource = read("app/(dashboard)/xac-nhan-ket-qua/page.tsx");
const tepKetQuaSource = read("app/(dashboard)/customers/TepKetQua.tsx");
const rolesSource = read("lib/roles.ts");
const navItemsSource = read("app/(dashboard)/nav-items.ts");
const emailDaGanSource = read("app/(dashboard)/ban-xet-nghiem/EmailDaGan.tsx");

test("12/11: màn 'Xác nhận kết quả đối tác' ĐÃ BỎ — không còn trên thanh bên, không quyền riêng", () => {
  // Tuyền 12/11/2026: tờ đối tác máy nhận Hợp lệ ngay; nhân viên theo dõi + gán / gán lại
  // ở Việc của đối tác. Không được thêm lại mục / màn hàng chờ.
  assert.equal(navItemsSource.indexOf('href: "/xac-nhan-ket-qua"'), -1);
  assert.equal(navItemsSource.indexOf('"/xac-nhan-ket-qua"'), -1);
  assert.doesNotMatch(rolesSource, /"\/xac-nhan-ket-qua"/);
  assert.equal(navItemsSource.indexOf('href: "/duyet-ket-qua"'), -1);
  assert.equal(
    existsSync(new URL("app/(dashboard)/xac-nhan-ket-qua/HangChoXacNhanKetQua.tsx", ROOT)),
    false,
    "Màn hàng chờ cũ phải đã xoá",
  );
});

test("link cũ /xac-nhan-ket-qua chuyển hướng về Việc của đối tác", () => {
  assert.match(xacNhanPageSource, /redirect\("\/ban-xet-nghiem"\)/);
});

test("sửa tờ gắn nhầm / chưa có chỉ định nằm ở 'Thư email đã gán' (Việc của đối tác)", () => {
  assert.match(emailDaGanSource, /from "\.\/ChuyenVaoChiDinh"/);
  assert.match(emailDaGanSource, /Gán lại cho khách khác/);
});

test("hồ sơ khách TepKetQua.tsx: vẫn hiện badge Chờ xác nhận (khi phòng khám bật lại cờ)", () => {
  assert.match(
    tepKetQuaSource,
    /t\.xac_nhan_trang_thai === "CHO_XAC_NHAN"/,
    "TepKetQua.tsx chưa kiểm tra xac_nhan_trang_thai === 'CHO_XAC_NHAN'",
  );
  assert.match(
    tepKetQuaSource,
    /Chờ xác nhận đúng người\/chỉ định/,
    "TepKetQua.tsx thiếu badge 'Chờ xác nhận đúng người/chỉ định'",
  );
});
