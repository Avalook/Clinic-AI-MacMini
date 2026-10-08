"use client";

// KHỐI "SẮP ĐẾN" — dây Nhận khách tại phòng (Tuyền chốt 07/10/2026,
// docs/KE-HOACH-NHAN-TAI-PHONG.md). Danh sách do máy chủ trả (`sap_den_phong`
// của hàng chờ phòng): MỌI khách check-in hôm nay chưa check-out ("ngu ngu tí
// nhưng pick ra dễ"), trừ khách đang chờ / làm ở chính phòng này. Máy chủ xếp:
// có chỉ định nhận được mà ★ / được hướng dẫn tới đây → có chỉ định nhận được
// → còn lại.
//
// MỖI KHÁCH ĐÚNG MỘT DÒNG GỌN (Tuyền chốt bố cục 07/10 tối): tên · mã · số ·
// "N chỉ định" · nhãn nơi đang ở. KHÔNG liệt kê từng chỉ định ở đây (3 chỉ định
// không được trông như 3 người, không vỡ chữ ở 375). Bấm dòng → khung bên phải
// liệt kê chỉ định + nút Nhận.

import Chip from "@/components/ui/Chip";
import SoLuot from "@/components/ui/SoLuot";
import { nhanBuoiCuaLuot, type ChipLieuTrinh } from "@/lib/lieu-trinh";

import { type ChiDinhPhong } from "../../_lam-viec/api";

export interface KhachSapDen {
  visit_id: string;
  khach: string | null;
  ma_khach: string | null;
  so_tiep_don: number | null;
  so_booking: number | null;
  duoc_huong_dan: boolean;
  /** Khách vào số "sắp đến" (có chỉ định chưa vào phòng nào mà phòng làm được). */
  tinh_so: boolean;
  so_chi_dinh: number;
  so_nhan_duoc: number;
  /** Câu máy chủ viết: khách đang ở đâu / "chưa có chỉ định ở phòng này". */
  dang_o: string | null;
  chi_dinh: ChiDinhPhong[];
}

export default function SapDenPhong({
  ds,
  chon,
  onChon,
  lieuTrinh = null,
}: {
  ds: KhachSapDen[];
  /** visit_id đang mở ở khung phải. */
  chon: string | null;
  onChon: (visitId: string) => void;
  /** Chip liệu trình của cả lô (08/10/2026) — chỉ thêm chữ vào dòng phụ. */
  lieuTrinh?: ChipLieuTrinh | null;
}) {
  if (ds.length === 0) return null;
  const soDem = ds.filter((k) => k.tinh_so).length;

  return (
    <section aria-label="Khách sắp đến phòng" className="space-y-1.5 rounded-card border border-info bg-info-bg p-2">
      <p className="px-1 text-meta font-semibold uppercase tracking-wide text-info">
        Sắp đến ({soDem})
        {ds.length > soDem ? (
          <span className="font-normal normal-case"> · +{ds.length - soDem} khách khác hôm nay</span>
        ) : null}
      </p>
      <ul className="space-y-1">
        {ds.map((k) => {
          const dangChon = k.visit_id === chon;
          const sao = k.chi_dinh.some((c) => c.nhan_duoc && c.chuyen);
          return (
            <li key={k.visit_id}>
              <button
                type="button"
                onClick={() => onChon(k.visit_id)}
                aria-pressed={dangChon}
                className={`flex w-full items-center gap-2 rounded-control border px-2 py-1.5 text-left ${
                  dangChon ? "border-brand-500 bg-brand-50" : "border-line bg-surface"
                }`}
              >
                <span
                  title="Số check-in"
                  className="grid size-7 shrink-0 place-items-center rounded-full bg-surface-sunken text-meta font-bold text-ink"
                >
                  {k.so_tiep_don ?? "—"}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1">
                    <span
                      className={`truncate text-sm font-semibold ${k.so_nhan_duoc > 0 ? "text-ink" : "text-ink-muted"}`}
                    >
                      {k.khach ?? "—"}
                    </span>
                    <SoLuot booking={k.so_booking} className="shrink-0" />
                  </span>
                  <span className="block truncate text-label text-ink-muted">
                    {[
                      k.ma_khach,
                      k.so_chi_dinh > 0 ? `${k.so_chi_dinh} chỉ định` : null,
                      nhanBuoiCuaLuot(lieuTrinh, k.visit_id, k.chi_dinh),
                      k.dang_o,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </span>
                </span>
                {k.duoc_huong_dan ? (
                  <Chip tone="info" className="shrink-0">
                    Hướng dẫn tới đây
                  </Chip>
                ) : sao ? (
                  <Chip tone="info" className="shrink-0">
                    ★
                  </Chip>
                ) : null}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
