import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// LUỒNG ĐỐI TÁC CHUNG (Tuyền 16/10/2026).
//
//   1. Tài khoản đối tác: thanh bên CHỈ "Việc của đối tác" — bấm thử staging thấy
//      cả "Trang chủ" và "Kế toán" (/ke-toan không có dòng NAV_ROLES nên luật gốc
//      mở cho mọi vai khi `quyen` null — mà đối tác luôn null).
//   2. Bàn /doi-tac: không còn dòng tóm tắt, không "Lấy mẫu", không "Có mẫu ·
//      chờ nhận"; chỉ hai chữ riêng của đối tác.
//   3. Phòng đối tác ở /phong: nút cuối "Đã nhận mẫu" gọi CÙNG lệnh với bàn.

import { canSeeNav, canSeeNavGoc, hienTrenThanhBen, vaoDuocMan } from "../lib/roles.ts";

test("đối tác: thanh bên chỉ /doi-tac — không Trang chủ, không Kế toán", () => {
  assert.equal(hienTrenThanhBen("PARTNER", "/doi-tac", null), true);
  for (const href of ["/home", "/ke-toan", "/hanh-trinh", "/phong", "/reports", "/customers"]) {
    assert.equal(hienTrenThanhBen("PARTNER", href, null), false, href);
    assert.equal(canSeeNav("PARTNER", href), false, href);
    assert.equal(canSeeNavGoc("PARTNER", href), false, href);
    assert.equal(vaoDuocMan(href, ["PARTNER"], null), false, href);
  }
  assert.equal(vaoDuocMan("/doi-tac", ["PARTNER"], null), true);
});

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("bàn /doi-tac theo luồng mới — không Lấy mẫu, không dòng tóm tắt", () => {
  const bang = doc("../app/doi-tac/BangDoiTac.tsx");
  assert.ok(!bang.includes("/api/doi-tac/da-lay-mau"), "bỏ nút Đã lấy mẫu");
  assert.ok(!bang.includes("Có mẫu · chờ nhận"));
  assert.ok(!bang.includes("chờ lấy\n          mẫu"), "bỏ dòng tóm tắt");
  assert.ok(bang.includes("KhoiViecDoiTac"), "phiếu + Trả kết quả (khối chung)");
  assert.ok(bang.includes("/api/doi-tac/phieu"), "đối tác điền phiếu qua cửa đối tác");
  const khoi = doc("../app/(dashboard)/_lam-viec/KhoiDoiTac.tsx");
  assert.ok(khoi.includes('"Đã nhận mẫu · chờ kết quả"'));
  assert.ok(khoi.includes('"Có kết quả"'));
  assert.ok(!khoi.includes("tham khảo"), "bỏ dòng Thu hộ đối tác · tham khảo");
  assert.ok(!khoi.includes("Chưa thu hộ"), "bỏ chip Chưa thu hộ");
});

test("phòng đối tác: Đã nhận mẫu = cùng lệnh bàn đối tác", () => {
  const phong = doc("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
  assert.ok(phong.includes('DOI_TAC: "Đã nhận mẫu"'));
  assert.ok(phong.includes("/api/doi-tac/cho-tai-lieu"));
  assert.ok(phong.includes("la_doi_tac"));
});

// 16/10/2026 (Tuyền: "bê form sang, sao để mỗi chỗ một kiểu, sửa khó hơn"):
// /doi-tac DÙNG LẠI thành phần của phòng dịch vụ — không tự vẽ thẻ.
test("bàn /doi-tac dùng CHUNG thẻ khách, thẻ dịch vụ, ô tệp, ô tìm với phòng", () => {
  const bang = doc("../app/doi-tac/BangDoiTac.tsx");
  const phong = doc("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
  const hang = doc("../app/(dashboard)/phong/[ma]/HangChoKhachPhong.tsx");
  for (const [ten, nguon] of [
    ["TheKhachHangCho", "_lam-viec/TheKhachHangCho"],
    ["NhomHangCho", "_lam-viec/TheKhachHangCho"],
    ["TheDichVu", "_lam-viec/TheDichVu"],
    ["KhungTep", "_lam-viec/KhungTep"],
    ["KhoiViecDoiTac", "_lam-viec/KhoiDoiTac"],
    ["OTimKhach", "components/ui/OTimKhach"],
    ["ThongBaoHoanTac", "components/ui/ThongBaoHoanTac"],
  ]) {
    assert.ok(bang.includes(`<${ten}`), `/doi-tac vẽ bằng ${ten}`);
    assert.ok(bang.includes(nguon), `/doi-tac nhập ${ten} từ ${nguon}`);
  }
  // Phòng dịch vụ gọi đúng những thành phần ấy — sửa một chỗ, cả hai đổi.
  assert.ok(hang.includes("<TheKhachHangCho") && hang.includes("<NhomHangCho"));
  assert.ok(phong.includes("<TheDichVu") && phong.includes("<KhoiViecDoiTac") && phong.includes("<OTimKhach"));
  // Không tự vẽ thẻ / nút riêng như bản cũ.
  assert.ok(!bang.includes("<button"), "không <button> tự vẽ — nút nằm trong thành phần chung");
  assert.ok(!bang.includes("function MotViec"), "bỏ thẻ việc tự vẽ");
  assert.ok(!bang.includes("<textarea"), "ghi chú nhận mẫu nằm trong khối chung");
  assert.ok(!bang.includes("guiTepCoTienDo"), "tải tệp qua KhungTep (cửa đối tác)");
  // Dòng thông báo cố định trên đầu (giữ câu cũ sau bước khác) → thông báo như phòng.
  assert.ok(!bang.includes("setXong("), "bỏ dòng thông báo xanh cố định");
});

test("ô tệp: cửa đối tác tải qua /api/doi-tac, không xem trước khi máy chủ không cho", () => {
  const tep = doc("../app/(dashboard)/_lam-viec/KhungTep.tsx");
  assert.ok(tep.includes('laDoiTac ? "/api/doi-tac" : "/api/cskh/ket-qua"'));
  assert.ok(tep.includes("coTep && xemDuoc"), "thumbnail chỉ khi được mở tệp");
});

test("phòng đối tác: nút của dòng chỉ định là 'Đã nhận mẫu', không bày nút kết thúc thứ hai", () => {
  const phong = doc("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
  const khung = doc("../app/(dashboard)/phong/[ma]/KhungChiDinhKhach.tsx");
  assert.ok(phong.includes("nhanXong={phong.la_doi_tac === true ? NUT_XONG.DOI_TAC : undefined}"));
  assert.ok(khung.includes('h.hanh === "bat-dau" ? "Bắt đầu" : nhanXong'));
  assert.ok(phong.includes('loai === "DOI_TAC" && coNutTrenDong ? null'));
});

test("khối đối tác: tiến độ chỉ tô đoạn đã tới; thu hộ một quy tắc điền sẵn", () => {
  const khoi = doc("../app/(dashboard)/_lam-viec/KhoiDoiTac.tsx");
  assert.ok(khoi.includes('b.toi ? "bg-success" : "bg-line"'), "không tô màu 'bước đang ở'");
  assert.ok(!khoi.includes("bg-brand-500"), "chưa nhận mẫu thì đoạn nhận mẫu chưa tô");
  assert.ok(khoi.includes("viec.gia_tham_khao != null && viec.gia_tham_khao > 0"));
  const bang = doc("../app/doi-tac/BangDoiTac.tsx");
  assert.ok(!bang.includes("BUOC"), "thanh tiến độ tự vẽ cũ đã bỏ");
});
