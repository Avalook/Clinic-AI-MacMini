"use client";

// Bộ ô nhập công ty xuất hoá đơn (G5c) — DÙNG CHUNG cho khối trên phiếu thu
// (`CongTyHoaDon`) và khối trong hồ sơ khách (`CongTyKhach`). Chỉ vẽ ô; luật (MST chỉ
// nhắc, độ dài, trùng) ở máy chủ.

import ONhap from "@/components/ui/ONhap";

export type CongTy = {
  ten_cong_ty: string; dia_chi_cong_ty: string; ma_so_thue: string;
  email_nhan_hd: string; nguoi_mua: string;
};

export const CONG_TY_TRONG: CongTy = {
  ten_cong_ty: "", dia_chi_cong_ty: "", ma_so_thue: "", email_nhan_hd: "", nguoi_mua: "",
};

const O: { k: keyof CongTy; ten: string; goiY?: string }[] = [
  { k: "ten_cong_ty", ten: "Tên công ty" },
  { k: "ma_so_thue", ten: "Mã số thuế", goiY: "10 số, hoặc 10 số-001" },
  { k: "dia_chi_cong_ty", ten: "Địa chỉ công ty" },
  { k: "email_nhan_hd", ten: "Email nhận hoá đơn" },
  { k: "nguoi_mua", ten: "Người mua (không bắt buộc)", goiY: "Để trống thì ô người mua trong file cũng để trống" },
];

/** Chỉ lấy 5 trường công ty từ một đối tượng lớn hơn (id, mốc giờ…). */
export function sangForm(c: CongTy): CongTy {
  return {
    ten_cong_ty: c.ten_cong_ty, dia_chi_cong_ty: c.dia_chi_cong_ty, ma_so_thue: c.ma_so_thue,
    email_nhan_hd: c.email_nhan_hd, nguoi_mua: c.nguoi_mua,
  };
}

export default function FormCongTy({ form, onDoi }: { form: CongTy; onDoi: (f: CongTy) => void }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {O.map(o => (
        <label key={o.k} className="min-w-0 space-y-1 text-meta text-ink-muted">
          <span className="block">{o.ten}</span>
          <ONhap className="w-full" aria-label={o.ten} value={form[o.k] ?? ""}
            onChange={e => onDoi({ ...form, [o.k]: e.target.value })} />
          {o.goiY ? <span className="block text-meta text-ink-faint">{o.goiY}</span> : null}
        </label>
      ))}
    </div>
  );
}
