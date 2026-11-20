// Kiểu dữ liệu + lời gọi API của màn Kiểm kê ca (`KiemKeCa.tsx`) — tách ra 20/11/2026
// để màn không vượt trần dòng. Chỉ chuyển nguyên văn, không đổi hành vi.

export type Ca = "SANG" | "CHIEU" | "TOI";
export type Loai = "DAU" | "CUOI" | "DOT_XUAT";

export interface DongKiem {
  drug_catalog_id: string;
  ten: string;
  ma_hang: string | null;
  don_vi: string;
  dem: number;
  ton_may: number | null;
  lech: number | null;
  giao_chua_gan_lo: number | null;
  ly_do: string | null;
  chua_ap: number | null;
  chua_ap_ly_do: string | null;
  /** Có giá trị = phiếu từ 31/10: chốt đã ghi sổ, không còn bước điều chỉnh riêng. */
  giao_da_tach: number | null;
}

/** Dòng lệch máy chủ tính trước khi chốt. */
export interface DongLech {
  drug_catalog_id: string;
  don_vi: string;
  ten: string;
  dem: number;
  ton_may: number;
  giao_chua_gan_lo: number;
  lech: number;
}

export interface Phieu {
  id: string;
  ngay: string;
  ca: Ca;
  loai: Loai;
  trang_thai: "NHAP" | "CHOT";
  phien_ban: number;
  phieu_truoc_id: string | null;
  phieu_sau_id: string | null;
  ly_do_sua: string | null;
  mot_phan: boolean;
  dung_so_ca_truoc: boolean;
  chot_luc: string | null;
  moc_ton_luc: string | null;
  dieu_chinh_luc: string | null;
  dieu_chinh_ly_do: string | null;
  hoan_tac_luc: string | null;
  nguoi_chot: string | null;
  nguoi_dieu_chinh: string | null;
  dong: DongKiem[];
}

export interface TomTat {
  id: string;
  ca: Ca;
  loai: Loai;
  trang_thai: "NHAP" | "CHOT";
  phien_ban: number;
  phieu_truoc_id: string | null;
  phieu_sau_id: string | null;
  ly_do_sua: string | null;
  so_lech: number;
  so_chua_ap: number;
  dieu_chinh_luc: string | null;
  hoan_tac_luc: string | null;
}

export interface Nhac {
  ca: Ca;
  thieu_dau_ca: boolean;
  thieu_cuoi_ca_truoc: boolean;
}

export interface KetQuaDieuChinh {
  bo_qua: { ly_do: string }[];
}

export type KetQua<T> = { ok: true; data: T } | { ok: false; loi: string | null };

export async function goi<T>(method: "GET" | "POST", url: string, body?: unknown): Promise<KetQua<T>> {
  try {
    const r = await fetch(url, {
      method,
      cache: "no-store",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const d = (await r.json().catch(() => null)) as
      | (T & { message?: string; detail?: unknown; error?: string })
      | null;
    if (r.ok && d) return { ok: true, data: d };
    const ct = typeof d?.detail === "string" ? d.detail : null;
    const thongDiep = d?.message ?? ct ?? d?.error ?? "Máy chủ từ chối.";
    const loiKyThuat = /mã lỗi\s*[a-f\d-]+|lỗi chưa lường trước/i.test(thongDiep);
    return {
      ok: false,
      loi: loiKyThuat ? null : thongDiep,
    };
  } catch {
    return { ok: false, loi: "Mất kết nối — CHƯA lưu." };
  }
}
