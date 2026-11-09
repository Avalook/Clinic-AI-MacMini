#!/usr/bin/env node
// Dựng dữ liệu demo cho video "Việc của đối tác" — BẰNG CHÍNH API CỦA APP (không INSERT tay).
// Chạy lại lần nào cũng ra cùng trạng thái đầu chương:
//   - chưa có việc demo HÔM NAY ⇒ tạo: khách → lịch hẹn → check-in → bác sĩ chỉ định;
//   - đã có ⇒ đưa việc về đúng trạng thái bằng lệnh bù của bàn (huỷ mẫu, huỷ ghi nhận thu,
//     lý do "Dựng lại video hướng dẫn") — hoàn tác được, như nhân viên bấm.
// Chỉ chạy với stack local (api.mjs từ chối địa chỉ không phải loopback).
//
//   node scripts/video-huong-dan/dung-du-lieu.mjs

import { cho, goi } from "./api.mjs";

const LY_DO = "Dựng lại video hướng dẫn";
export const DOI_TAC = {
  ten: "Medlatec",
  ma_ngan: "MED",
  hen: 3,
  // Chuỗi MẪU rõ là giả — chỉ để dòng "Chuyển khoản vào: …" có chữ trên hình.
  tk: "Ngân hàng mẫu · 0000 0000 00 · TÀI KHOẢN MẪU",
};
//: Dịch vụ đối tác có sẵn ở danh mục local (bên thu = đối tác) + giá gợi ý trên hình.
export const DICH_VU = [
  { ma: "CLS_HPV", gia: 350000 },
  { ma: "CLS_THINPREP", gia: 550000 },
];
//: Khách giả, rõ là giả. `trang_thai`: trạng thái việc lúc bắt đầu quay.
export const KHACH = [
  { ten: "Nguyễn Thị Minh Anh", sdt: "0900000101", nam_sinh: 1992, trang_thai: "chua_thu" },
];

const log = (...a) => console.log("  ·", ...a);

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
  return d.id;
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
  const bat = new Date(Math.ceil((Date.now() + 20 * 60_000) / 900_000) * 900_000);
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

/** Đưa việc về trạng thái đầu chương bằng lệnh bù của bàn XN. */
async function veTrangThai(viec, trangThai) {
  for (const v of viec) {
    if (v.mau_id) {
      await goi("ql", "POST", "xet-nghiem/ban/huy-mau", { mau_id: v.mau_id, loai: "NHAP_SAI", ly_do: LY_DO });
      log(`huỷ mẫu ${v.ten_dich_vu}`);
    }
    if (v.thu_id && trangThai === "chua_thu") {
      await goi("ql", "POST", "xet-nghiem/ban/huy-thu", { order_id: v.order_id, ly_do: LY_DO });
      log(`huỷ ghi nhận thu ${v.ten_dich_vu}`);
    }
  }
}

export async function dungDuLieu() {
  console.log("Dựng dữ liệu demo (stack local):");
  await doiTac();
  for (const k of KHACH) {
    let viec = await viecHomNay(k.sdt);
    if (viec.length < DICH_VU.length) {
      const bn = await taoKhach(k);
      await chiDinh(await luotMoi(k, bn));
      viec = await viecHomNay(k.sdt);
      log(`${k.ten}: ${viec.length} việc mới`);
    }
    await veTrangThai(viec, k.trang_thai);
    const sau = await viecHomNay(k.sdt);
    log(`${k.ten}: ${sau.map((v) => `${v.ten_dich_vu} = ${v.trang_thai.nhan ?? v.trang_thai.ma}`).join(" · ")}`);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  dungDuLieu().catch((e) => {
    console.error(`\nDỰNG DỮ LIỆU HỎNG: ${e.message}`);
    process.exit(1);
  });
}
