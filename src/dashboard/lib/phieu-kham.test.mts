// Bản in phiếu khám hai trang (27/09/2026): mục III và trang ảnh đọc qua hai
// hàm này — màn khám dùng CÙNG hàm, nên giấy và màn không lệch nhau.
import assert from "node:assert/strict";
import test from "node:test";

import { vnYmd } from "./datetime.ts";
import {
  anhInDuoc,
  dongKetQua,
  dongNgoaiDanhMuc,
  dongTuDon,
  dongTuMau,
  HEN_NHANH,
  laONgayTaiKham,
  ngayHenTaiKham,
  soLuongTuChu,
  thanhTienDong,
  type ChiDinhVaKetQua,
  type KetQuaMotChiDinh,
  type MauThuoc,
} from "./phieu-kham.ts";

const tep = (id: string, loai_tep: string, xac: string | null, luc: string): KetQuaMotChiDinh => ({
  loai: "TEP",
  tep_id: id,
  ten: id,
  loai_tep,
  xac_nhan_trang_thai: xac,
  tai_len_luc: luc,
});

test("anhInDuoc: chỉ ẢNH hợp lệ (NULL = tải ở phòng), theo thứ tự chụp", () => {
  const cd = {
    ket_qua: [
      tep("a2", "ANH", "HOP_LE", "2026-09-27T09:02:00Z"),
      tep("a1", "ANH", null, "2026-09-27T09:01:00Z"),
      tep("cho", "ANH", "CHO_XAC_NHAN", "2026-09-27T09:03:00Z"),
      tep("tu-choi", "ANH", "TU_CHOI", "2026-09-27T09:04:00Z"),
      tep("vid", "VIDEO", null, "2026-09-27T09:05:00Z"),
      tep("pdf", "PDF", null, "2026-09-27T09:06:00Z"),
    ],
  } as unknown as ChiDinhVaKetQua;
  assert.deepEqual(
    anhInDuoc(cd).map((k) => k.tep_id),
    ["a1", "a2"],
  );
});

test("dongKetQua: bỏ ô trống, tách Kết luận, gắn đơn vị cho số", () => {
  const k = {
    loai: "PHIEU",
    ten: "Siêu âm",
    khung: [
      {
        ma: "do",
        ten: "Số đo",
        block: [
          { ma: "tu_cung", ten: "Tử cung", kieu: "so", goi_y: "mm" },
          { ma: "trong", ten: "Ô trống", kieu: "text" },
          { ma: "ket_luan", ten: "Kết luận", kieu: "doan_van" },
        ],
      },
    ],
    du_lieu: {
      tu_cung: { gia_tri: "45" },
      trong: { gia_tri: "" },
      ket_luan: { gia_tri: "Bình thường" },
    },
  } as unknown as KetQuaMotChiDinh;
  const { dong, ketLuan } = dongKetQua(k);
  assert.deepEqual(dong, [{ nhan: "Tử cung", gia: "45 mm" }]);
  assert.equal(ketLuan, "Bình thường");
});

// --- Đơn thuốc: đơn giá · ĐVT kho · dòng ngoài danh mục (27/09/2026) --------
const mau = (p: Partial<MauThuoc>): MauThuoc => ({
  ma: "T1",
  nhan_nguon: "Duphaston",
  brand: "",
  type: "Uống",
  dosage: "Ngày 2 lần",
  note: "",
  unit: "viên",
  drug_catalog_id: "k1",
  gia: 12000,
  ...p,
});

test("chọn thuốc kho: mang đơn giá + ĐVT kho; thuốc chưa gắn kho thì không", () => {
  const d = dongTuMau(mau({}));
  assert.equal(d.don_gia, 12000);
  assert.equal(d.dvt_kho, "viên");
  const chuaGan = dongTuMau(mau({ drug_catalog_id: null, gia: null }));
  assert.equal(chuaGan.don_gia, null);
  assert.equal(chuaGan.dvt_kho, null, "ĐVT chỉ là chữ khi KHO có");
  const tuDo = dongNgoaiDanhMuc();
  assert.equal(tuDo.drug_catalog_id, null);
  assert.equal(tuDo.ten_thuoc, "");
});

test("số lượng đọc như máy chủ: số / thập phân phẩy; phân số và 0 thì không đoán", () => {
  assert.equal(soLuongTuChu("30"), 30);
  assert.equal(soLuongTuChu(" 1,5 "), 1.5);
  assert.equal(soLuongTuChu("2 viên"), 2);
  assert.equal(soLuongTuChu("1/2"), null);
  assert.equal(soLuongTuChu("0"), null);
  assert.equal(soLuongTuChu("uống đến hết"), null);
  assert.equal(soLuongTuChu(""), null);
});

