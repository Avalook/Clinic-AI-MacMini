// Thành tiền dòng thuốc ở màn kê đơn: MÁY CHỦ tính (`services/thuoc/gia_dong.py`, cùng
// hàm với hoá đơn và quầy thu — 26/11/2026). Màn chỉ giữ số máy chủ trả cho dòng ĐÃ
// LƯU; tệp này không tính tiền, chỉ biết khi nào số đang hiện đã cũ.

import { gopSoLuongQuayDien, type DongThuoc } from "./phieu-kham.ts";

/** Dòng vừa sửa số lượng / ĐVT: bỏ thành tiền cũ tới khi máy chủ trả số mới. */
export function boTienCu(d: DongThuoc, ma: keyof DongThuoc): DongThuoc {
  return ma === "so_luong" || ma === "don_vi" ? { ...d, thanh_tien: null } : d;
}

/** Đơn vừa nạp lại (sự kiện `prescription`): gộp số quầy điền (`gopSoLuongQuayDien`),
 *  rồi lấy đơn giá + thành tiền máy chủ cho dòng đang khớp bản đã lưu (cùng số, cùng
 *  ĐVT). Dòng bác sĩ đang gõ khác thì không đụng. null = không có gì đổi. */
export function gopTuMayChu(hienTai: DongThuoc[], may: DongThuoc[]): DongThuoc[] | null {
  const gop = gopSoLuongQuayDien(hienTai, may) ?? hienTai;
  let doi = gop !== hienTai;
  const ra = gop.map((d) => {
    const m = d.id ? may.find((x) => x.id === d.id) : undefined;
    if (!m || d.so_luong !== m.so_luong || d.don_vi !== m.don_vi) return d;
    if (d.thanh_tien === m.thanh_tien && d.don_gia === m.don_gia) return d;
    doi = true;
    return { ...d, don_gia: m.don_gia, thanh_tien: m.thanh_tien };
  });
  return doi ? ra : null;
}
