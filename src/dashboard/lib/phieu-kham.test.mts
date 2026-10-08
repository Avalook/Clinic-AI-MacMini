// Bản in phiếu khám hai trang (27/09/2026): mục III và trang ảnh đọc qua hai
// hàm này — màn khám dùng CÙNG hàm, nên giấy và màn không lệch nhau.
import assert from "node:assert/strict";
import test from "node:test";

import { vnYmd } from "./datetime.ts";
import { docNhoGap, ghiNhoGap, moBanDau, type KhoNho } from "./ngan-gap.ts";
import {
  anhInDuoc,
  phanChiDinh,
  chipMauDanhMuc,
  coGiaTriO,
  gomNhom,
  oCuaNhom,
  oDangHien,
  oThuGonDangAn,
  soODaDien,
  dongKetQua,
  tongPhongKham,
  dongNgoaiDanhMuc,
  dongTuDon,
  dongTuMau,
  giaTriDoc,
  HEN_NHANH,
  laDicom,
  laONgayTaiKham,
  ngayHenTaiKham,
  nhomThuThuat,
  NHOM_THU_THUAT_MAC_DINH,
  soLuongTuChu,
  tachDanhMucKhac,
  thanhTienDong,
  gopCanhBao,
  type ChiDinhVaKetQua,
  type KetQuaMotChiDinh,
  type MauThuoc,
  type OPhieu,
  type NhomCls,
  type ThuThuatNguon,
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

test("anhInDuoc: DICOM không vào trang ảnh (trình duyệt không vẽ được) — đợt 3", () => {
  const dicomCu = { ...tep("dcm-cu", "ANH", null, "2026-09-27T09:01:00Z"), mime: "application/dicom" };
  const dicomMoi = { ...tep("dcm", "TAI_LIEU", null, "2026-09-27T09:02:00Z"), mime: "application/dicom" };
  const jpg = { ...tep("jpg", "ANH", null, "2026-09-27T09:03:00Z"), mime: "image/jpeg" };
  const cd = { ket_qua: [dicomCu, dicomMoi, jpg] } as unknown as ChiDinhVaKetQua;
  assert.deepEqual(
    anhInDuoc(cd).map((k) => k.tep_id),
    ["jpg"],
  );
});

test("laDicom: đúng mime, không phân biệt hoa thường; rác → false", () => {
  assert.equal(laDicom("application/dicom"), true);
  assert.equal(laDicom(" Application/DICOM "), true);
  assert.equal(laDicom("image/jpeg"), false);
  assert.equal(laDicom(null), false);
  assert.equal(laDicom(undefined), false);
  assert.equal(laDicom(42), false);
  assert.equal(laDicom(""), false);
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

test("tachDanhMucKhac: nhóm phiếu giấy giữ nguyên, nhóm bảng giá gom một danh sách", () => {
  const m = (nhan: string) => ({ nhan, cach_tra_ket_qua: "", form_id_ket_qua: null, service_code: nhan });
  const ds: NhomCls[] = [
    { nhom: "Siêu âm thai", muc: [m("SA1")] },
    { nhom: "Thủ thuật (danh mục phòng khám)", muc: [m("LEEP"), m("PRP")] },
    { nhom: "Xét nghiệm", muc: [m("XN1")] },
    { nhom: "Xét nghiệm (danh mục phòng khám)", muc: [m("NIPT")] },
  ];
  const { chinh, khac } = tachDanhMucKhac(ds);
  assert.deepEqual(chinh.map((n) => n.nhom), ["Siêu âm thai", "Xét nghiệm"]);
  assert.deepEqual(khac.map((x) => [x.nhan, x.nhom_goc]), [
    ["LEEP", "Thủ thuật"],
    ["PRP", "Thủ thuật"],
    ["NIPT", "Xét nghiệm"],
  ]);
  // Rác từ máy chủ không làm sập danh mục.
  assert.deepEqual(tachDanhMucKhac(null as unknown as NhomCls[]), { chinh: [], khac: [] });
  assert.deepEqual(tachDanhMucKhac([null, { nhom: "x" }] as unknown as NhomCls[]), { chinh: [], khac: [] });
});

test("chipMauDanhMuc: đối tác · mẫu PDF · tự do", () => {
  assert.equal(chipMauDanhMuc({ cach_tra_ket_qua: "Đối tác", form_id_ket_qua: "KQ_X" }).nhan, "đối tác");
  assert.equal(chipMauDanhMuc({ cach_tra_ket_qua: "Siêu âm", form_id_ket_qua: "KQ_SA" }).nhan, "mẫu PDF");
  assert.equal(chipMauDanhMuc({ cach_tra_ket_qua: "", form_id_ket_qua: "KQ_CHUNG" }).nhan, "tự do");
  assert.equal(chipMauDanhMuc({ cach_tra_ket_qua: "Nội bộ", form_id_ket_qua: null }).nhan, "tự do");
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

test("ô ngày đọc / in kiểu VN; giá trị lạ để nguyên", () => {
  const o = { ma: "pk_follow_date", ten: "Ngày tái khám", kieu: "ngay" } as OPhieu;
  assert.equal(giaTriDoc(o, { gia_tri: "2026-10-27", nguon: "BS" }), "27/10/2026");
  assert.equal(giaTriDoc(o, { gia_tri: "tuần sau", nguon: "BS" }), "tuần sau");
  assert.equal(giaTriDoc(o, { gia_tri: "", nguon: "BS" }), "—");
  const chu = { ma: "x", ten: "X", kieu: "text" } as OPhieu;
  assert.equal(giaTriDoc(chu, { gia_tri: "2026-10-27", nguon: "BS" }), "2026-10-27");
});

test("gopCanhBao: ô vừa gửi lấy cảnh báo mới, ô khác giữ cảnh báo cũ (đợt 3)", () => {
  const cu = [
    { ma: "so_1", ten: "Chu kỳ", loi: "“28-30” không phải số — ô được để trống." },
    { ma: "ngay_1", ten: "Ngày KCC", loi: "Ngày không đọc được." },
  ];
  // Lưu ô khác (text) — không có cảnh báo mới → hai cảnh báo cũ còn nguyên.
  assert.deepEqual(gopCanhBao(cu, ["ghi_chu"], []), cu);
  // Sửa ô số cho đúng → hết cảnh báo ô ấy, ô ngày vẫn còn.
  assert.deepEqual(gopCanhBao(cu, ["so_1"], []), [cu[1]]);
  // Gửi lại ô số vẫn sai → cảnh báo mới thay cũ, không nhân đôi.
  const moi = [{ ma: "so_1", ten: "Chu kỳ", loi: "“abc” không phải số — ô được để trống." }];
  assert.deepEqual(gopCanhBao(cu, ["so_1"], moi), [cu[1], moi[0]]);
  // Trùng mã trong phản hồi → một.
  assert.equal(gopCanhBao([], ["so_1"], [moi[0], moi[0]]).length, 1);
});

test("gopCanhBao: phản hồi rác không ném, bỏ phần tử hỏng", () => {
  const cu = [{ ma: "a", ten: "A", loi: "x" }];
  assert.deepEqual(gopCanhBao(cu, [], null), cu);
  assert.deepEqual(gopCanhBao(cu, [], "loi"), cu);
  assert.deepEqual(gopCanhBao([], [], [null, 1, { ma: "", ten: "t", loi: "l" }, { ma: "b" }]), []);
  assert.deepEqual(gopCanhBao([], [], [{ ma: "b", ten: "B", loi: "hỏng", thua: 1 }]), [
    { ma: "b", ten: "B", loi: "hỏng" },
  ]);
});

// ── Đợt 3 (27/09/2026): ô nào đang hiện — thu_gon · hien_khi · gap ──────────
const TG = (ma: string): OPhieu => ({ ma, ten: ma, kieu: "text", nhom: "Tiền sử", thu_gon: true });
const CO: OPhieu = {
  ma: "x_co",
  ten: "Dị ứng thuốc",
  kieu: "chon",
  nhom: "Tiền sử",
  lua_chon: [
    { ma: "x_co_1", ten: "Có" },
    { ma: "x_co_2", ten: "Không" },
  ],
};
const CT: OPhieu = {
  ma: "x_ct",
  ten: "Chi tiết dị ứng thuốc",
  kieu: "doan_van",
  nhom: "Tiền sử",
  hien_khi: { o: "x_co", la: "x_co_1" },
};
const KHONG = new Set<string>();

test("thu_gon: ẩn cho tới khi bấm chip; bấm rồi thì hiện", () => {
  assert.equal(oDangHien(TG("a"), {}, KHONG), false);
  assert.equal(oDangHien(TG("a"), {}, new Set(["a"])), true);
  assert.equal(oDangHien(TG("a"), {}, new Set(["b"])), false);
});

test("ô có giá trị LUÔN hiện — tải lại phiếu không giấu chữ đã gõ", () => {
  assert.equal(oDangHien(TG("a"), { a: "1001" }, KHONG), true);
  // chỉ khoảng trắng = chưa điền
  assert.equal(oDangHien(TG("a"), { a: "   " }, KHONG), false);
  // Chi tiết dị ứng đã có chữ mà ô Có/Không đang "Không" (hoặc phiếu cũ chưa chọn)
  assert.equal(oDangHien(CT, { x_ct: "Penicillin", x_co: "x_co_2" }, KHONG), true);
  assert.equal(oDangHien(CT, { x_ct: "Penicillin" }, KHONG), true);
});

test("hien_khi: chỉ hiện khi ô chọn kia đang chọn đúng mã", () => {
  assert.equal(oDangHien(CT, {}, KHONG), false);
  assert.equal(oDangHien(CT, { x_co: "" }, KHONG), false);
  assert.equal(oDangHien(CT, { x_co: "x_co_2" }, KHONG), false);
  assert.equal(oDangHien(CT, { x_co: "x_co_1" }, KHONG), true);
  // ô điều khiển nhiều-chọn: hiện khi mảng có mã
  const nhieu: OPhieu = { ...CT, hien_khi: { o: "y", la: "y_3" } };
  assert.equal(oDangHien(nhieu, { y: ["y_1", "y_3"] }, KHONG), true);
  assert.equal(oDangHien(nhieu, { y: ["y_1"] }, KHONG), false);
  // bấm chip không mở được ô hien_khi (không phải ô thu gọn)
  assert.equal(oDangHien(CT, {}, new Set(["x_ct"])), false);
});

test("ô thường (không khai gì) luôn hiện — phiếu v1 vẽ đủ như cũ", () => {
  assert.equal(oDangHien({ ma: "a", ten: "A", kieu: "text" }, {}, KHONG), true);
  assert.equal(oDangHien(CO, {}, KHONG), true);
});

test("chip thu gọn = ô thu_gon CHƯA hiện, đúng thứ tự khung", () => {
  const [nhom] = gomNhom([TG("a"), TG("b"), CO, CT, TG("c")]);
  assert.deepEqual(
    oThuGonDangAn(nhom, {}, KHONG).map((o) => o.ma),
    ["a", "b", "c"],
  );
  assert.deepEqual(
    oThuGonDangAn(nhom, { b: "x" }, new Set(["c"])).map((o) => o.ma),
    ["a"],
  );
});

test("gap là của NHÓM: mọi ô khai gap mới gập", () => {
  const cls = (ma: string, gap = true): OPhieu => ({ ma, ten: ma, kieu: "text", nhom: "CLS", gap });
  const [a, b] = gomNhom([TG("t"), cls("c1"), cls("c2")]);
  assert.equal(a.gap, false);
  assert.equal(b.gap, true);
  const [nua] = gomNhom([cls("c1"), cls("c2", false)]);
  assert.equal(nua.gap, false);
});

test("đếm ô đã điền của nhóm — tính cả ô trong bảng", () => {
  const bang = { ma: "kq", ten: "Xét nghiệm", cot: ["Kết quả"] };
  const [n] = gomNhom([
    { ma: "b1", ten: "AMH", kieu: "text", nhom: "CLS", gap: true, bang, hang: "AMH", cot: "Kết quả" },
    { ma: "b2", ten: "FSH", kieu: "text", nhom: "CLS", gap: true, bang, hang: "FSH", cot: "Kết quả" },
  ]);
  assert.deepEqual(oCuaNhom(n).map((o) => o.ma), ["b1", "b2"]);
  assert.equal(soODaDien(oCuaNhom(n), { b2: "3.1" }), 1);
  assert.equal(soODaDien(oCuaNhom(n), {}), 0);
});

test("coGiaTriO: rỗng · trắng · mảng rỗng = chưa điền", () => {
  assert.equal(coGiaTriO(undefined), false);
  assert.equal(coGiaTriO(""), false);
  assert.equal(coGiaTriO("  "), false);
  assert.equal(coGiaTriO([]), false);
  assert.equal(coGiaTriO(["a"]), true);
  assert.equal(coGiaTriO("0"), true);
});

// ── Ngăn gập nhớ theo người dùng ────────────────────────────────────────────
test("mở lúc đầu: đã nhớ thì theo nhớ, rác/không có thì theo mặc định", () => {
  assert.equal(moBanDau("1", false), true);
  assert.equal(moBanDau("0", true), false);
  assert.equal(moBanDau(null, true), true);
  assert.equal(moBanDau(undefined, false), false);
  assert.equal(moBanDau("rác", false), false);
  assert.equal(moBanDau("true", true), true);
});

test("đọc/ghi nhớ gập: kho hỏng hay không có kho thì không ném", () => {
  const bang = new Map<string, string>();
  const kho: KhoNho = {
    getItem: (k) => bang.get(k) ?? null,
    setItem: (k, v) => void bang.set(k, v),
  };
  ghiNhoGap("phieu-kham:NT:B", false, kho);
  assert.equal(docNhoGap("phieu-kham:NT:B", kho), "0");
  ghiNhoGap("phieu-kham:NT:B", true, kho);
  assert.equal(moBanDau(docNhoGap("phieu-kham:NT:B", kho), false), true);

  const hong: KhoNho = {
    getItem: () => {
      throw new Error("SecurityError");
    },
    setItem: () => {
      throw new Error("QuotaExceededError");
    },
  };
  assert.equal(docNhoGap("x", hong), null);
  assert.doesNotThrow(() => ghiNhoGap("x", true, hong));
  assert.equal(docNhoGap("x", null), null);
  assert.doesNotThrow(() => ghiNhoGap("x", true, null));
  assert.equal(docNhoGap("", kho), null);
});

test("nhomThuThuat: chia nhóm theo máy chủ, giữ thứ tự; thiếu nhóm → nhóm mặc định", () => {
  const tt = (ma: string, nhan: string, nhom?: string | null, form: string | null = null): ThuThuatNguon => ({
    ma,
    nhan,
    nhom,
    form_id_ket_qua: form,
    service_code: `CLS_${ma}`,
    gia: 1000,
  });
  const ds = [
    tt("p1", "Đặt vòng nội tiết", "Thủ thuật"),
    tt("p16", "Yếu cơ", "Sàn chậu — trải nghiệm 5 phút ghế ĐTT"),
    tt("p9", "Nong bao quy đầu ÂV", "Thủ thuật"),
    tt("p11", "Biofeedback", "Sàn chậu — định hướng điều trị", "KQ_X"),
  ];
  const r = nhomThuThuat(ds);
  assert.deepEqual(
    r.map((n) => [n.nhom, n.muc.map((m) => m.nhan)]),
    [
      ["Thủ thuật", ["Đặt vòng nội tiết", "Nong bao quy đầu ÂV"]],
      ["Sàn chậu — trải nghiệm 5 phút ghế ĐTT", ["Yếu cơ"]],
      ["Sàn chậu — định hướng điều trị", ["Biofeedback"]],
    ],
  );
  assert.equal(r[2].muc[0].cach_tra_ket_qua, "Có biểu mẫu");
  assert.equal(r[0].muc[0].cach_tra_ket_qua, "");
  assert.equal(r[0].muc[0].service_code, "CLS_p1");
  assert.equal(r[0].muc[0].gia, 1000);
  // Máy chủ bản cũ (không có `nhom`) → một nhóm như trước.
  assert.deepEqual(
    nhomThuThuat([tt("a", "A"), tt("b", "B", "  ")]).map((n) => [n.nhom, n.muc.length]),
    [[NHOM_THU_THUAT_MAC_DINH, 2]],
  );
  // Rác → rỗng / bỏ dòng hỏng, không ném.
  assert.deepEqual(nhomThuThuat(null), []);
  assert.deepEqual(nhomThuThuat(undefined), []);
  assert.deepEqual(nhomThuThuat([null as unknown as ThuThuatNguon, { ma: "x" } as ThuThuatNguon]), []);
});

// Đối tác tự thu (27/09/2026): nút "Chỉ định N mục · tổng" ở bàn khám chỉ cộng
// phần phòng khám — mục khách trả trực tiếp đối tác (cờ máy chủ) không cộng.
test("tongPhongKham bỏ mục đối tác tự thu và mục chưa có giá", () => {
  const muc = [
    { nhan: "Khám", cach_tra_ket_qua: "", form_id_ket_qua: null, service_code: "KHAM", gia: 250000 },
    {
      nhan: "HPV",
      cach_tra_ket_qua: "",
      form_id_ket_qua: null,
      service_code: "HPV",
      gia: 900000,
      doi_tac_thu: true,
    },
    { nhan: "Chưa giá", cach_tra_ket_qua: "", form_id_ket_qua: null, service_code: "X", gia: null },
    { nhan: "Không mã", cach_tra_ket_qua: "", form_id_ket_qua: null, service_code: null, gia: 5 },
  ];
  assert.equal(tongPhongKham(["KHAM", "HPV"], muc), 250000);
  assert.equal(tongPhongKham(["HPV"], muc), 0);
  assert.equal(tongPhongKham(["X", "KHONG_CO"], muc), 0);
  assert.equal(tongPhongKham([], muc), 0);
});

// Sắp lại khối 3/4 (08/10): một chỉ định không bao giờ ra hai thẻ. Điều trị theo
// cờ máy chủ `dieu_tri`, xét TRƯỚC danh mục thủ thuật.
test("phanChiDinh: điều trị theo cờ máy chủ, một chỉ định một chỗ", () => {
  const cd = (service_code: string, dieu_tri?: boolean) =>
    ({ service_order_id: service_code, service_code, dieu_tri }) as unknown as ChiDinhVaKetQua;
  const gheDien = cd("CLS_GHE_DTT", true); // vừa ở danh mục thủ thuật vừa là điều trị
  const laser = cd("LASER_TIEN_DINH", true); // điều trị, KHÔNG ở danh mục thủ thuật
  const datVong = cd("TT_DAT_VONG");
  const sieuAm = cd("SA_2D");
  const maTT = new Set(["CLS_GHE_DTT", "TT_DAT_VONG"]);
  const ra = phanChiDinh([sieuAm, gheDien, datVong, laser], maTT);
  assert.deepEqual(ra.dieuTri, [gheDien, laser]);
  assert.deepEqual(ra.thuThuat, [datVong]);
  assert.deepEqual(ra.cls, [sieuAm]);
  // Chưa nạp danh mục thủ thuật: điều trị vẫn đúng chỗ, phần còn lại về CLS.
  const chuaNap = phanChiDinh([gheDien, datVong]);
  assert.deepEqual(chuaNap.dieuTri, [gheDien]);
  assert.deepEqual(chuaNap.cls, [datVong]);
  assert.deepEqual(phanChiDinh([], maTT), { dieuTri: [], thuThuat: [], cls: [] });
});
