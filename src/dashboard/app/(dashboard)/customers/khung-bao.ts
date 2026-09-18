// KHUNG BÁO DƯỚI TÊN KHÁCH — mọi thay đổi ảnh hưởng lịch của khách, một chỗ.
//
// Tuyền chốt 16/09/2026: *"trạng thái này sẽ hiện ngay bên dưới của [tên, mã,
// số điện thoại], ghi rõ là lịch lúc nào của bác sĩ nào… ngoài ra vị trí này
// cũng để báo vụ bị đổi lịch, nhắc cskh gọi lại cho khách vì còn 7 ngày nữa là
// đi khám / trước 1 ngày đi khám, có kết quả xét nghiệm gọi đi lấy hay bất kể 1
// thay đổi nào ảnh hưởng lịch của khách này"*.
//
// FILE NÀY KHÔNG SINH VIỆC. Việc nào tồn tại là do backend nói (`v_viec_cskh`
// qua `viec`, lời hẹn gọi lại, mốc nhắc tái khám, cờ mất bác sĩ tính ở
// page.tsx). Ở đây chỉ DỊCH những sự thật ấy thành câu người trực đọc được và
// xếp cái gấp lên trước. Thuần — không React, không I/O — để test bằng node.

export type MucBao = "gap" | "nhac";

export interface DongBao {
  /** Khoá ổn định cho React + test. */
  khoa: string;
  muc: MucBao;
  cau: string;
  /** Hành động khi bấm: mở sửa lịch, hoặc chọn một việc ở cột phải. */
  hanhDong?: { loai: "sua_lich" } | { loai: "chon_viec"; ma: string };
}

export interface DauVaoBao {
  homNay: string; // yyyy-mm-dd giờ VN
  luot: {
    id: string | null;
    slot_start: string | null;
    doctor_name?: string | null;
    mat_bac_si?: boolean;
    bs_go_co_ca_lai?: boolean;
    thu_thuat_xong_luc?: string | null;
    theo_doi_thu_thuat?: string | null;
    theo_doi_sau_ngay?: number | null;
  } | null;
  /** Việc đang mở của lượt đang xem (+ việc không gắn lượt). */
  viec: { trang_thai: string; qua_han: boolean; han_xu_ly: string | null }[];
  quanLyDoiGio: boolean;
  henGoiLai: { id: string; ngay_goi: string; gio_goi: string | null; ly_do: string }[];
  taiKham: { id: string; luot_goi: number; ngay_hen: string; han_goi: string; qua_han: boolean }[];
  nowMs: number;
}

function ngay(d: string): string {
  const [y, m, dd] = d.slice(0, 10).split("-");
  return dd && m ? `${dd}/${m}${y ? `/${y}` : ""}` : d;
}

