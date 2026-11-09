#!/usr/bin/env node
// Dựng dữ liệu demo cho video "Việc của đối tác" — BẰNG CHÍNH API CỦA APP (không INSERT tay).
// Chạy lại lần nào cũng ra cùng trạng thái đầu chương:
//   - chưa có việc demo HÔM NAY ⇒ tạo: khách → lịch hẹn → check-in → bác sĩ chỉ định;
//   - đã có ⇒ đưa việc về đúng trạng thái bằng lệnh bù của bàn (huỷ mẫu, huỷ ghi nhận thu,
//     lý do "Dựng lại video hướng dẫn") rồi ghi thu lại nếu chương cần — như nhân viên bấm.
// Chỉ chạy với stack local (api.mjs từ chối địa chỉ không phải loopback).
//
//   node scripts/video-huong-dan/dung-du-lieu.mjs            # mọi chương
//   node scripts/video-huong-dan/dung-du-lieu.mjs --chuong 3 # chỉ thứ chương 3 cần

import { cho, goi } from "./api.mjs";

const LY_DO = "Dựng lại video hướng dẫn";
export const DOI_TAC = {
  ten: "Medlatec",
  ma_ngan: "MED",
  hen: 3,
  // Chuỗi MẪU rõ là giả — chỉ để dòng "Chuyển khoản vào: …" có chữ trên hình.
  tk: "Ngân hàng mẫu · 0000 0000 00 · TÀI KHOẢN MẪU",
};
//: Đối tác chương 1 THÊM MỚI trên hình. Lần quay trước để lại ⇒ đổi mã + ngưng (không có Xoá).
export const DOI_TAC_MOI = { ten: "Phòng xét nghiệm Mẫu", ma_ngan: "PXN", dich_vu: "Tổng phân tích nước tiểu" };
//: Dịch vụ đối tác có sẵn ở danh mục local (bên thu = đối tác) + giá gợi ý trên hình.
export const DICH_VU = [
  { ma: "CLS_HPV", gia: 350000, khop: /hpv/i },
  { ma: "CLS_THINPREP", gia: 550000, khop: /thinprep/i },
];
const DA_THU_CA_HAI = {
  CLS_HPV: { tien_mat: "350000" },
  CLS_THINPREP: { chuyen_khoan: "550000", ma_giao_dich: "FT26110900456" },
};
//: Khách giả, rõ là giả. `dau`: khoản thu từng xét nghiệm lúc bắt đầu quay (thiếu = chưa thu).
//: `ds` (nhiều khách): chương có bước KHÔNG hoàn tác được (Hoàn tiền thật — luật: đã hoàn thì
//: không huỷ ghi nhận) ⇒ mỗi lần quay trong ngày dùng khách kế tiếp chưa bị hoàn.
export const KHACH = {
  thu: { ds: [{ ten: "Nguyễn Thị Minh Anh", sdt: "0900000101", nam_sinh: 1992 }], dau: {} },
  lay_mau: { ds: [{ ten: "Lê Thị Ngọc Lan", sdt: "0900000103", nam_sinh: 1988 }], dau: { CLS_HPV: { tien_mat: "350000" } } },
  hoan: {
    ds: [
      { ten: "Trần Thị Thu Hà", sdt: "0900000111", nam_sinh: 1990 },
      { ten: "Phạm Thị Hồng Nhung", sdt: "0900000112", nam_sinh: 1987 },
      { ten: "Đỗ Thị Mai Phương", sdt: "0900000113", nam_sinh: 1994 },
      { ten: "Vũ Thị Thanh Hương", sdt: "0900000114", nam_sinh: 1991 },
      { ten: "Bùi Thị Lan Chi", sdt: "0900000115", nam_sinh: 1989 },
    ],
    dau: DA_THU_CA_HAI,
  },
};
//: Chương nào cần khách nào (khoá KHACH) + có đặt lại đối tác thêm mới không.
const CAN = { 0: ["lay_mau"], 1: ["doi_tac_moi"], 2: ["thu"], 3: ["hoan"], 4: ["lay_mau"] };

