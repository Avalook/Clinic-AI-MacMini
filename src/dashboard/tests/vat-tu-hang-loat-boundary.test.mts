import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// ĐẶT CỜ VẬT TƯ HÀNG LOẠT THEO LOẠI (Kho vật tư → Danh mục) — ranh giới giao diện:
//   · proxy chỉ chuyển tiếp xuống ĐÚNG một đường FastAPI, bắt đăng nhập, không luật nghiệp vụ;
//   · khối "Đặt cho cả loại" xem trước (ap_dung=false) rồi mới ghi (ap_dung=true), xác nhận ngay
//     trên trang (XacNhanTaiCho, không window.confirm), có Hoàn tác bằng ids máy chủ trả;
//   · mã loại / cờ ở màn KHỚP bảng trong service Python (chống lệch hai nơi);
//   · không luật nghiệp vụ trong TSX (không đụng `active`, không suy quyền từ vai).

const doc = (rel: string) => readFileSync(new URL(rel, import.meta.url), "utf8");
const route = doc("../app/api/service-price/vat-tu-hang-loat/route.ts");
const khoi = doc("../app/(dashboard)/kho-vat-tu/DatCoTheoLoai.tsx");
const danhMuc = doc("../app/(dashboard)/kho-vat-tu/DanhMucVatTu.tsx");
const dich = doc("../../clinicai/services/vat_tu_danh_muc_service.py");
const boComment = (m: string) => m.replace(/^\s*\/\/.*$/gm, "");
const khoiPy = (ten: string) => dich.slice(dich.indexOf(`${ten}:`), dich.indexOf("}", dich.indexOf(`${ten}:`)));

test("proxy: bắt đăng nhập, chỉ chuyển tiếp xuống đúng một đường, chỉ POST", () => {
  assert.match(route, /Unauthorised/);
  assert.match(route, /status: 401/);
  assert.match(route, /proxyJsonToBackend\(\s*"POST",\s*"\/api\/v1\/service-prices\/vat-tu\/hang-loat"/);
  assert.doesNotMatch(route, /export async function (GET|PUT|PATCH|DELETE)/);
  // Không tự quyết quyền / loại / cờ ở tầng Next — máy chủ trả 422 có câu.
  assert.doesNotMatch(boComment(route), /price\.service|role\s*===|vai\s*===|VPP|VTYT/);
  // Chỉ chuyển bốn khoá đã biết; không rải nguyên body.
  assert.doesNotMatch(route, /\.\.\.body\b/);
  assert.match(route, /ap_dung: body\.ap_dung \?\? false/);
});

test("mã loại và cờ ở màn khớp bảng trong service Python", () => {
  const loaiPy = [...khoiPy("LOAI_HANG_LOAT").matchAll(/^ {4}"([A-Z_]+)": (?:"[A-Z]+"|None),$/gm)].map((m) => m[1]);
  const coPy = [...khoiPy("CO_HANG_LOAT").matchAll(/^ {4}"([a-z_]+)": "[a-z_]+",$/gm)].map(
    (m) => m[1],
  );
  assert.deepEqual([...loaiPy].sort(), ["CHUA_PHAN_LOAI", "VPP", "VTYT"]);
  assert.deepEqual([...coPy].sort(), ["can_duyet_nhap", "can_ql_duyet", "kinh_doanh"]);
  for (const ma of [...loaiPy, ...coPy]) {
    assert.ok(khoi.includes(`"${ma}"`), `màn thiếu mã ${ma}`);
  }
  // Tên hiển thị đúng chữ Tuyền giao.
  for (const ten of [
    "Văn phòng phẩm",
    "Vật tư y tế",
    "Chưa phân loại",
    "Được kinh doanh",
    "Cần QL duyệt bán",
    "Cần duyệt nhập",
  ]) {
    assert.ok(khoi.includes(ten), `màn thiếu nhãn “${ten}”`);
  }
});

test("xem trước 'Sẽ đổi N vật tư' rồi mới Áp dụng; xác nhận tại chỗ, không window.confirm", () => {
  assert.match(khoi, /ap_dung: false/);
  assert.match(khoi, /ap_dung: true/);
  assert.match(khoi, /Sẽ \$\{bat \? "gắn" : "gỡ"\} nhãn/);
  assert.match(khoi, /XacNhanTaiCho/);
  assert.doesNotMatch(khoi, /window\.confirm|\bconfirm\(/);
  // Nút Áp dụng khoá khi chưa đếm xong hoặc không có gì để đổi.
  assert.match(khoi, /disabled=\{ban \|\| xem === null \|\| so === 0\}/);
  // Mở hộp xác nhận chứ không ghi ngay.
  assert.match(khoi, /onClick=\{\(\) => setHoiKhoa\(khoa\)\}/);
  // Ghi xong tải lại danh sách.
  assert.match(khoi, /router\.refresh\(\)/);
});

test("Hoàn tác: gửi giá trị ngược cho đúng ids máy chủ trả", () => {
  assert.match(khoi, /bat: !daDoi\.bat, ids: daDoi\.ids/);
  assert.match(khoi, /ids: r\.kq\.ids/);
});

test("đi qua proxy Next, không gọi thẳng FastAPI; không luật nghiệp vụ trong TSX", () => {
  assert.match(khoi, /\/api\/service-price\/vat-tu-hang-loat/);
  assert.doesNotMatch(khoi, /\/api\/v1\//);
  assert.doesNotMatch(khoi, /\bactive\b|price\.service|MANAGEMENT|role\s*===|vai\s*===|quyenCuaToi|useQuyen/);
});

test("nút luôn có type, không màu cảnh báo cho việc bình thường, lỗi đỏ chỉ ở role=alert", () => {
  assert.doesNotMatch(khoi, /<button(?![^>]*type=)/);
  assert.doesNotMatch(khoi, /bg-warning|bg-danger|text-warning|tone="(warning|danger)"/);
  for (const m of khoi.matchAll(/<p[^>]*text-danger[^>]*>/g)) {
    assert.match(m[0], /role="alert"/);
  }
  for (const m of khoi.matchAll(/<Button\b[^>]*>/g)) {
    assert.match(m[0], /type="button"/);
  }
});

test("chỉ hiện cho người sửa được danh mục; người chỉ xem không thấy khối", () => {
  assert.match(danhMuc, /suaDuoc \? <DatCoTheoLoai ds=\{ds\} \/> : null/);
  // Khối nằm TRÊN bảng vật tư (đầu tab).
  assert.ok(danhMuc.indexOf("<DatCoTheoLoai") < danhMuc.indexOf("<VatTuBangGia"));
});
