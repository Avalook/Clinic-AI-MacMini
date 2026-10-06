"use client";

// Lịch sử thay đổi lịch trực — kiểu "lịch sử phiên bản" của Google Docs (Khối 3,
// Tuyền 06/10/2026). Mọi phép tính (phiên bản nào, khác gì, ai sửa) do máy chủ
// làm — `GET /api/v1/roster/phien-ban`; ở đây chỉ còn kiểu dữ liệu và mảnh trình
// bày dùng chung.
//
// 06/10 tối (Tuyền): khối "Lịch sử thay đổi" riêng ĐÃ GỘP vào bảng "Đăng ký /
// xếp ca" (`RosterRegisterTable`) — ô Phiên bản nằm trên thanh công cụ dính của
// bảng, chọn bản cũ thì CHÍNH bảng xếp ca tô màu và chỉ xem; danh sách thay đổi
// của tuần ở ngăn "Xem các thay đổi", từng ô ở "Lịch sử ô này" trong popup.
//
// AI THẤY: máy chủ quyết (cửa `roster.manage` / `config.clinic.manage` — trưởng
// ca và quản lý). Không được xem → trang nhận `null` → không bày ô Phiên bản.

import Chip from "../../../components/ui/Chip";
import { fmtDateTime } from "../../../lib/datetime";
import { doctorName } from "../../../lib/doctor-name";
import { SHIFT_LABEL, dayShort, fmtDayMonth } from "../../../lib/roster";
import type { LoaiThayDoi } from "../home/WorkRosterTable";

export interface SoThayDoi {
  them: number;
  xoa: number;
  doi_nguoi: number;
}

export interface MucPhienBan {
  ma: string;
  loai: "GOC" | "AP_DUNG_LAI" | "LEN_BAN" | "THAY_DOI";
  luc: string | null;
  boi_ten: string | null;
  so: SoThayDoi;
}

export interface OPhienBan {
  id: string;
  work_date: string;
  shift: string;
  station: string;
  staff_id: string | null;
  staff_name: string | null;
  ten_chuan: string | null;
  vai: string;
  vai_ngan: string;
  thay_doi: LoaiThayDoi | null;
  truoc_ten: string | null;
}

/** Một lần thêm / xoá / đổi người ở một ô (ngày × ca × vị trí). */
export interface DongNhatKy {
  ma: string;
  loai_ban: MucPhienBan["loai"];
  luc: string | null;
  boi_ten: string | null;
  loai: LoaiThayDoi;
  roster_id: string;
  work_date: string;
  shift: string;
  station: string;
  ten: string | null;
  truoc_ten: string | null;
}

export interface PhienBanTraVe {
  tuan: string | null;
  co_lich_su: boolean;
  da_ap_dung: boolean;
  lich_su_tu: string | null;
  phien_ban: MucPhienBan[];
  dang_xem:
    | (MucPhienBan & {
        moi_nhat: boolean;
        truoc_ma: string | null;
        dong: OPhienBan[];
        da_xoa: OPhienBan[];
      })
    | null;
  /** Mọi lần thêm / xoá / đổi người của tuần, mới nhất trước. */
  nhat_ky?: DongNhatKy[];
}

const NHAN_LOAI: Record<MucPhienBan["loai"], string> = {
  GOC: "Lịch gốc (áp dụng tuần)",
  AP_DUNG_LAI: "Áp dụng lại",
  LEN_BAN: "Lịch lúc bắt đầu ghi lịch sử",
  THAY_DOI: "Sửa lịch",
};

function tomTat(so: SoThayDoi): string {
  const phan = [
    so.doi_nguoi ? `đổi người ${so.doi_nguoi}` : "",
    so.xoa ? `xoá ${so.xoa}` : "",
    so.them ? `thêm ${so.them}` : "",
  ].filter(Boolean);
  return phan.join(" · ");
}

const tenNguoi = (t: string | null | undefined) => (t ? doctorName(t) || t : "");

/** Nhãn một phiên bản trong ô chọn: giờ · loại / tóm tắt · người sửa. */
export function nhanMuc(p: MucPhienBan, moiNhat: boolean): string {
  const tt = p.loai === "THAY_DOI" ? tomTat(p.so) : NHAN_LOAI[p.loai];
  const ai = tenNguoi(p.boi_ten) || "không rõ người sửa";
  return `${fmtDateTime(p.luc)} · ${tt || NHAN_LOAI[p.loai]} · ${ai}${moiNhat ? " (mới nhất)" : ""}`;
}