const log = (...a) => console.log("  ·", ...a);
const maCua = (v) => DICH_VU.find((d) => d.khop.test(v.ten_dich_vu ?? ""))?.ma;

async function doiTac() {
  const ds = await goi("ql", "GET", "xet-nghiem/doi-tac");
  let d = ds.doi_tac.find((x) => x.ma_ngan === DOI_TAC.ma_ngan);
  const than = {
    ten: DOI_TAC.ten,
    ma_ngan: DOI_TAC.ma_ngan,
    hen_tra_so_ngay_mac_dinh: DOI_TAC.hen,
    tai_khoan_nhan_ck: DOI_TAC.tk,
  };
  if (!d) {
    const moi = await goi("ql", "POST", "xet-nghiem/doi-tac", than);
    d = moi.doi_tac.find((x) => x.ma_ngan === DOI_TAC.ma_ngan);
    log(`tạo đối tác ${DOI_TAC.ten}`);
  } else if (d.tai_khoan_nhan_ck !== DOI_TAC.tk) {
    const moi = await goi("ql", "PUT", `xet-nghiem/doi-tac/${d.id}`, { ...than, sdt: d.sdt, ghi_chu: d.ghi_chu });
    d = moi.doi_tac.find((x) => x.ma_ngan === DOI_TAC.ma_ngan);
    log("đặt tài khoản nhận chuyển khoản mẫu");
  }
  const gia = await goi("ql", "GET", "service-prices?group=dich_vu");
  const dsGia = Array.isArray(gia) ? gia : (gia.items ?? gia.service_prices ?? gia.rows ?? []);
  for (const dv of DICH_VU) {
    const sp = dsGia.find((s) => s.service_code === dv.ma);
    if (!sp) throw new Error(`Danh mục local thiếu dịch vụ ${dv.ma}.`);
    const daGan = d.dich_vu?.some((g) => g.service_price_id === sp.id && g.mac_dinh && g.gia_hieu_luc === dv.gia);
    if (!daGan) {
      await goi("ql", "POST", "xet-nghiem/doi-tac-dich-vu", {
        doi_tac_id: d.id,
        service_price_id: sp.id,
        gia_goi_y: String(dv.gia),
        hen_tra_so_ngay: DOI_TAC.hen,
        mac_dinh: true,
      });
      log(`gán ${dv.ma} → ${DOI_TAC.ma_ngan}, gợi ý ${dv.gia}`);
    }
  }
}

/** Chương 1 thêm "Phòng xét nghiệm Mẫu" (PXN) trên hình. Lần quay trước còn ⇒ bỏ gán, đổi
 *  sang mã cũ, ngưng có lý do (không có Xoá; thẻ ngưng xếp cuối danh sách). */
async function datLaiDoiTacMoi() {
  const ds = await goi("ql", "GET", "xet-nghiem/doi-tac");
  const d = ds.doi_tac.find((x) => x.ma_ngan === DOI_TAC_MOI.ma_ngan);
  if (!d) return;
  for (const g of d.dich_vu ?? []) await goi("ql", "POST", `xet-nghiem/doi-tac-dich-vu/${g.id}/bo`, {});
  const maCu = `C${Date.now().toString(36).slice(-6).toUpperCase()}`;
  await goi("ql", "PUT", `xet-nghiem/doi-tac/${d.id}`, {
    // Tên cũ KHÔNG chứa tên mới — kịch bản tìm thẻ theo tên "Phòng xét nghiệm Mẫu".
    ten: `Bản quay cũ ${maCu}`,
    ma_ngan: maCu,
    sdt: d.sdt,
    ghi_chu: d.ghi_chu,
    tai_khoan_nhan_ck: d.tai_khoan_nhan_ck,
    hen_tra_so_ngay_mac_dinh: d.hen_tra_so_ngay_mac_dinh,
  });
  if (!d.ngung_luc) await goi("ql", "POST", `xet-nghiem/doi-tac/${d.id}/ngung`, { ngung: true, ly_do: LY_DO });
  log(`đối tác ${DOI_TAC_MOI.ma_ngan} lần quay trước → ${maCu}, đã ngưng`);
}

