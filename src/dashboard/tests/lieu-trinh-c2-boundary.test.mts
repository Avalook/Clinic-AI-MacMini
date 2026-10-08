// LIỆU TRÌNH C2 (08/10/2026, docs/KE-HOACH-LIEU-TRINH.md) — CSKH + khung khách +
// chip phòng / tiếp đón / bàn khám + bản in:
//   * CSKH `/nhac-tai-kham` có tab "Liệu trình" hai danh sách (đề xuất / đang dở
//     quá X ngày), nút Đăng ký / Đặt lịch buổi kế (bộ đặt lịch SẴN CÓ) / Dừng,
//     mọi lệnh có Hoàn tác;
//   * khung khách có khối "Liệu trình" + lịch sử sửa;
//   * chip: MỘT lần gọi theo lô lượt, chỉ THÊM chữ — không đổi lọc / đếm / sắp
//     xếp, liệu trình không sinh dòng mới ở danh sách vận hành nào;
//   * bản in phiếu khám: "Liệu trình: buổi k/N" từ máy chủ;
//   * route Next chỉ chuyển tiếp FastAPI, không chạm DB; không luật trong TSX.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  docSoBuoiDangKy,
  khoaLuot,
  nhanBuoi,
  nhanBuoiCuaLuot,
  nhanLieuTrinhLuot,
  type ChipLieuTrinh,
} from "../lib/lieu-trinh.ts";

const read = (path: string) => readFileSync(new URL(path, import.meta.url), "utf8");

const PAGE = read("../app/(dashboard)/nhac-tai-kham/page.tsx");
const CSKH = read("../app/(dashboard)/nhac-tai-kham/LieuTrinhCskh.tsx");
const DONG = read("../app/(dashboard)/_lam-viec/LieuTrinhKhach.tsx");
const DAT = read("../app/(dashboard)/_lam-viec/DatLichBuoiKe.tsx");
const HOOK = read("../app/(dashboard)/_lam-viec/dung-chip-lieu-trinh.ts");
const KHUNG_KHACH = read("../app/(dashboard)/_lam-viec/KhungKhach.tsx");
const CUSTOMERS = read("../app/(dashboard)/customers/CustomersView.tsx");
const PHONG = read("../app/(dashboard)/phong/[ma]/PhongDichVu.tsx");
const SAP_DEN = read("../app/(dashboard)/phong/[ma]/SapDenPhong.tsx");
const HANG = read("../app/(dashboard)/phong/[ma]/HangChoKhachPhong.tsx");
const KHUNG_CD = read("../app/(dashboard)/phong/[ma]/KhungChiDinhKhach.tsx");
const TIEP_DON = read("../app/(dashboard)/reception/queue/QueueBoard.tsx");
const BAN_KHAM = read("../app/(dashboard)/ban-kham/BanKham.tsx");
const IN = read("../app/print/phieu-kham/[visitId]/InPhieuKham.tsx");
const R_DS = read("../app/api/cskh/lieu-trinh/route.ts");
const R_MOT = read("../app/api/cskh/lieu-trinh/[id]/route.ts");
const R_CHIP = read("../app/api/lieu-trinh/chip/route.ts");

const CHIP: ChipLieuTrinh = {
  chi_dinh: {
    o1: {
      visit_id: "v1",
      lieu_trinh_id: "l1",
      buoi_so: 3,
      so_buoi: 10,
      tra_truoc: true,
      service_name: "Ghế điện",
      trang_thai: "DANG_LAM",
    },
    o2: {
      visit_id: "v2",
      lieu_trinh_id: "l2",
      buoi_so: 1,
      so_buoi: 5,
      tra_truoc: false,
      service_name: "Laser",
      trang_thai: "DANG_LAM",
    },
  },
  khach: {
    v1: [{ lieu_trinh_id: "l1", service_name: "Ghế điện", so_buoi: 10, da_lam: 2, con_lai: 8, con_tra_truoc: 3 }],
    v2: [{ lieu_trinh_id: "l2", service_name: "Laser", so_buoi: 5, da_lam: 0, con_lai: 5, con_tra_truoc: 0 }],
    v3: [],
  },
};

