// Lời báo "Đã mở lượt bán theo đơn khám … — N thuốc đã thêm / không thêm được: …"
// (16/10/2026, Tuyền bấm thử: bấm "Bán theo đơn này" xong không biết đơn đã nối
// hay chưa). KHÔNG phải toast: lời báo GIỮ trên khung lượt bán lẻ cho tới khi
// người dùng thao tác tiếp (thu, sửa giỏ, nối/gỡ đơn) hoặc bấm "Ẩn".
//
// Kho nhỏ trong bộ nhớ trang: người gửi (`LichSuDonThuoc`, lúc ở khung chọn
// khách — màn đang bị đóng lại) và người hiện (`BanLeThu`, mount sau khi màn
// chọn lượt) là hai component khác cây, kể cả khi đi từ /pharmacy/inventory
// sang /pharmacy bằng router.push (điều hướng trong app giữ nguyên bộ nhớ).
// Tải lại trang thì mất lời báo — chip "Đang bán theo đơn" vẫn còn vì nó đọc từ
// dữ liệu máy chủ.

import { useSyncExternalStore } from "react";

interface NoiDon {
  visitId: string;
  /** Nhiều dòng, ngăn bằng "\n". */
  cau: string;
}

let hienTai: NoiDon | null = null;
const nghe = new Set<() => void>();
const phat = () => nghe.forEach((f) => f());

export function baoNoiDon(visitId: string, cau: string): void {
  hienTai = { visitId, cau };
  phat();
}

export function anNoiDon(): void {
  if (!hienTai) return;
  hienTai = null;
  phat();
}

const dangKy = (f: () => void) => {
  nghe.add(f);
  return () => {
    nghe.delete(f);
  };
};

/** Lời báo đang giữ cho lượt này (null = không có). */
export function useNoiDon(visitId: string | null): string | null {
  const v = useSyncExternalStore(
    dangKy,
    () => hienTai,
    () => null,
  );
  return v && v.visitId === visitId ? v.cau : null;
}
