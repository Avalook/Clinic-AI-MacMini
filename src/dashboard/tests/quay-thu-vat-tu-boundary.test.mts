import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { TOI_DA_KET_QUA, timVatTu, type VatTuMuc } from "../lib/vat-tu.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");
const quay = read("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
const vatTu = read("../app/(dashboard)/thu-ngan/VatTuQuay.tsx");
const bangGia = read("../app/(dashboard)/cashier/VatTuBangGia.tsx");
const thuocTinh = read("../app/(dashboard)/cashier/VatTuThuocTinh.tsx");
const suaGia = read("../app/api/service-price/route.ts");
const danhMuc = read("../app/(dashboard)/cashier/DanhMucDichVuPhong.tsx");
const proxy = read("../app/api/luot-kham/route.ts");

const muc = (ten: string, extra: Partial<VatTuMuc> = {}): VatTuMuc => ({
  id: ten,
  ten,
  don_vi: "cái",
  don_gia: 1000,
  ban_duoc: true,
  ly_do_khong_ban: null,
  can_ql_duyet: false,
  chon_nhanh: false,
  goi_y: false,
  ...extra,
});

test("tìm vật tư: gõ không dấu, không phân hoa thường, nhiều từ", () => {
  const ds = [
    muc("Đầu dò Bio 1 lần"),
    muc("Đầu dò Bio nhiều lần"),
    muc("Vòng nội tiết tránh thai Mirena"),
    muc("Gạc củ ấu"),
  ];
  assert.deepEqual(
    timVatTu(ds, "dau do").map((m) => m.ten),
    ["Đầu dò Bio 1 lần", "Đầu dò Bio nhiều lần"],
  );
  assert.deepEqual(
    timVatTu(ds, "MIRENA").map((m) => m.ten),
    ["Vòng nội tiết tránh thai Mirena"],
  );
  assert.deepEqual(
    timVatTu(ds, "bio nhieu").map((m) => m.ten),
    ["Đầu dò Bio nhiều lần"],
  );
  assert.deepEqual(timVatTu(ds, "   "), []);
  assert.deepEqual(timVatTu(ds, "khong co"), []);
});

test("tìm vật tư: giữ thứ tự máy chủ và cắt ở trần", () => {
  const ds = Array.from({ length: 20 }, (_, i) => muc(`Gạc ${i}`));
  const kq = timVatTu(ds, "gac");
  assert.equal(kq.length, TOI_DA_KET_QUA);
  assert.equal(kq[0].ten, "Gạc 0");
});

test("khối Mua thêm vật tư chỉ ở quầy dịch vụ, không ở quầy thuốc", () => {
  assert.match(quay, /import VatTuQuay from "\.\/VatTuQuay"/);
  assert.match(quay, /quay !== "thuoc" && !daThuCua\(l\.visit_id, "dich_vu"\) \? \(\s*<VatTuQuay/);
  assert.match(quay, /"luot_vat_tu"/);
});

test("khối vật tư dùng thành phần chung, không tự vẽ nút / màu / style", () => {
  for (const nguon of [vatTu, bangGia, thuocTinh]) {
    assert.doesNotMatch(nguon, /<button/);
    assert.doesNotMatch(nguon, /style=\{\{/);
    assert.doesNotMatch(nguon, /#[0-9a-fA-F]{3,8}\b/);
    assert.doesNotMatch(nguon, /window\.confirm/);
  }
  assert.match(vatTu, /import Button from "@\/components\/ui\/Button"/);
  // Hai đầu dò là nút chọn nhanh, máy chủ quyết nút nào nổi lên đầu (`goi_y`).
  assert.match(vatTu, /const nhanh = goi\.danh_muc\.filter\([\s\S]*m\.chon_nhanh && \(!m\.can_ql_duyet \|\| goi\.la_quan_ly\)/);
  assert.match(vatTu, /timVatTu\(goi\.danh_muc, tim\)\.filter\([\s\S]*!m\.can_ql_duyet \|\| goi\.la_quan_ly/);
  assert.match(vatTu, /timVatTu\(goi\.danh_muc, tim\)\.filter\([\s\S]*!m\.can_ql_duyet \|\| goi\.la_quan_ly/);
  assert.match(vatTu, /m\.goi_y \? "soft" : "secondary"/);
  // Hàng cần duyệt chỉ hiện thao tác cho Quản lý đang đăng nhập.
  assert.match(vatTu, /if \(m\.can_ql_duyet\)/);
  assert.match(vatTu, /if \(!goi\?\.la_quan_ly\) return/);
  assert.match(vatTu, /m\.ban_duoc && \(!m\.can_ql_duyet \|\| goi\.la_quan_ly\)/);
  assert.match(vatTu, /const khoaTheoQuanLy = d\.can_ql_duyet && !goi\.la_quan_ly/);
  assert.doesNotMatch(vatTu, /duyet\.quanLy|goi\.quan_ly|Người đã duyệt/);
  assert.match(vatTu, /ly_do_duyet: duyet\.lyDo/);
});

test("thuộc tính vật tư có đường gửi cho mọi cột, giữ false/null/rỗng", () => {
  assert.match(bangGia, /<VatTuThuocTinh d=\{d\}/);
  for (const cot of ["loai_vat_tu", "gia_nhap", "don_vi", "ma_vach", "kinh_doanh",
    "can_duyet_nhap", "can_ql_duyet", "chon_nhanh"]) {
    assert.ok(thuocTinh.includes(`"${cot}"`), `ô ${cot}`);
    assert.ok(suaGia.includes(`"${cot}"`), `proxy ${cot}`);
  }
  assert.match(suaGia, /filter\(\(key\) => key in body\)/);
  assert.match(thuocTinh, /onSua\(d\.id, patch,/);
  assert.match(thuocTinh, /await onSua[\s\S]*setPatch\(\{\}\)/);
});

test("proxy chỉ cho đúng ba lệnh vật tư + một đường đọc", () => {
  assert.match(proxy, /"vat-tu-them": \(id\) => `\/api\/v1\/luot-kham\/visits\/\$\{id\}\/vat-tu`/);
  assert.match(proxy, /"vat-tu-so-luong": \(id\) => `\/api\/v1\/luot-kham\/vat-tu\/\$\{id\}`/);
  assert.match(proxy, /"vat-tu-bo": \(id\) => `\/api\/v1\/luot-kham\/vat-tu\/\$\{id\}\/bo`/);
  assert.match(proxy, /xem === "vat-tu"/);
});

test("Bảng giá: vật tư là phần riêng, không cột phòng / nhóm việc", () => {
  assert.match(danhMuc, /<VatTuBangGia/);
  assert.doesNotMatch(bangGia, /Chưa có phòng|Phòng làm|chua_co_phong|node_code/);
  assert.match(bangGia, /unit_price/);
  assert.match(bangGia, /active: !d\.active/);
});
