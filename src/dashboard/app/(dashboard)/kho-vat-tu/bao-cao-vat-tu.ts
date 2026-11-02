export interface DongTieuHao {
  vat_tu_id: string;
  room_id: string;
  ten: string;
  don_vi: string | null;
  phong: string;
  du_du_lieu: boolean;
  ly_do_thieu: string;
  dau: number | null;
  nhan: number | null;
  tra: number | null;
  cuoi: number | null;
  tieu_hao: number | null;
  da_dung: number | null;
  trong_do_huy: number | null;
  /** Bán cho khách giữa hai lần đếm (ròng sau hoàn tác). */
  da_ban: number | null;
  /** Phần còn lại của hao hụt theo số đếm sau khi trừ bán và huỷ. */
  dung_khong_ban: number | null;
  tra_nha_san_xuat: number | null;
  cap_trong_ky: number;
  thuc_te_gan_nhat: number | null;
  thuc_te_gan_nhat_luc: string | null;
  gia_nhap: number;
  gia_tri: number | null;
  gia_tri_da_dung: number | null;
  dem_dau_luc: string | null;
  /** Chưa có lần đếm trước kỳ: đầu kỳ = lần đếm đầu tiên trong kỳ. */
  dau_trong_ky: boolean;
  dem_cuoi_luc: string | null;
  canh_bao: string;
}

export interface GoiTieuHao {
  tu: string;
  den: string;
  items: DongTieuHao[];
  theo_phong: {
    room_id: string;
    phong: string;
    gia_tri: number;
    gia_tri_da_dung: number;
    so_dong: number;
    chua_du: number;
  }[];
  tong_gia_tri: number;
  tong_gia_tri_da_dung: number;
}

export function khoangTuanHienTai(): { tu: string; den: string } {
  const parts = new Intl.DateTimeFormat("en", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const year = Number(values.year);
  const month = Number(values.month);
  const day = Number(values.day);
  const today = new Date(Date.UTC(year, month - 1, day));
  const monday = new Date(Date.UTC(year, month - 1, day - ((today.getUTCDay() + 6) % 7)));
  return {
    tu: monday.toISOString().slice(0, 10),
    den: today.toISOString().slice(0, 10),
  };
}

export async function docBaoCaoVatTu(
  tu: string,
  den: string,
  signal?: AbortSignal,
): Promise<{ goi: GoiTieuHao } | { loi: string }> {
  const query = new URLSearchParams({ ky: "tuy", tu, den });
  try {
    const response = await fetch(`/api/vat-tu-kho/tieu-hao?${query}`, {
      cache: "no-store",
      signal,
    });
    const data = (await response.json().catch(() => null)) as (GoiTieuHao & { error?: string }) | null;
    if (!response.ok || !data?.items) {
      return { loi: data?.error ?? "Không đọc được báo cáo vật tư." };
    }
    return { goi: data };
  } catch {
    return { loi: "Mất kết nối — chưa đọc được báo cáo vật tư." };
  }
}
