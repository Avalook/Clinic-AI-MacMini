// Cột + bộ lọc "Phản hồi thuốc" ở bảng Danh sách khách hàng, và dòng "Phản hồi
// thuốc gần nhất" ở đầu khung khách (16/10/2026).
//
// Tuyền: "phản hồi chỉ hiện trong khung chi tiết, chưa hiện thành một cột trong
// bảng danh sách khách — cho ra chỗ dễ nhìn thì tốt".
//
// Lỗi kiểu này không có triệu chứng ồn ào: xoá một dòng props là cột biến mất mà
// màn vẫn dựng được. Test khoá các mắt xích: máy chủ trả khối `phan_hoi_thuoc` →
// page.tsx dựng map theo khách → CustomersView vẽ cột + bộ lọc → khung khách vẽ
// dòng tóm tắt. Và luật "chữ trung tính" (không đỏ/vàng báo động).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");
const page = doc("../app/(dashboard)/customers/page.tsx");
const view = doc("../app/(dashboard)/customers/CustomersView.tsx");
const cot = doc("../app/(dashboard)/customers/PhanHoiThuocCot.tsx");
const khung = doc("../app/(dashboard)/_lam-viec/KhungKhach.tsx");
const khoiThuoc = doc("../app/(dashboard)/_lam-viec/PhanHoiThuocKhach.tsx");

test("page.tsx đọc khối phan_hoi_thuoc từ GÓI man-khach-hang, không mở vòng mới", () => {
  assert.match(page, /phan_hoi_thuoc\?: unknown\[\]/);
  assert.match(page, /khoi\("phan_hoi_thuoc"\)/);
  // Vẫn đúng MỘT lời gọi gói (goi-man-khach-boundary canh số lời gọi).
  assert.equal((page.match(/man-khach-hang\?ids=/g) ?? []).length, 1);
  assert.ok(!page.includes('.from("tuong_tac_cskh")'), "không đọc sổ chăm sóc qua PostgREST");
  assert.match(page, /phanHoiThuocByPatient=\{phanHoiThuocByPatient\}/);
});

test("bảng có cột 'Phản hồi thuốc' — tiêu đề và ô cùng số cột lưới", () => {
  assert.match(view, /<span>Phản hồi thuốc<\/span>/);
  assert.match(view, /<PhanHoiThuocCot/);
  // Lưới tiêu đề và lưới dòng PHẢI cùng số cột (9) — lệch là cột trượt sai chỗ.
  const luoi = view.match(/md:grid-cols-\[[^\]]+\]/g) ?? [];
  assert.equal(luoi.length, 2, "lưới tiêu đề + lưới dòng");
  assert.equal(luoi[0], luoi[1], "hai lưới phải GIỐNG HỆT nhau");
  assert.equal(luoi[0].split("_").length, 9, "9 cột sau khi thêm Phản hồi thuốc");
});

test("khách chưa có phản hồi → ô trống, không chữ 'không có'", () => {
  assert.match(cot, /if \(!tt \|\| tt\.so_phan_hoi < 1\) return null;/);
  assert.ok(!/không có|chưa có/i.test(cot.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "")), "ô trống không chữ");
  // Điện thoại: ô trống ẩn hẳn, ô có dữ liệu hiện.
  assert.match(view, /"hidden md:block"/);
});

test("ô hiện số phản hồi + ngày gần nhất + rút gọn + tooltip đủ nội dung", () => {
  assert.match(cot, /so_phan_hoi\} phản hồi/);
  assert.match(cot, /fmtDate\(tt\.luc\)/);
  assert.match(cot, /tt\.tom_tat/);
  assert.match(cot, /title=\{tieuDe\}/);
  // Rút gọn do MÁY CHỦ làm (không luật trong TSX): ở đây không có slice/substring.
  assert.ok(!/\.slice\(|\.substring\(|\.substr\(/.test(cot), "rút gọn ở backend");
});

test("chữ trung tính — không đỏ/vàng báo động", () => {
  for (const [ten, nguon] of [["cột", cot]] as const) {
    assert.ok(
      !/danger|warning|text-red|text-amber|text-yellow|bg-red|bg-amber/.test(nguon),
      `${ten} phản hồi thuốc không được dùng sắc báo động`,
    );
  }
  assert.match(cot, /tone="neutral"/);
  const dong = khung.slice(khung.indexOf("function DongPhanHoiGanNhat"), khung.indexOf("function Trong("));
  assert.ok(!/danger|warning|text-red|text-amber/.test(dong), "dòng đầu khung trung tính");
});

test("bộ lọc 'Có phản hồi sau dùng thuốc': cờ URL đi qua go(), trang và máy chủ", () => {
  assert.match(view, /Có phản hồi sau dùng thuốc/);
  assert.match(view, /params\.set\("phan_hoi_thuoc", "1"\)/);
  assert.match(page, /sp\.phan_hoi_thuoc === "1"/);
  assert.match(page, /thamSo\.set\("phan_hoi_thuoc", "1"\)/);
  // Đổi trang giữ bộ lọc (duongTrang) — mất cờ là sang trang 2 hết lọc.
  assert.match(page, /qs\.set\("phan_hoi_thuoc", "1"\)/);
  // Lọc ở máy chủ (cả danh sách), không lọc client trên 50 dòng đang xem.
  assert.ok(!/rows\.filter\([^)]*phanHoiThuoc/.test(view));
});

test("khung khách: dòng 'Phản hồi thuốc gần nhất' ở ĐẦU khung, không đọc lần hai", () => {
  assert.match(khung, /Phản hồi thuốc gần nhất/);
  assert.match(khung, /onDoc=\{setPhanHoiThuoc\}/);
  // Dòng nằm TRƯỚC khối Ghi chú (khối đầu tiên).
  assert.ok(
    khung.indexOf("<DongPhanHoiGanNhat") < khung.indexOf("<Khoi tieuDe={`Ghi chú về khách"),
    "dòng tóm tắt phải đứng đầu khung",
  );
  // Khối con báo lên qua callback — không có fetch thứ hai cho phản hồi thuốc.
  assert.match(khoiThuoc, /onDoc\?\.\(data\.items\)/);
  assert.equal((khung.match(/xem=phan-hoi-thuoc/g) ?? []).length, 0);
});