async function viecHomNay(sdt) {
  const ban = await goi("ql", "GET", "xet-nghiem/ban");
  const homNay = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date());
  return ban.viec.filter((v) => v.sdt === sdt && v.ngay_chi_dinh === homNay && !v.trang_thai.ma.includes("HUY"));
}

async function taoKhach(k) {
  // Cơ sở = cơ sở của lễ tân (stack local có cơ sở đã ngừng hoạt động).
  const me = await goi("letan", "GET", "me");
  const p = await goi("letan", "POST", "patients", {
    full_name: k.ten,
    phone_primary: k.sdt,
    birth_year: k.nam_sinh,
    gender: "FEMALE",
    location_id: me.location_id,
  });
  return p.duplicate ? p.matches[0] : p;
}

async function luotCua(k) {
  const bang = await goi("bs.a", "GET", "luot-kham/bang");
  return (bang.luot ?? []).find((l) => l.sdt === k.sdt && !l.ket_thuc_luc);
}

/** Phiên bác sĩ chính của lượt đang mở; lượt còn ở Tư vấn thì đi nốt bằng API. */
async function phienBacSi(k) {
  for (let i = 0; i < 40; i++) {
    const l = await luotCua(k);
    const chinh = l?.phien?.find((x) => x.loai === "PRIMARY");
    if (chinh) return chinh.id;
    const tv = l?.phien?.find((x) => x.loai === "TU_VAN" && x.trang_thai !== "completed");
    if (tv && l.sinh_hieu_trang_thai === "pending") {
      await goi("dd.sa", "POST", `luot-kham/visits/${l.visit_id}/vitals/khong-do`, { ly_do: "TU_CHOI" });
    } else if (tv && tv.trang_thai === "queued") {
      await goi("bs.a", "POST", `luot-kham/consultations/${tv.id}/start`, undefined, { choPhep: [409] });
    } else if (tv && tv.trang_thai === "in_progress") {
      await goi("bs.a", "POST", `luot-kham/consultations/${tv.id}/xong-tu-van`, undefined, { choPhep: [409] });
    }
    await cho(1000);
  }
  throw new Error(`Không thấy phiên bác sĩ của ${k.ten} sau 40 giây — worker sự kiện có chạy không?`);
}

async function luotMoi(k, benhNhan) {
  if (await luotCua(k)) return phienBacSi(k);
  const loai = await goi("letan", "GET", "catalog/service-types");
  const dsLoai = Array.isArray(loai) ? loai : (loai.items ?? loai.service_types ?? []);
  // "Khác": vào thẳng bác sĩ chính (không qua tư vấn) — đủ để bác sĩ chỉ định xét nghiệm.
  const pk = dsLoai.find((t) => t.code === "KHAC");
  const bs = await goi("bs.a", "GET", "me");
  // Mỗi khách một khung giờ riêng (đuôi SĐT) — khỏi đụng sức chứa của cùng bác sĩ.
  const lech = (Number(k.sdt.slice(-2)) % 16) * 30 * 60_000;
  const bat = new Date(Math.ceil((Date.now() + 20 * 60_000) / 900_000) * 900_000 + lech);
  const lich = await goi(
    "cskh",
    "POST",
    "appointments/bookings",
    {
      clinic_patient_id: benhNhan.clinic_patient_id ?? benhNhan.id,
      service_type_id: pk.id,
      slot_start: bat.toISOString(),
      slot_end: new Date(bat.getTime() + 30 * 60_000).toISOString(),
      doctor_id: bs.staff_id ?? bs.id,
    },
    { idem: true },
  );
  const apptId = lich.appointment_id ?? lich.id ?? lich.appointment?.id;
  await goi("letan", "POST", "luot-kham/check-in", { appointment_id: apptId });
  log(`check-in ${k.ten}`);
  return phienBacSi(k);
}

async function chiDinh(phienId) {
  await goi("bs.a", "POST", `luot-kham/consultations/${phienId}/start`, undefined, { choPhep: [409] });
  await goi(
    "bs.a",
    "POST",
    `luot-kham/consultations/${phienId}/service-orders`,
    { service_codes: DICH_VU.map((d) => d.ma) },
    { idem: true },
  );
}

