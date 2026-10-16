"use client";

// CỘT "PHẢN HỒI THUỐC" của bảng Danh sách khách hàng (16/10/2026).
// Tuyền: "phản hồi chỉ hiện trong khung chi tiết, chưa hiện thành một cột trong
// bảng danh sách khách — cho ra chỗ dễ nhìn thì tốt". Một ô: số phản hồi · ngày
// gần nhất, dưới là nội dung rút gọn (máy chủ cắt ~40 ký tự); rê chuột / chạm
// giữ thấy đủ. Khách chưa có phản hồi thì để trống — không chữ "không có".
// Chữ trung tính: phản hồi sau dùng thuốc là việc BÌNH THƯỜNG, không phải cảnh báo.
// Mọi con số/chữ rút gọn do `man_khach_hang_service.tom_tat_phan_hoi_thuoc` tính;
// ở đây chỉ vẽ.

import Chip from "@/components/ui/Chip";
import { fmtDate } from "@/lib/datetime";

import { NHAN_KENH } from "../_lam-viec/PhanHoiThuocKhach";

/** Một dòng tóm tắt theo khách — hình của `tom_tat_phan_hoi_thuoc` (backend). */
export interface TomTatPhanHoiThuoc {
  clinic_patient_id: string;
  so_phan_hoi: number;
  /** Lúc ghi phản hồi gần nhất (ISO). */
  luc: string | null;
  kenh: string | null;
  /** Nội dung rút gọn ~40 ký tự (máy chủ cắt). */
  tom_tat: string | null;
  /** Nội dung đủ (máy chủ cắt 400 ký tự) — cho tooltip. */
  noi_dung: string | null;
}

/** Ô của một khách; `tt` undefined = không có phản hồi → ô trống. */
export default function PhanHoiThuocCot({ tt }: { tt: TomTatPhanHoiThuoc | undefined }) {
  if (!tt || tt.so_phan_hoi < 1) return null;
  const kenh = tt.kenh ? (NHAN_KENH[tt.kenh] ?? tt.kenh) : null;
  const ngay = tt.luc ? fmtDate(tt.luc) : null;
  const tieuDe =
    `Phản hồi gần nhất${ngay ? ` ${ngay}` : ""}${kenh ? ` · ${kenh}` : ""}` +
    (tt.noi_dung ? `: ${tt.noi_dung}` : "");
  return (
    <div className="min-w-0" title={tieuDe} data-cot="phan-hoi-thuoc">
      <div className="flex min-w-0 flex-wrap items-center gap-1">
        <Chip tone="neutral">{tt.so_phan_hoi} phản hồi</Chip>
        {ngay ? <span className="text-meta text-ink-muted">{ngay}</span> : null}
      </div>
      {tt.tom_tat ? (
        <span className="mt-0.5 block truncate text-meta text-ink-soft">{tt.tom_tat}</span>
      ) : null}
    </div>
  );
}
