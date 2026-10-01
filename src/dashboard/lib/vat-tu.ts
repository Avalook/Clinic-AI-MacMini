// Vật tư bán thêm ở quầy Thu tiền dịch vụ (Tuyền 01/10/2026, C13).
//
// Máy chủ quyết TẤT CẢ: mặt hàng nào bán được (giá > 0, đang bán — luật file
// KiotViet "giá 0 = không bán"), hàng nào là nút chọn nhanh, hàng nào lượt này
// cần (gợi ý), hàng nào cần quản lý duyệt, thứ tự hiện. Tệp này chỉ có kiểu dữ
// liệu và MỘT hàm lọc chữ cho ô tìm (gõ không dấu cũng ra) — không luật tiền nào.

/** Bỏ dấu + thường — "dau do" ra "Đầu dò". Cùng cách với `boDauTim` của lib/
 *  phieu-kham.ts; viết lại ở đây để tệp này không kéo theo cả thư viện phiếu
 *  khám (và để chạy được dưới `node --test` không qua trình đóng gói). */
export function boDauVatTu(s: string): string {
  return s.normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/đ/gi, "d").toLowerCase();
}

export interface VatTuMuc {
  id: string;
  ten: string;
  don_vi: string | null;
  don_gia: number | null;
  ban_duoc: boolean;
  /** Vì sao không bán được ("chưa có giá — không bán", "đã ngưng bán"). */
  ly_do_khong_ban: string | null;
  can_ql_duyet: boolean;
  chon_nhanh: boolean;
  /** Lượt này có dịch vụ cần món này (Tập máy Bio → đầu dò). */
  goi_y: boolean;
}

export interface VatTuDong {
  id: string;
  service_price_id: string;
  ten: string;
  don_vi: string | null;
  don_gia: number;
  so_luong: number;
  thanh_tien: number;
  da_thu: boolean;
  nguoi_duyet: string | null;
  ly_do_duyet: string | null;
}

export interface VatTuGoi {
  danh_muc: VatTuMuc[];
  dong: VatTuDong[];
  tong: number;
  duoc_sua: boolean;
  la_quan_ly: boolean;
  quan_ly: { id: string; ten: string }[];
}

/** Số mặt hàng hiện dưới ô tìm. */
export const TOI_DA_KET_QUA = 8;

/**
 * Lọc danh mục theo chữ gõ — bỏ dấu, không phân hoa thường ("dau do", "MIRENA"
 * ra hàng có dấu). Giữ thứ tự máy chủ trả; chữ rỗng → không có kết quả (màn chỉ
 * hiện danh sách khi người dùng gõ). Hàm thuần.
 */
export function timVatTu(
  ds: readonly VatTuMuc[],
  tu: string,
  toiDa: number = TOI_DA_KET_QUA,
): VatTuMuc[] {
  const khoa = boDauVatTu(tu.trim());
  if (!khoa) return [];
  const tung = khoa.split(/\s+/);
  return ds
    .filter((m) => {
      const ten = boDauVatTu(m.ten);
      return tung.every((t) => ten.includes(t));
    })
    .slice(0, toiDa);
}
