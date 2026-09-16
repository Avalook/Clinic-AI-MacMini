// Gọi máy chủ cho các màn làm việc theo phòng (Tuyền chốt 16/09/2026).
//
// MỘT ĐƯỜNG DỮ LIỆU: lượt khám → hàng chờ phòng → khám → chỉ định → kết quả →
// bác sĩ duyệt. Mọi màn phòng (bàn khám, siêu âm, thủ thuật, lấy mẫu, duyệt kết
// quả) đọc và ghi qua đây — không màn nào tự nói chuyện với bảng cũ.
//
// Chỉ là ống dẫn: thứ tự hàng chờ, ai được bấm gì, kết quả phiên khám là gì…
// đều do máy chủ quyết. Tệp này không chứa luật nào.

import { nhanLoi } from "@/lib/loi-api";

export type TrangThaiHang =
  | "blocked"
  | "waiting"
  | "called"
  | "serving"
  | "done";

export interface DongHangCho {
  id: string;
  trang_thai: TrangThaiHang;
  /** KHAM = lượt khám chính của bác sĩ · DICH_VU = chỉ định xếp vào phòng. */
  loai: "KHAM" | "DICH_VU";
  /** Mã phiên khám (KHAM) hoặc mã chỉ định (DICH_VU). */
  ref_id: string;
  visit_id: string;
  clinic_patient_id: string;
  appointment_id: string | null;
  so_thu_tu: number;
  ten: string;
  ma_bn: string;
  uu_tien: boolean;
  uu_tien_ly_do: string | null;
  viec: string | null;
  dich_vu_kham: string | null;
  form_code: string | null;
  service_code: string | null;
  node_code: string | null;
  exec_status: string | null;
  phien_status: string | null;
  bac_si: string | null;
  phong: string | null;
  vao_hang_luc: string | null;
  bat_dau_luc: string | null;
  xong_luc: string | null;
  ket_qua_luc: string | null;
  duyet_luc: string | null;
}

export interface Phong {
  id: string;
  code: string;
  ten: string;
  tang: string | null;
  nodes: string[];
  vi_tri?: string[];
}

export interface PhongHomNay {
  phong_cua_toi: Phong[];
  tat_ca_phong: Phong[];
}

export type KetQuaDoc<T> = { ok: true; data: T } | { ok: false; loi: string };

export async function docBang<T>(
  xem: string | null,
  thamSo: Record<string, string> = {},
): Promise<KetQuaDoc<T>> {
  const q = new URLSearchParams(thamSo);
  if (xem) q.set("xem", xem);
  const qs = q.toString();
  try {
    const r = await fetch(`/api/luot-kham${qs ? `?${qs}` : ""}`, {
      cache: "no-store",
    });
    const d = await r.json().catch(() => null);
    if (!r.ok) return { ok: false, loi: nhanLoi(d, "Không đọc được dữ liệu.") };
    return { ok: true, data: d as T };
  } catch {
    return { ok: false, loi: "Mất kết nối tới máy chủ." };
  }
}

// Khoá gửi lại đặt ở MỨC MODULE: gọi Date.now/Math.random trong thân component
// vi phạm luật thuần khiết của React (react-hooks/purity).
function khoaGuiLai(): string {
  return `lv-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

export async function guiThaoTac(
  thaoTac: string,
  id: string,
  duLieu: Record<string, unknown> = {},
): Promise<{ ok: true; data: Record<string, unknown> } | { ok: false; loi: string }> {
  try {
    const r = await fetch("/api/luot-kham", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": khoaGuiLai(),
      },
      body: JSON.stringify({ thao_tac: thaoTac, id, du_lieu: duLieu }),
    });
    const d = await r.json().catch(() => null);
    if (!r.ok) return { ok: false, loi: nhanLoi(d, "Thao tác không thành công.") };
    return { ok: true, data: (d ?? {}) as Record<string, unknown> };
  } catch {
    return { ok: false, loi: "Mất kết nối — thao tác CHƯA được ghi." };
  }
}

/** "chờ 12 phút" từ một mốc ISO. Rỗng khi không tính được. */
export function soPhutTu(iso: string | null, den?: string | null): string {
  if (!iso) return "";
  const cuoi = den ? new Date(den).getTime() : Date.now();
  const phut = Math.floor((cuoi - new Date(iso).getTime()) / 60000);
  if (!Number.isFinite(phut) || phut < 0) return "";
  if (phut < 60) return `${phut} phút`;
  return `${Math.floor(phut / 60)} giờ ${phut % 60} phút`;
}

export function gioVn(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}
