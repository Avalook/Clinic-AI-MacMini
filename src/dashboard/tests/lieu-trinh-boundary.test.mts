import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// LIỆU TRÌNH ĐIỀU TRỊ — giao diện C1 (08/10/2026, docs/KE-HOACH-LIEU-TRINH.md):
// dải liệu trình trong thẻ chỉ định điều trị (hồ sơ khám khối 3) + khối "Liệu
// trình" ở quầy thu dịch vụ + dòng trả trước trên hoá đơn / phiếu thu. Con số,
// trạng thái, nút nào hiện đều do MÁY CHỦ trả; route Next chỉ chuyển tiếp.
const doc = (f: string) => readFileSync(new URL(f, import.meta.url), "utf8");
/** Bỏ dòng chú thích — chỉ soi mã thật. */
const ma = (s: string) => s.replace(/^\s*\/\/.*$/gm, "");
const LIB = doc("../lib/lieu-trinh.ts");
const ROUTE = doc("../app/api/lieu-trinh/route.ts");
const THE = doc("../app/(dashboard)/_lam-viec/phieu-kham/LieuTrinhThe.tsx");
const KHOI = doc("../app/(dashboard)/_lam-viec/phieu-kham/KhoiDieuTri.tsx");
const QUAY = doc("../app/(dashboard)/thu-ngan/LieuTrinhQuay.tsx");
const QTN = doc("../app/(dashboard)/thu-ngan/QuayThuNgan.tsx");
const HD = doc("../app/(dashboard)/thu-ngan/HoaDonMot.tsx");
const IN = doc("../app/print/phieu-thu/[id]/InPhieuThu.tsx");

