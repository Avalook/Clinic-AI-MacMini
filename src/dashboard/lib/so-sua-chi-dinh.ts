// Kiểu dữ liệu sổ sửa / bỏ chỉ định (Khối 2, 06/10/2026) — dạng máy chủ trả
// (`so_sua_chi_dinh_service.dong_so`). Chỉ kiểu, không luật.

export interface DongSoSua {
  id: string;
  luc: string | null;
  sua_luc: string | null;
  nhom: string | null;
  nhom_nhan: string;
  hanh_dong: string | null;
  hanh_dong_nhan: string;
  ten_muc: string | null;
  cau: string;
  boi: string | null;
  boi_vai: string | null;
  phong_kham: string | null;
  bac_si_chinh: string | null;
  chi_dinh_goc_boi: string | null;
  da_thu: number;
  tien_thua: number;
  ly_do: string | null;
  da_bao_bac_si_luc: string | null;
  hoan_tac_boi: string | null;
  hoan_tac_luc: string | null;
  hoan_tac_duoc: boolean;
}

export interface SoSua {
  chi_xem: boolean;
  dong: DongSoSua[];
}
