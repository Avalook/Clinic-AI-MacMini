// VIỆC TÁI KHÁM — một thẻ, dùng CHUNG ở khung khách (Quản lý khách hàng / Tiếp
// đón) và màn Nhắc tái khám (Tuyền 29/09/2026). Bác sĩ chỉ đặt NGÀY; trước hẹn
// 7 ngày máy chủ sinh việc cho CSKH gọi chốt giờ. Thẻ này CHỈ VẼ đủ những gì
// CSKH cần để gọi — mọi luật (hạn gọi, đã có lịch, bác sĩ bỏ hẹn) nằm ở
// `services/hen_tai_kham_service.py`, tình trạng là mã máy chủ trả.

import { Phone } from "lucide-react";

import { buttonClass } from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import { fmtDate } from "@/lib/datetime";

export interface ChiTietHen {
  visit_id: string;
  bac_si: string | null;
  loai_kham: string | null;
  ngay_kham: string | null;
  chan_doan: string | null;
  can_kiem_tra: string[];
  ghi_chu_bac_si: string | null;
  /** Lịch hẹn THẬT bác sĩ đã đặt ngay trên phiếu (02/10/2026) — CSKH gọi chốt
   *  giờ / phân bác sĩ cho lịch này thay vì đặt lịch mới. */
  lich_bac_si_dat?: {
    ngay: string;
    gio: string;
    den: string;
    bac_si: string | null;
  } | null;
}

/** Nhãn hiển thị cho mã tình trạng máy chủ tính (`hen_tai_kham_service.tinh_trang`). */
export const NHAN_TINH_TRANG: Record<string, [string, ChipTone]> = {
  CHUA_TOI_HAN: ["Chưa tới hạn gọi", "neutral"],
  CHO_GOI: ["Cần gọi chốt giờ", "warning"],
  DA_GOI: ["Đã gọi", "success"],
  DA_CO_LICH: ["Đã có lịch", "success"],
  DA_HUY: ["Bác sĩ bỏ hẹn", "neutral"],
  KHONG_CAN: ["Không cần", "neutral"],
};

export default function ViecTaiKham({
  ngayHen,
  hanGoi,
  tinhTrang,
  chiTiet,
  sdt,
  maKhach,
  coNut,
}: {
  ngayHen: string | null;
  hanGoi?: string | null;
  /** Mã máy chủ; không có (màn Nhắc tái khám chỉ nhận việc đang chờ) = CHO_GOI. */
  tinhTrang?: string;
  chiTiet: ChiTietHen | null;
  sdt?: string | null;
  maKhach?: string | null;
  /** Hiện [Gọi] + [Đặt lịch] — chỉ khi việc còn mở. */
  coNut: boolean;
}) {
  const [nhan, tone] = NHAN_TINH_TRANG[tinhTrang ?? "CHO_GOI"] ?? [tinhTrang ?? "", "neutral" as ChipTone];
  return (
    <div className="space-y-1.5 rounded-control border border-hairline bg-surface p-2.5 text-meta text-ink">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <span className="font-semibold tabular-nums">
          Hẹn tái khám {ngayHen ? fmtDate(ngayHen) : "—"}
        </span>
        <Chip tone={tone}>{nhan}</Chip>
        {tinhTrang === "CHUA_TOI_HAN" && hanGoi ? (
          <span className="text-ink-muted">gọi từ {fmtDate(hanGoi)}</span>
        ) : null}
      </div>
      {chiTiet ? (
        <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-0.5">
          <dt className="text-ink-muted">Bác sĩ hẹn</dt>
          <dd>{chiTiet.bac_si ?? "—"}</dd>
          <dt className="text-ink-muted">Lần trước</dt>
          <dd>
            {chiTiet.loai_kham ?? "—"}
            {chiTiet.ngay_kham ? ` · ${fmtDate(chiTiet.ngay_kham)}` : ""}
          </dd>
          <dt className="text-ink-muted">Chẩn đoán</dt>
          <dd>{chiTiet.chan_doan ?? "—"}</dd>
          <dt className="text-ink-muted">Kiểm tra lại</dt>
          <dd className="flex flex-wrap gap-1">
            {chiTiet.can_kiem_tra.length > 0
              ? chiTiet.can_kiem_tra.map((k) => (
                  <Chip key={k} tone="info">
                    {k}
                  </Chip>
                ))
              : "—"}
          </dd>
          {chiTiet.ghi_chu_bac_si ? (
            <>
              <dt className="text-ink-muted">Ghi chú BS</dt>
              <dd>{chiTiet.ghi_chu_bac_si}</dd>
            </>
          ) : null}
          {chiTiet.lich_bac_si_dat ? (
            <>
              <dt className="text-ink-muted">BS đã đặt lịch</dt>
              <dd className="tabular-nums">
                {chiTiet.lich_bac_si_dat.gio}–{chiTiet.lich_bac_si_dat.den} ·{" "}
                {fmtDate(chiTiet.lich_bac_si_dat.ngay)} ·{" "}
                {chiTiet.lich_bac_si_dat.bac_si ?? "Chưa phân bác sĩ"}
              </dd>
            </>
          ) : null}
        </dl>
      ) : null}
      {coNut ? (
        <div className="flex flex-wrap gap-2 pt-1">
          {sdt ? (
            <a href={`tel:${sdt}`} className={buttonClass("secondary", "sm")}>
              <Phone size={14} aria-hidden="true" />
              Gọi {sdt}
            </a>
          ) : null}
          {maKhach ? (
            <a
              href={`/appointments?bn=${encodeURIComponent(maKhach)}`}
              className={buttonClass("soft", "sm")}
            >
              Đặt lịch tái khám
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