test("chữ chip ghép từ số máy chủ (hàm thuần)", () => {
  assert.equal(nhanBuoi(CHIP.chi_dinh.o1), "Buổi 3/10 · đã trả trước");
  assert.equal(nhanBuoi(CHIP.chi_dinh.o2), "Buổi 1/5");
  assert.equal(nhanLieuTrinhLuot(CHIP, "v1"), "Liệu trình Ghế điện: còn 3 buổi đã trả");
  assert.equal(nhanLieuTrinhLuot(CHIP, "v2"), "Liệu trình Laser: đã làm 0/5");
  assert.equal(nhanLieuTrinhLuot(CHIP, "v3"), null);
  assert.equal(nhanLieuTrinhLuot(null, "v1"), null);
  assert.equal(nhanLieuTrinhLuot(CHIP, null), null);
  // Dòng khách ở phòng: chỉ định của ĐÚNG lượt, theo id chỉ định hoặc ref_id hàng chờ.
  assert.equal(nhanBuoiCuaLuot(CHIP, "v1", [{ id: "x" }, { id: "o1" }]), "Buổi 3/10 · đã trả trước");
  assert.equal(nhanBuoiCuaLuot(CHIP, "v1", [{ ref_id: "o1" }]), "Buổi 3/10 · đã trả trước");
  assert.equal(nhanBuoiCuaLuot(CHIP, "v2", [{ id: "o1" }]), null);
  assert.equal(nhanBuoiCuaLuot(null, "v1", [{ id: "o1" }]), null);
});

test("khoá lô lượt ổn định: bỏ rỗng / trùng, xếp — đổi thứ tự không gọi lại", () => {
  assert.equal(khoaLuot(["b", null, "a", "b", undefined, ""]), "a,b");
  assert.equal(khoaLuot(["a", "b"]), khoaLuot(["b", "a"]));
  assert.equal(khoaLuot([]), "");
  assert.equal(khoaLuot(Array.from({ length: 400 }, (_, i) => `v${1000 + i}`)).split(",").length, 300);
});

test("số buổi đăng ký: rác → null (nút tắt), không ném", () => {
  for (const rac of ["", " ", "abc", "0", "-1", "201", "1.5", "1e2", "١"]) {
    assert.equal(docSoBuoiDangKy(rac), null, rac);
  }
  assert.equal(docSoBuoiDangKy(" 5 "), 5);
  assert.equal(docSoBuoiDangKy("200"), 200);
});