const khopThu = (v, m) =>
  Number(v.tien_mat ?? 0) === Number(m.tien_mat ?? 0) &&
  Number(v.chuyen_khoan ?? 0) === Number(m.chuyen_khoan ?? 0) &&
  (v.ma_giao_dich ?? "") === (m.ma_giao_dich ?? "");

/** Đưa việc về trạng thái đầu chương bằng lệnh bù của bàn XN, rồi ghi thu theo `dau`. */
async function veTrangThai(k, dau) {
  // Một ống có thể chung nhiều việc ⇒ huỷ mỗi mẫu MỘT lần.
  for (const mauId of new Set((await viecHomNay(k.sdt)).map((v) => v.mau_id).filter(Boolean))) {
    await goi("ql", "POST", "xet-nghiem/ban/huy-mau", { mau_id: mauId, loai: "NHAP_SAI", ly_do: LY_DO });
    log(`huỷ mẫu của ${k.ten}`);
  }
  for (const v of await viecHomNay(k.sdt)) {
    const muon = dau[maCua(v)];
    let coThu = !!v.thu_id;
    if (coThu && !(muon && khopThu(v, muon))) {
      await goi("ql", "POST", "xet-nghiem/ban/huy-thu", { order_id: v.order_id, ly_do: LY_DO });
      log(`huỷ ghi nhận thu ${v.ten_dich_vu}`);
      coThu = false;
    }
    if (!coThu && muon) {
      await goi("dd.sa", "POST", "xet-nghiem/ban/ghi-thu", {
        order_id: v.order_id,
        tien_mat: muon.tien_mat ?? "",
        chuyen_khoan: muon.chuyen_khoan ?? "",
        ma_giao_dich: muon.ma_giao_dich ?? "",
      });
      log(`ghi thu ${v.ten_dich_vu}`);
    }
  }
}

/** Khách đầu tiên trong `ds` chưa có việc nào hôm nay bị hoàn tiền (hoàn không bù được). */
async function chonKhach(ds) {
  for (const k of ds) {
    const viec = await viecHomNay(k.sdt);
    if (!viec.some((v) => Number(v.da_hoan ?? 0) > 0)) return { k, viec };
  }
  throw new Error("Hết khách mẫu chưa bị hoàn tiền hôm nay — thêm tên vào KHACH.hoan hoặc quay ngày khác.");
}

/** Dựng dữ liệu cho chương `so` (bỏ trống = mọi chương). Trả {khoá: tên khách} để kịch bản
 *  dùng `{khach_<khoá>}`. */
export async function dungDuLieu(so = null) {
  console.log("Dựng dữ liệu demo (stack local):");
  await doiTac();
  const can = new Set(so === null ? Object.values(CAN).flat() : (CAN[so] ?? []));
  if (can.has("doi_tac_moi")) await datLaiDoiTacMoi();
  const ten = {};
  for (const [khoa, nhom] of Object.entries(KHACH)) {
    if (!can.has(khoa)) continue;
    let { k, viec } = await chonKhach(nhom.ds);
    if (viec.length < DICH_VU.length) {
      const bn = await taoKhach(k);
      await chiDinh(await luotMoi(k, bn));
      viec = await viecHomNay(k.sdt);
      log(`${k.ten}: ${viec.length} việc mới`);
    }
    await veTrangThai(k, nhom.dau);
    const sau = await viecHomNay(k.sdt);
    log(`${k.ten}: ${sau.map((v) => `${v.ten_dich_vu} = ${v.trang_thai.nhan ?? v.trang_thai.ma}`).join(" · ")}`);
    ten[`khach_${khoa}`] = k.ten;
  }
  return ten;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const i = process.argv.indexOf("--chuong");
  dungDuLieu(i >= 0 ? Number(process.argv[i + 1]) : null).catch((e) => {
    console.error(`\nDỰNG DỮ LIỆU HỎNG: ${e.message}`);
    process.exit(1);
  });
}