test("route /api/lieu-trinh chỉ chuyển tiếp theo danh sách trắng, mã là UUID", () => {
  assert.match(ROUTE, /proxyJsonToBackend/);
  assert.doesNotMatch(ROUTE, /getSupabaseService|\.from\(|\.rpc\(/, "không chạm database");
  assert.match(ROUTE, /if \(!UUID\.test\(id\)\) return sai/);
  for (const duong of ["/theo-luot/", "/quay/", "/lich-su", "/dieu-chinh", "/dung", "/mo-lai", "/hoan-tac", "/tra-truoc", "lieu-trinh-buoi/gan", "lieu-trinh-buoi/go"]) {
    assert.ok(ROUTE.includes(duong), `thiếu đường ${duong}`);
  }
});

test("mọi lệnh liệu trình mang khoá gửi lại; lỗi đọc qua nhanLoi + mã 409", () => {
  assert.match(LIB, /du_lieu: \{ idempotency_key: khoaLT\(\), \.\.\.duLieu \}/);
  assert.match(LIB, /loi: nhanLoi\(d, /);
  assert.match(LIB, /ma: typeof d\?\.error === "string" \? d\.error : null/);
});

test("dải liệu trình: nút theo cờ máy chủ, không tự suy trạng thái", () => {
  const m = ma(THE);
  assert.match(m, /lt\.nut\?\.dieu_chinh/);
  assert.match(m, /lt\.nut\?\.dung/);
  assert.match(m, /lt\.nut\?\.mo_lai/);
  assert.match(m, /lt\.hoan_tac \?/);
  assert.match(m, /cd\.nut\?\.go/);
  assert.match(m, /cd\.nut\?\.tao/);
  assert.match(m, /cd\.nut\?\.chon/);
  // Không tự tính tiền / còn nợ trong TSX — số của máy chủ.
  assert.match(m, /còn nợ \$\{lt\.chua_tra\} buổi \(\$\{tienLT\(lt\.tien_con_lai\)\}\)/);
  assert.doesNotMatch(m, /so_buoi\s*-\s*|don_gia\s*\*/);
  // 409 DA_GAN_LIEU_TRINH → hỏi rõ rồi gửi lại tach_khoi_lieu_trinh_cu.
  assert.match(m, /kq\.ma === "DA_GAN_LIEU_TRINH"/);
  assert.match(m, /tach_khoi_lieu_trinh_cu: tach/);
  // Phiếu điều trị của buổi cũ mở CHỈ ĐỌC (trang in kết quả).
  assert.match(m, /href=\{`\/print\/ket-qua\/\$\{b\.order_id\}`\}/);
  // Không window.confirm — xác nhận tại chỗ.
  assert.doesNotMatch(m, /window\.confirm/);
  assert.match(m, /<XacNhanTaiCho/);
});

test("mọi nút ghi của dải nằm sau choGhi (popup Lịch sử khám, /patient-list chỉ đọc)", () => {
  const m = ma(THE);
  for (const nut of ["Điều chỉnh", "Dừng", "Mở lại", "Gỡ khỏi liệu trình", "Lập liệu trình mới"]) {
    assert.ok(m.includes(nut), `thiếu nút ${nut}`);
  }
  assert.match(m, /\{choGhi && lt\.nut\?\.dieu_chinh && !sua \?/);
  assert.match(m, /\{choGhi && lt\.nut\?\.dung && !hoiDung \?/);
  assert.match(m, /\{choGhi && lt\.nut\?\.mo_lai \?/);
  assert.match(m, /\{choGhi \? them : null\}/);
  assert.match(m, /\{choGhi && \(cd\.nut\?\.tao \|\| moTach\) && !hoiTach \?/);
  assert.match(KHOI, /\{choGhi && lt \? \(\s*<DeXuatLieuTrinh/);
});

test("KhoiDieuTri: dải trong thân thẻ + nghe đúng bảng liệu trình", () => {
  assert.match(KHOI, /<DaiLieuTrinh visitId=\{visitId\} cd=\{cdLT\} luot=\{lt\} choGhi=\{choGhi\} onDoi=\{napLT\} \/>/);
  assert.match(
    KHOI,
    /useNgheBang\(\["lieu_trinh", "lieu_trinh_buoi", "lieu_trinh_lich_su", "lieu_trinh_tra_truoc"\], napLT\)/,
  );
  assert.match(KHOI, /docLT<LieuTrinhLuot>\("theo-luot", visitId\)/);
});

test("quầy: khối Liệu trình ở hoá đơn khách đang chọn, trả trước qua máy chủ", () => {
  assert.match(QTN, /<LieuTrinhQuay visitId=\{l\.visit_id\} reloadToken=\{l\.quay_thu\?\.revision\}/);
  // Lượt chỉ có dòng trả trước: cờ chờ thu của máy chủ.
  assert.match(QTN, /Boolean\(l\.cho_thu\)/);
  const m = ma(QUAY);
  assert.match(m, /docLT<\{ lieu_trinh: LTQ\[\] \}>\("quay", visitId\)/);
  assert.match(m, /lenhLT\("tra-truoc", \{/);
  assert.match(m, /expected_so_buoi: dangChon\?\.so_buoi \?\? null/);
  assert.match(m, /void tra\("het"\)/);
  assert.match(m, /max=\{x\.tra_truoc_toi_da\}/);
  assert.match(m, /x\.goi_y_tra_them/);
  assert.match(m, /useNgheBang\(\["lieu_trinh", "lieu_trinh_buoi", "lieu_trinh_tra_truoc"\], nap\)/);
  assert.doesNotMatch(m, /\*\s*x\.don_gia|don_gia\s*\*/, "không tự nhân tiền");
});

test("hoá đơn quầy: [Bỏ] dòng trả trước + chip Buổi k/N trên chỉ định", () => {
  assert.match(HD, /lenhLT\("bo-tra-truoc", \{\}, id\)/);
  assert.match(HD, /d\.loai === "lieu_trinh" && boTraTruoc \?/);
  assert.match(HD, /nhanBuoi\(d\.lieu_trinh\.buoi_so, d\.lieu_trinh\.so_buoi, d\.lieu_trinh\.tra_truoc\)/);
  assert.match(LIB, /`Buổi \$\{buoiSo\}\/\$\{soBuoi\}\$\{traTruoc \? " · đã trả trước" : ""\}`/);
});

test("phiếu thu in dòng trả trước kèm (liệu trình), không in × k", () => {
  assert.match(IN, /\{d\.lieu_trinh \? " \(liệu trình\)" : d\.so_luong !== 1 \?/);
});