test("CSKH /nhac-tai-kham: tab Liệu trình, hai danh sách, chọn X ngày", () => {
  assert.match(PAGE, /TabNhacTaiKham/);
  assert.match(PAGE, /<LieuTrinhCskh/);
  assert.match(PAGE, /tab === "lieu-trinh"/);
  assert.match(CSKH, /docDs\("de_xuat"/);
  assert.match(CSKH, /docDs\("dang_do"/);
  assert.match(CSKH, /\/api\/cskh\/lieu-trinh\?/);
  assert.match(CSKH, /Đề xuất chưa đăng ký/);
  assert.match(CSKH, /Đang dở, quá \$\{quaNgay\} ngày chưa quay lại/);
  assert.match(CSKH, /QUA_NGAY_CHON/);
  assert.match(CSKH, /<DatLichBuoiKe/);
  // Đọc hỏng phải nói thẳng — không giả "không ai cần gọi".
  assert.match(CSKH, /KHÔNG có nghĩa là không ai cần gọi/);
});

test("dòng liệu trình: Đăng ký (1 / N / số khác) · Đặt lịch buổi kế · Dừng · Mở lại · Hoàn tác", () => {
  for (const lenh of ['"dang-ky"', '"dung"', '"mo-lai"', '"hoan-tac"']) {
    assert.match(DONG, new RegExp(`thao_tac: ${lenh}`), lenh);
  }
  assert.match(DONG, /1 buổi/);
  assert.match(DONG, /Cả lộ trình \{lt\.so_buoi\} buổi/);
  assert.match(DONG, /Số khác/);
  assert.match(DONG, /Đặt lịch buổi kế/);
  assert.match(DONG, /Không đăng ký/);
  assert.match(DONG, /expected_revision/);
  assert.match(DONG, /idempotency_key/);
  // Mọi lệnh có Hoàn tác (thông báo + lịch sử sửa).
  assert.match(DONG, /onBao\(\{ cau, goi: hoanTacLieuTrinh\(lt\.id\) \}\)/);
  assert.match(DONG, /<NutHoanTac/);
  assert.match(DONG, /Lịch sử sửa/);
  // Không luật nghiệp vụ / không hộp thoại hệ thống / không gọi thẳng FastAPI.
  assert.doesNotMatch(DONG, /window\.confirm|\/api\/v1\//);
  assert.doesNotMatch(DONG, /so_buoi\s*-|da_tra\s*-|don_gia\s*\*/);
});

test("Đặt lịch buổi kế = bộ đặt lịch SẴN CÓ khoá loại khám Điều trị máy chủ trả", () => {
  assert.match(DAT, /import DatLichModal from "\.\.\/customers\/DatLichModal"/);
  assert.match(DAT, /khoaDichVu=\{\{ serviceId: lt\.service_type_id/);
  assert.doesNotMatch(DAT, /<input|<select|fetch\(/);
  assert.match(CUSTOMERS, /<DatLichBuoiKe/);
  assert.match(CUSTOMERS, /onDatLichLieuTrinh=\{canEdit \? setDatLichLt : undefined\}/);
});

test("khung khách /customers: khối Liệu trình (mọi liệu trình + lịch sử sửa)", () => {
  assert.match(KHUNG_KHACH, /<Khoi tieuDe="Liệu trình">/);
  assert.match(KHUNG_KHACH, /<LieuTrinhCuaKhach/);
  assert.match(DONG, /\/api\/cskh\/lieu-trinh\?khach=/);
  assert.match(DONG, /quyen_cskh/);
  assert.match(DONG, /kemLichSu/);
});

test("chip: MỘT lần gọi theo lô lượt cho mỗi màn, chỉ thêm chữ", () => {
  assert.equal((HOOK.match(/fetch\(/g) ?? []).length, 1);
  assert.match(HOOK, /\/api\/lieu-trinh\/chip\?luot=/);
  for (const [ten, nd] of [
    ["PhongDichVu", PHONG],
    ["QueueBoard", TIEP_DON],
    ["BanKham", BAN_KHAM],
  ] as const) {
    assert.equal((nd.match(/useChipLieuTrinh\(/g) ?? []).length, 1, `${ten} gọi chip đúng một lần`);
  }
  // Dòng con KHÔNG tự gọi máy chủ và KHÔNG dùng chip để lọc / sắp xếp / đếm.
  for (const [ten, nd] of [
    ["SapDenPhong", SAP_DEN],
    ["HangChoKhachPhong", HANG],
    ["KhungChiDinhKhach", KHUNG_CD],
  ] as const) {
    assert.doesNotMatch(nd, /lieu-trinh\/chip|useChipLieuTrinh/, `${ten} không tự gọi chip`);
    assert.doesNotMatch(nd, /lieuTrinh[^\n]*\.(filter|sort|length)/, `${ten} không lọc theo chip`);
  }
  assert.match(KHUNG_CD, /nhanBuoi\(buoi\)/);
  assert.match(TIEP_DON, /nhanLieuTrinhLuot\(chipLt/);
  assert.match(BAN_KHAM, /nhanLieuTrinhLuot\(lieuTrinh/);
});

test("bản in phiếu khám: Liệu trình: buổi k/N từ máy chủ", () => {
  assert.match(IN, /\{c\.lieu_trinh \? \(/);
  assert.match(IN, /Liệu trình: buổi \{c\.lieu_trinh\.buoi_so\}\/\{c\.lieu_trinh\.so_buoi\}/);
});

test("route Next chỉ chuyển tiếp FastAPI, không chạm DB", () => {
  for (const nd of [R_DS, R_MOT, R_CHIP]) {
    assert.match(nd, /proxyJsonToBackend/);
    assert.doesNotMatch(nd, /supabase|createClient|\.from\(/i);
  }
  assert.match(R_DS, /\/api\/v1\/lieu-trinh\/cskh/);
  assert.match(R_DS, /\/api\/v1\/lieu-trinh\/theo-khach\//);
  assert.match(R_MOT, /\/api\/v1\/lieu-trinh\/\$\{id\}\/lich-su/);
  assert.match(R_MOT, /"dang-ky", "dung", "mo-lai", "hoan-tac"/);
  assert.match(R_CHIP, /\/api\/v1\/lieu-trinh\/chip\?luot=/);
});
