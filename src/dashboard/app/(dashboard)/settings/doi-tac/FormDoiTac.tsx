// (Client — chỉ `DoiTacView.tsx` dùng.) Form thêm / sửa một đối tác xét nghiệm. Chỉ
// gom ô; luật ô (mã ngắn, số ngày, link Drive, độ dài) ở máy chủ `o_nhap.doc_form_doi_tac`.

import type { ReactNode } from "react";

import Button from "@/components/ui/Button";
import ONhap from "@/components/ui/ONhap";

export interface FormDT {
  id: string | null;
  ten: string;
  ma_ngan: string;
  sdt: string;
  ghi_chu: string;
  drive_folder: string;
  tai_khoan_nhan_ck: string;
  hen_tra_so_ngay_mac_dinh: string;
}

export const TRONG: FormDT = {
  id: null,
  ten: "",
  ma_ngan: "",
  sdt: "",
  ghi_chu: "",
  drive_folder: "",
  tai_khoan_nhan_ck: "",
  hen_tra_so_ngay_mac_dinh: "",
};

function O({ nhan, rong, children }: { nhan: string; rong?: boolean; children: ReactNode }) {
  return (
    <label className={`flex flex-col gap-1 text-meta text-ink-soft ${rong ? "sm:col-span-2" : ""}`}>
      {nhan}
      {children}
    </label>
  );
}

export default function FormDoiTac({
  form,
  dang,
  onSua,
  onLuu,
  onThoi,
}: {
  form: FormDT;
  dang: boolean;
  onSua: (k: keyof FormDT, v: string) => void;
  onLuu: () => void;
  onThoi: () => void;
}) {
  return (
    <div className="space-y-3 rounded-card border border-line bg-surface p-4 shadow-card">
      <p className="text-emph font-semibold text-ink">{form.id ? "Sửa đối tác" : "Thêm đối tác"}</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <O nhan="Tên đối tác">
          <ONhap value={form.ten} maxLength={120} placeholder="vd Medlatec" onChange={(e) => onSua("ten", e.target.value)} />
        </O>
        <O nhan="Mã ngắn (2–10 chữ/số)">
          <ONhap value={form.ma_ngan} maxLength={10} placeholder="vd MED" onChange={(e) => onSua("ma_ngan", e.target.value)} />
        </O>
        <O nhan="Hẹn trả mặc định (ngày)">
          <ONhap
            value={form.hen_tra_so_ngay_mac_dinh}
            inputMode="numeric"
            maxLength={2}
            onChange={(e) => onSua("hen_tra_so_ngay_mac_dinh", e.target.value)}
          />
        </O>
        <O nhan="Số điện thoại">
          <ONhap value={form.sdt} maxLength={30} inputMode="tel" onChange={(e) => onSua("sdt", e.target.value)} />
        </O>
        <O nhan="Tiền thu hộ chuyển khoản vào (ngân hàng · số tài khoản · tên)" rong>
          <ONhap
            value={form.tai_khoan_nhan_ck}
            maxLength={200}
            placeholder="vd Vietcombank · 0123456789 · CONG TY MEDLATEC"
            onChange={(e) => onSua("tai_khoan_nhan_ck", e.target.value)}
          />
        </O>
        <O nhan="Thư mục Google Drive của đối tác (dán link thư mục)" rong>
          <ONhap value={form.drive_folder} maxLength={1000} onChange={(e) => onSua("drive_folder", e.target.value)} />
        </O>
        <O nhan="Ghi chú" rong>
          <ONhap value={form.ghi_chu} maxLength={2000} onChange={(e) => onSua("ghi_chu", e.target.value)} />
        </O>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="primary" disabled={dang} onClick={onLuu}>
          {dang ? "Đang lưu…" : "Lưu"}
        </Button>
        <Button type="button" variant="ghost" onClick={onThoi}>
          Thôi
        </Button>
      </div>
    </div>
  );
}