function gioNgay(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

/** Số ngày giữa hai ngày yyyy-mm-dd (b − a). */
function cachNgay(a: string, b: string): number {
  return Math.round((Date.parse(b.slice(0, 10)) - Date.parse(a.slice(0, 10))) / 86_400_000);
}

export function dungKhungBao(v: DauVaoBao): DongBao[] {
  const ra: DongBao[] = [];
  const coViec = (ma: string) => v.viec.find((x) => x.trang_thai === ma);
  const l = v.luot;
  const lich = l?.slot_start
    ? `Lịch ${gioNgay(l.slot_start)}${l.doctor_name ? ` với ${l.doctor_name}` : ""}`
    : "Lịch của khách";

  if (coViec("VUOT_SUC_CHUA")) {
    ra.push({
      khoa: "VUOT_SUC_CHUA",
      muc: "gap",
      cau: `${lich} vượt sức chứa — ca đã đủ số lượng khám. Bấm để đặt lịch khác thay lịch này.`,
      hanhDong: { loai: "sua_lich" },
    });
  }
  if (l?.mat_bac_si) {
    ra.push({
      khoa: "MAT_BAC_SI",
      muc: "gap",
      cau: l.bs_go_co_ca_lai
        ? `${lich}: ca bác sĩ đã xếp lại — gọi khách, đặt lại đúng khung nếu còn chỗ.`
        : `${lich}: bác sĩ đã đổi lịch làm việc — gọi khách đổi lịch.`,
      hanhDong: { loai: "sua_lich" },
    });
  }
  if (v.quanLyDoiGio) {
    ra.push({
      khoa: "QUAN_LY_DOI_GIO",
      muc: "gap",
      cau: `${lich}: quản lý đã đổi giờ so với giờ hẹn ban đầu — gọi báo khách.`,
    });
  }
  const kqGui = coViec("KQ_CHUA_GUI");
  if (kqGui) {
    ra.push({
      khoa: "KQ_CHUA_GUI",
      muc: "gap",
      cau: "Có kết quả xét nghiệm bác sĩ đã cho phép gửi — gửi / gọi khách lấy kết quả.",
      hanhDong: { loai: "chon_viec", ma: "KQ_CHUA_GUI" },
    });
  }
  const kqMuon = coViec("CHO_KQ_XN");
  if (kqMuon?.qua_han) {
    ra.push({
      khoa: "CHO_KQ_XN",
      muc: "gap",
      cau: "Kết quả xét nghiệm về muộn quá hạn — hỏi đơn vị xét nghiệm.",
      hanhDong: { loai: "chon_viec", ma: "CHO_KQ_XN" },
    });
  }
  const xacNhan = coViec("CHO_XAC_NHAN");
  if (xacNhan && l?.slot_start) {
    const con = cachNgay(v.homNay, l.slot_start);
    ra.push({
      khoa: "CHO_XAC_NHAN",
      muc: xacNhan.qua_han ? "gap" : "nhac",
      cau: `Còn ${Math.max(con, 0)} ngày tới ${lich.toLowerCase()} — gọi xác nhận lịch.`,
    });
  }
  if (coViec("NHAC_HEN_MAI") && l?.slot_start) {
    ra.push({
      khoa: "NHAC_HEN_MAI",
      muc: "nhac",
      cau: `Ngày mai (${ngay(l.slot_start)}) khách có lịch — gọi nhắc khách.`,
      hanhDong: { loai: "chon_viec", ma: "NHAC_HEN_MAI" },
    });
  }
  for (const h of v.henGoiLai) {
    if (h.ngay_goi > v.homNay) continue;
    ra.push({
      khoa: `HEN_${h.id}`,
      muc: h.ngay_goi < v.homNay ? "gap" : "nhac",
      cau: `Tới hạn gọi lại khách ${h.gio_goi ? `${h.gio_goi.slice(0, 5)} ` : ""}ngày ${ngay(h.ngay_goi)} — ${h.ly_do}`,
    });
  }
  for (const t of v.taiKham) {
    if (!t.qua_han && t.han_goi > v.homNay) continue;
    ra.push({
      khoa: `TK_${t.id}`,
      muc: t.qua_han ? "gap" : "nhac",
      cau: `${t.luot_goi === 1 ? "Gọi mời tái khám" : "Gọi nhắc đi khám"} — hẹn quay lại ${ngay(t.ngay_hen)}.`,
    });
  }
  if (l?.theo_doi_thu_thuat === "CAN" && l.thu_thuat_xong_luc && l.theo_doi_sau_ngay) {
    const han = Date.parse(l.thu_thuat_xong_luc) + l.theo_doi_sau_ngay * 86_400_000;
    const conMs = han - v.nowMs;
    if (conMs <= 86_400_000) {
      ra.push({
        khoa: "THEO_DOI_THU_THUAT",
        muc: conMs <= 0 ? "gap" : "nhac",
        cau: `${conMs <= 0 ? "Quá hạn" : "Tới hạn"} gọi hỏi thăm sau thủ thuật (hạn ${gioNgay(new Date(han).toISOString())}).`,
      });
    }
  }
  // Gấp trước, nhắc sau — giữ thứ tự nguồn trong cùng mức.
  return [...ra.filter((d) => d.muc === "gap"), ...ra.filter((d) => d.muc === "nhac")];
}