/** Tên hiển thị của một ô ở phiên bản: tên chuẩn theo staff_id, rơi về chuỗi cũ. */
export const tenHien = (o: OPhienBan) =>
  (o.staff_id && doctorName(o.ten_chuan)) || o.staff_name || "";

/** Đọc một phiên bản (`ma` rỗng = mới nhất). Lỗi → chuỗi báo lỗi đọc được. */
export async function taiPhienBan(
  tuan: string,
  ma?: string | null,
): Promise<PhienBanTraVe | string> {
  try {
    const q = new URLSearchParams({ phien_ban: tuan });
    if (ma) q.set("ban", ma);
    const res = await fetch(`/api/roster?${q}`, { cache: "no-store" });
    if (!res.ok) return `Không đọc được phiên bản (lỗi ${res.status}).`;
    return (await res.json()) as PhienBanTraVe;
  } catch {
    return "Mất kết nối — thử chọn lại.";
  }
}

const TONE_LOAI = { THEM: "success", XOA: "danger", DOI_NGUOI: "info" } as const;
const CHU_LOAI: Record<LoaiThayDoi, string> = {
  THEM: "Thêm",
  XOA: "Xoá",
  DOI_NGUOI: "Đổi người",
};

/** Chú thích ba màu — cùng token với ô tô màu (`MAU_THAY_DOI`). */
export function ChuThichMau() {
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <Chip tone="success">+ Thêm</Chip>
      <Chip tone="info">Đổi: cũ → mới</Chip>
      <Chip tone="danger">
        <span className="line-through">Xoá</span>
      </Chip>
    </span>
  );
}

/**
 * Danh sách thay đổi (mới nhất trước). `nhan` = mã vị trí → tên hiển thị;
 * `boO` = bỏ phần "ngày · ca · vị trí" khi đã đứng trong popup của đúng ô ấy.
 * `onXemBan` có thì giờ mỗi dòng là nút mở phiên bản ấy trên bảng.
 */
export function DanhSachThayDoi({
  nhatKy,
  nhan,
  boO = false,
  dangXemMa = null,
  onXemBan,
}: {
  nhatKy: DongNhatKy[];
  nhan: Record<string, string>;
  boO?: boolean;
  dangXemMa?: string | null;
  onXemBan?: (ma: string) => void;
}) {
  return (
    <ul className="space-y-1.5">
      {nhatKy.map((n, i) => (
        <li
          key={`${n.ma}-${n.roster_id}-${n.loai}-${i}`}
          className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-body text-ink"
        >
          <Chip tone={TONE_LOAI[n.loai]}>{CHU_LOAI[n.loai]}</Chip>
          {boO ? null : (
            <span className="text-ink-muted">
              {dayShort(n.work_date)} {fmtDayMonth(n.work_date)} ·{" "}
              {SHIFT_LABEL[n.shift as keyof typeof SHIFT_LABEL] ?? n.shift} ·{" "}
              {nhan[n.station] ?? n.station}
            </span>
          )}
          <span className={n.loai === "XOA" ? "line-through" : undefined}>
            {n.loai === "DOI_NGUOI" && n.truoc_ten
              ? `${tenNguoi(n.truoc_ten)} → ${tenNguoi(n.ten)}`
              : tenNguoi(n.ten)}
            {boO && n.shift === "FULL" ? (
              <span className="text-ink-muted"> (cả ngày)</span>
            ) : null}
          </span>
          <span className="text-meta text-ink-muted">
            · {tenNguoi(n.boi_ten) || "không rõ người sửa"} ·{" "}
            {onXemBan ? (
              <button
                type="button"
                onClick={() => onXemBan(n.ma)}
                className="underline decoration-dotted underline-offset-2 hover:text-ink"
                aria-label={`Xem bảng lịch tại phiên bản ${fmtDateTime(n.luc)}`}
              >
                {fmtDateTime(n.luc)}
              </button>
            ) : (
              fmtDateTime(n.luc)
            )}
            {dangXemMa === n.ma ? " · bản đang xem" : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}