test("thành tiền chỉ khi có giá, đọc được số lượng và ĐVT khớp kho", () => {
  const d = { ...dongTuMau(mau({})), so_luong: "10" };
  assert.equal(thanhTienDong(d), 120000);
  assert.equal(thanhTienDong({ ...d, so_luong: "1,5", don_gia: 1001 }), 1502, "làm tròn đồng");
  assert.equal(thanhTienDong({ ...d, so_luong: "1/2" }), null);
  assert.equal(thanhTienDong({ ...d, don_vi: "Hộp" }), null, "2 hộp × giá một viên là sai");
  assert.equal(thanhTienDong({ ...d, don_vi: " Viên " }), 120000, "không phân biệt hoa/thường");
  assert.equal(thanhTienDong({ ...dongNgoaiDanhMuc(), so_luong: "3" }), null);
});

test("đọc đơn đã lưu: giữ ĐVT đã ghi; đơn cũ chưa ghi ĐVT thì lấy ĐVT kho", () => {
  const goc = {
    id: "p1",
    drug_catalog_id: "k1",
    drug_name_raw: "Duphaston",
    dosage_instructions: "Uống — Ngày 2 lần",
    caution: null,
    don_gia: 12000,
    dvt_kho: "viên",
  };
  const coDvt = dongTuDon({ ...goc, quantity: "2 hộp" });
  assert.deepEqual([coDvt.so_luong, coDvt.don_vi, coDvt.don_gia], ["2", "hộp", 12000]);
  const khongDvt = dongTuDon({ ...goc, quantity: "20" });
  assert.equal(khongDvt.don_vi, "viên");
  // Máy chủ cũ (chưa trả đơn giá) vẫn đọc được.
  const cu = dongTuDon({ ...goc, don_gia: undefined, dvt_kho: undefined, quantity: "5 viên" });
  assert.equal(cu.don_gia, null);
});

// --- Hẹn tái khám: chip 1 tuần · 2 tuần · 1 tháng · 3 tháng ----------------
const hen = (homNay: string, nhan: string) =>
  ngayHenTaiKham(homNay, HEN_NHANH.find((h) => h.nhan === nhan)!);

test("hẹn nhanh cộng ngày / tháng lịch từ hôm nay giờ VN", () => {
  assert.equal(hen("2026-09-27", "1 tuần"), "2026-10-04");
  assert.equal(hen("2026-09-27", "2 tuần"), "2026-10-11");
  assert.equal(hen("2026-09-27", "1 tháng"), "2026-10-27");
  assert.equal(hen("2026-09-27", "3 tháng"), "2026-12-27");
  assert.equal(hen("2026-12-28", "1 tuần"), "2027-01-04", "qua năm");
  assert.equal(hen("2026-11-15", "3 tháng"), "2027-02-15");
});

test("ngày không có ở tháng đích thì lùi về cuối tháng", () => {
  assert.equal(hen("2027-01-31", "1 tháng"), "2027-02-28");
  assert.equal(hen("2028-01-31", "1 tháng"), "2028-02-29", "năm nhuận");
  assert.equal(hen("2026-08-31", "1 tháng"), "2026-09-30");
  assert.equal(hen("2026-11-30", "3 tháng"), "2027-02-28");
});

test("hôm nay rác → rỗng, không ném", () => {
  assert.equal(hen("", "1 tuần"), "");
  assert.equal(hen("27/09/2026", "1 tuần"), "");
  assert.equal(hen("2026-02-30", "1 tháng"), "");
  assert.equal(hen("abc", "3 tháng"), "");
});

test("hôm nay tính theo giờ VN: 23:30 UTC đã là ngày hôm sau ở VN", () => {
  // `vnYmd` là nguồn "hôm nay" nơi gọi dùng; ghim ở đây để hai hàm đi cùng nhau.
  assert.equal(vnYmd(new Date(Date.UTC(2026, 8, 26, 23, 30))), "2026-09-27");
  assert.equal(hen(vnYmd(new Date(Date.UTC(2026, 8, 26, 23, 30))), "1 tuần"), "2026-10-04");
});

test("ô ngày tái khám nhận theo quy ước tên ô của máy chủ", () => {
  assert.equal(laONgayTaiKham("pk_follow_date"), true);
  assert.equal(laONgayTaiKham("hmvs_follow_date"), true);
  assert.equal(laONgayTaiKham("pk_ngay_kinh_cuoi"), false);
});
