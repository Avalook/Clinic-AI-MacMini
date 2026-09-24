// Danh mục ít đổi: cơ sở và dịch vụ khám.
//
// Mọi màn có ô chọn cơ sở / dịch vụ đều hỏi lại hai danh sách này mỗi lần dựng
// trang, dù chúng đổi vài tháng một lần. Gói qua `nhoTheoPhongKham` để cắt
// vòng gọi — xem lý do đo đạc trong `bo-nho-tam.ts`.
//
// KHÔNG đặt ở đây những thứ đổi theo phút (lịch hẹn, ghế trống, trạng thái
// bệnh nhân). Một ô lịch "còn trống" nhớ quá hạn là hai người đặt trùng.

import { getClinicId } from "./clinic-session";
import { nhoTheoPhongKham } from "./bo-nho-tam";
import { fetchFromBackend } from "./backend-proxy";

export interface MucDanhMuc {
  id: string;
  name: string;
}

/** Cơ sở của phòng khám đang đăng nhập, sắp theo tên. */
export async function layCoSo(): Promise<MucDanhMuc[]> {
  const clinicId = await getClinicId();
  // 24/09/2026: đọc qua backend `GET /api/v1/catalog/locations` (lọc phòng khám
  // ở máy chủ) thay vì đọc thẳng `clinic_location` bằng Supabase.
  return nhoTheoPhongKham("co-so", clinicId ?? "", async () => {
    const data = await fetchFromBackend<MucDanhMuc[]>("/api/v1/catalog/locations");
    return data ?? [];
  });
}

/** Dịch vụ khám ĐANG BẬT của phòng khám đang đăng nhập, sắp theo tên.
 *  Chỉ có năm loại khám (migration 20260807000007); thiếu lọc này màn đặt lịch
 *  CSKH hiện đủ 14 dịch vụ cũ (FREE, Sản 2/3, Tiền hôn nhân…). */
export async function layDichVu(): Promise<MucDanhMuc[]> {
  const clinicId = await getClinicId();
  // 24/09/2026: đọc qua backend `GET /api/v1/catalog/service-types` (chỉ loại
  // đang bật của phòng khám người gọi).
  return nhoTheoPhongKham("dich-vu", clinicId ?? "", async () => {
    const data = await fetchFromBackend<
      { id: string; name: string; is_active: boolean | null }[]
    >("/api/v1/catalog/service-types");
    return (data ?? [])
      .filter((d) => d.is_active !== false)
      .map(({ id, name }) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name, "vi"));
  });
}
