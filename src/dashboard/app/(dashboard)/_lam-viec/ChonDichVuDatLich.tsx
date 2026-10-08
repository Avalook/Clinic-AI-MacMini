"use client";

/**
 * Ô CHỌN DỊCH VỤ khi đặt / sửa lịch — MỘT component cho mọi lối (Tuyền chốt
 * 07/10/2026, T0 của docs/KE-HOACH-CHON-DICH-VU-HO-SO-KHAM.md): Thêm khách hàng
 * (`NewPatientForm`), Đặt lịch (`BookingHub`), sửa / đặt lịch ở Quản lý khách
 * hàng (`AppointmentBooking`), popover Đổi dịch vụ khám (`ThaoTacLichTaiCho`).
 *
 * Bốn nhóm Khám · Điều trị · Thuốc (ẩn) · Khác do MÁY CHỦ gom
 * (`/api/catalog/dich-vu-dat-lich` → `services/dich_vu_dat_lich.py`); ở đây
 * không có luật nhóm nào — chỉ vẽ. "Khác" mang câu gợi ý ghi chú (không chặn lưu).
 */

import { useEffect, useState } from "react";
import ChipChon from "@/components/ui/ChipChon";

export interface MucDichVuDatLich {
  id: string;
  ten: string;
  /** Mã lĩnh vực trên hồ sơ khách (PK/SK/NT/HMVS/NK) — máy chủ suy từ phiếu. */
  linh_vuc?: string | null;
  /** Popover đổi dịch vụ: đang là dịch vụ của lịch. */
  hien_tai?: boolean;
  /** Popover đổi dịch vụ: chọn là máy chủ từ chối — câu ở `ghi_chu`. */
  chan?: boolean;
  ghi_chu?: string | null;
}

export interface NhomDichVuDatLich {
  ma: string;
  ten: string;
  /** Câu gợi ý ghi chú (nhóm Khác) — KHÔNG bắt buộc. */
  goi_y_ghi_chu: string | null;
  dich_vu: MucDichVuDatLich[];
}

let napChung: Promise<NhomDichVuDatLich[] | null> | null = null;

/** Nạp một lần cho cả trang; lỗi thì lần sau nạp lại. */
function napNhom(): Promise<NhomDichVuDatLich[] | null> {
  if (!napChung) {
    napChung = fetch("/api/catalog/dich-vu-dat-lich", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((j: { nhom?: NhomDichVuDatLich[] } | null) => j?.nhom ?? null)
      .catch(() => null)
      .then((nhom) => {
        if (nhom === null) napChung = null;
        return nhom;
      });
  }
  return napChung;
}

/** Nhóm dịch vụ: `co` (đã có sẵn, vd popover) hoặc nạp từ máy chủ. */
export function useNhomDichVu(co?: NhomDichVuDatLich[]): {
  nhom: NhomDichVuDatLich[];
  loi: boolean;
  dangNap: boolean;
} {
  const [nap, setNap] = useState<NhomDichVuDatLich[] | null | undefined>(
    co ? co : undefined,
  );
  useEffect(() => {
    if (co) return;
    let huy = false;
    void napNhom().then((n) => {
      if (!huy) setNap(n);
    });
    return () => {
      huy = true;
    };
  }, [co]);
  const nhom = co ?? nap ?? [];
  return { nhom, loi: !co && nap === null, dangNap: !co && nap === undefined };
}

/** Mục + nhóm của một id dịch vụ (null nếu không có trong danh sách). */
export function timDichVu(
  nhom: NhomDichVuDatLich[],
  id: string,
): { muc: MucDichVuDatLich; nhom: NhomDichVuDatLich } | null {
  for (const n of nhom) {
    const muc = n.dich_vu.find((d) => d.id === id);
    if (muc) return { muc, nhom: n };
  }
  return null;
}

/** Ô chọn dạng danh sách thả (biểu mẫu đặt lịch). */
export default function ChonDichVuDatLich({
  value,
  onChange,
  className,
  ariaLabel = "Dịch vụ",
  id,
  nhom: co,
}: {
  value: string;
  onChange: (id: string, muc: MucDichVuDatLich | null) => void;
  /** Lớp của ô `select` (mỗi màn giữ đúng kiểu ô đang dùng). */
  className?: string;
  ariaLabel?: string;
  id?: string;
  nhom?: NhomDichVuDatLich[];
}) {
  const { nhom, loi, dangNap } = useNhomDichVu(co);
  return (
    <>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value, timDichVu(nhom, e.target.value)?.muc ?? null)}
        className={className}
        aria-label={ariaLabel}
      >
        <option value="">{dangNap ? "Đang tải dịch vụ…" : "— Chọn dịch vụ —"}</option>
        {nhom.map((n) => (
          <optgroup key={n.ma} label={n.ten}>
            {n.dich_vu.map((d) => (
              <option key={d.id} value={d.id} disabled={d.chan}>
                {d.ten}
              </option>
            ))}
          </optgroup>
        ))}
      </select>
      {loi ? (
        <span role="alert" className="text-label text-danger">
          Không tải được danh sách dịch vụ — tải lại trang.
        </span>
      ) : null}
    </>
  );
}

/** Câu gợi ý ghi chú của nhóm đang chọn (vd "Khác") — chỉ nhắc, không chặn. */
export function GoiYGhiChu({
  value,
  ghiChu,
  nhom: co,
}: {
  value: string;
  ghiChu: string;
  nhom?: NhomDichVuDatLich[];
}) {
  const { nhom } = useNhomDichVu(co);
  const goiY = timDichVu(nhom, value)?.nhom.goi_y_ghi_chu;
  if (!goiY || ghiChu.trim()) return null;
  return <p className="text-label text-warning">{goiY}</p>;
}

/** Dạng chip một-lựa-chọn theo nhóm (popover Đổi dịch vụ khám). */
export function ChonDichVuDatLichChip({
  nhom,
  ten,
  chon,
  onChon,
  disabled,
}: {
  nhom: NhomDichVuDatLich[];
  /** `name` của nhóm radio. */
  ten: string;
  /** Id đang chọn; null = chưa chạm (hiện dịch vụ hiện tại). */
  chon: string | null;
  onChon: (id: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-col gap-3">
      {nhom.map((n) => (
        <fieldset key={n.ma} className="flex flex-col gap-1.5" disabled={disabled}>
          <legend className="mb-1 text-meta font-semibold text-ink-muted">{n.ten}</legend>
          {n.dich_vu.map((x) => (
            <div key={x.id} className="flex flex-col gap-0.5">
              <ChipChon
                kieu="mot"
                ten={ten}
                chon={chon === null ? !!x.hien_tai : chon === x.id}
                disabled={disabled || x.chan}
                onDoi={() => onChon(x.id)}
              >
                {x.ten}
                {x.hien_tai ? <span className="text-meta text-ink-muted">· đang chọn</span> : null}
              </ChipChon>
              {x.ghi_chu ? (
                <span className={`pl-2 text-label ${x.chan ? "text-danger" : "text-warning"}`}>
                  {x.ghi_chu}
                </span>
              ) : null}
            </div>
          ))}
        </fieldset>
      ))}
    </div>
  );
}
