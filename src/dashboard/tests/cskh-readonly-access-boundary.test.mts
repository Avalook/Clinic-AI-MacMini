import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  canOperateCustomerCare,
  canSeeNav,
  hienTrenThanhBen,
} from "../lib/roles.ts";

const read = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf8");

const page = read("../app/(dashboard)/customers/page.tsx");
const view = read("../app/(dashboard)/customers/CustomersView.tsx");
const phanHoi = read("../app/(dashboard)/customers/PhanHoiKhach.tsx");
const tep = read("../app/(dashboard)/customers/TepKetQua.tsx");
const tepProxy = read(
  "../app/api/cskh/ket-qua/[tepId]/noi-dung/route.ts",
);

test("thu ngân được xem customers nhưng không có capability ghi CSKH", () => {
  for (const role of ["CASHIER", "CASHIER_THUOC", "CASHIER_DV"] as const) {
    assert.equal(canSeeNav(role, "/customers"), true);
    assert.equal(canOperateCustomerCare(role), false);
  }
  assert.equal(canOperateCustomerCare("CSKH"), true);
  assert.equal(canOperateCustomerCare("RECEPTION"), true);
  assert.equal(canOperateCustomerCare("MANAGEMENT"), true);
  assert.equal(canOperateCustomerCare("TRUONG_CA"), true);
});

test("trưởng ca có cùng đường vào customers với backend", () => {
  assert.equal(canSeeNav("TRUONG_CA", "/customers"), true);
  assert.equal(hienTrenThanhBen("TRUONG_CA", "/customers"), true);
});

test("customers dựng vùng ghi chỉ khi có capability và giữ vùng chỉ đọc", () => {
  assert.match(page, /const canOperateCskh = canOperateCustomerCare\(role\)/);
  assert.match(page, /canOperateCskh=\{canOperateCskh\}/);
  assert.match(
    view,
    /canOperateCskh && selected[\s\S]{0,180}<VungLamViecKhach/,
    "VungLamViecKhach chứa POST controls không được mount cho vai chỉ đọc",
  );
  assert.match(
    view,
    /!canOperateCskh && selected[\s\S]{0,900}<PhanHoiKhach[\s\S]{0,400}readOnly/,
    "vai chỉ đọc vẫn cần xem lịch sử/phản hồi, nhưng component phải ở read-only mode",
  );
  assert.match(
    view,
    /!canOperateCskh && selected[\s\S]{0,1200}<TepKetQua[\s\S]{0,400}readOnly/,
    "vai chỉ đọc vẫn được xem tệp đúng lượt mà không có nút upload/send",
  );
  assert.match(
    view,
    /canOperateCskh && \(\s*<div[\s\S]{0,3000}<HanhDongTrangThai/,
    "khối thao tác POST ở cột phải phải bị loại khỏi cây render của thu ngân",
  );
  assert.match(view, /canManage && editOpen && selected/);
  assert.match(view, /canEdit && datLich && selected/);
  assert.match(
    view,
    /canManage \? \(\s*<button[\s\S]{0,350}setXemTrung/,
    "cảnh báo lịch trùng chỉ mở control huỷ lịch cho vai quản lý lịch",
  );
  assert.match(view, /canManage && xemTrung/);

  const historyBuilder = page.slice(
    page.indexOf("const lichSuKhamByPatient"),
    page.indexOf("const lichSuKhamByPatient") + 250,
  );
  assert.match(
    historyBuilder,
    /if \(rows\.length\)/,
    "quyền sửa lịch không được dùng để cắt dữ liệu lịch sử của vai chỉ đọc",
  );
  // 22/08/2026 (Lát 2): hai nhánh select theo vai (đầy đủ / rút gọn) không còn
  // — backend trả MỘT bộ trường đủ cho mọi vai (trim theo vai trước đây chỉ để
  // nhẹ payload, không phải quyền; RLS/route mới là chốt). Tiền đề còn lại:
  // vai chỉ đọc vẫn phải có TÊN DỊCH VỤ — tức câu SQL backend phải join lấy nó
  // và lồng thành `service:{name}` như PostgREST cũ.
  const goiService = readFileSync(
    new URL(
      "../../clinicai/services/man_khach_hang_service.py",
      import.meta.url,
    ),
    "utf8",
  );
  assert.match(
    goiService,
    /st\.name AS ten_dich_vu/,
    "nhánh lịch chỉ đọc vẫn cần tên dịch vụ để hiển thị đúng lượt khám",
  );
  assert.match(
    goiService,
    /d\["service"\] = \{"name": ten_dv\}/,
    "tên dịch vụ phải được lồng thành service:{name} như hình PostgREST cũ",
  );
});

test("feedback và tệp chỉ hiển thị dữ liệu khi readOnly", () => {
  assert.match(phanHoi, /readOnly = false/);
  assert.match(phanHoi, /!readOnly && \([\s\S]{0,300}\+ Ghi phản hồi/);
  assert.match(
    phanHoi,
    /!readOnly && p\.trang_thai !== "DA_XU_LY"/,
    "update/close feedback không được render ở chế độ chỉ đọc",
  );

  assert.match(tep, /readOnly = false/);
  assert.match(
    tep,
    /!readOnly && \([\s\S]{0,700}\+ Tải ảnh \/ phiếu/,
    "upload control không được render ở chế độ chỉ đọc",
  );
  assert.match(
    tep,
    /!readOnly && !t\.gui_luc/,
    "send confirmation controls không được render ở chế độ chỉ đọc",
  );
  assert.match(
    tep,
    /readOnly \? \(\s*<span[\s\S]{0,300}t\.ten_hien_thi[\s\S]{0,200}: \(\s*<button/,
    "backend không cho Thu ngân đọc nội dung tệp, nên tên tệp chỉ đọc không được là nút hỏng",
  );
});

test("proxy nội dung PHI không cho trình duyệt cache sau khi đổi tài khoản", () => {
  assert.match(tepProxy, /"Cache-Control": "private, no-store"/);
  assert.doesNotMatch(tepProxy, /max-age\s*=\s*300/);
});
