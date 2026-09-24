// KÊNH ĐẶT · NGƯỜI GIỚI THIỆU · LẦN ĐỔI / HUỶ LỊCH GẦN NHẤT (Tuyền 24/09/2026:
// "thông tin kênh đặt đã điền ở lần đặt lịch trước rồi (cái giới thiệu ấy) nó
// chưa được đồng bộ đến đây, cả ở danh sách bệnh nhân nữa" + "ở danh sách khách
// hay cả chỗ quản lý này cũng phải hiện … lần đổi hẹn hay huỷ hẹn này lý do là
// gì"). Dữ liệu do máy chủ trả (`COT_KENH_DOI_HUY`) — màn chỉ đặt nhãn.

import { nhanLyDoHuy } from "@/lib/ly-do-huy";

import { CHANNELS } from "../form-ui";

export interface DoiHuyGanNhat {
  loai: "DOI" | "HUY";
  ly_do: string | null;
  ma: string | null;
  luc: string | null;
}

export interface CoKenhDoiHuy {
  nguoi_gioi_thieu?: string | null;
  kenh_dat?: string | null;
  doi_huy_gan_nhat?: DoiHuyGanNhat | null;
}

function ngayGio(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export function nhanKenh(ma: string | null | undefined): string | null {
  if (!ma) return null;
  return CHANNELS.find((c) => c.id === ma)?.label ?? ma;
}

/** Câu "Đổi lịch 24/09 10:30: chị bận đột xuất" — null khi chưa đổi/huỷ lần nào. */
export function cauDoiHuy(d: DoiHuyGanNhat | null | undefined): string | null {
  if (!d) return null;
  const lyDo =
    d.loai === "HUY"
      ? [nhanLyDoHuy(d.ma), d.ly_do].filter(Boolean).join(" — ")
      : d.ly_do;
  const dau = d.loai === "HUY" ? "Huỷ lịch" : "Đổi lịch";
  return `${dau}${d.luc ? ` ${ngayGio(d.luc)}` : ""}: ${lyDo || "chưa ghi lý do"}`;
}

/** Hai dòng chữ nhỏ; không có gì để nói thì không vẽ gì. */
export default function KenhDoiHuy({
  k,
  gon = false,
}: {
  k: CoKenhDoiHuy;
  /** Dòng danh sách: một dòng, cắt chữ. */
  gon?: boolean;
}) {
  const kenh = nhanKenh(k.kenh_dat);
  const gioiThieu = (k.nguoi_gioi_thieu ?? "").trim();
  const doiHuy = cauDoiHuy(k.doi_huy_gan_nhat);
  if (!kenh && !gioiThieu && !doiHuy) return null;
  const dong1 = [kenh ? `Kênh: ${kenh}` : null, gioiThieu ? `Giới thiệu: ${gioiThieu}` : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <span className={`block text-label text-ink-muted ${gon ? "truncate" : ""}`}>
      {dong1 ? <span className="block">{dong1}</span> : null}
      {doiHuy ? (
        <span className={`block ${gon ? "truncate" : ""} text-warning`}>{doiHuy}</span>
      ) : null}
    </span>
  );
}
