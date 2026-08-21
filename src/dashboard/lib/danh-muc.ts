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
import { getSupabaseServer } from "./supabase-server";

export interface MucDanhMuc {
  id: string;
  name: string;
}

/** Cơ sở của phòng khám đang đăng nhập, sắp theo tên. */
export async function layCoSo(): Promise<MucDanhMuc[]> {
  const clinicId = await getClinicId();
  return nhoTheoPhongKham("co-so", clinicId ?? "", async () => {
    const supabase = await getSupabaseServer();
    const { data, error } = await supabase
      .from("clinic_location")
      .select("id, name")
      .order("name");
    // Lỗi thì trả rỗng — `nhoTheoPhongKham` cố ý KHÔNG nhớ mảng rỗng, nên lượt
    // sau vẫn hỏi lại thay vì khoá cứng một ô chọn trống suốt hạn giờ.
    if (error) return [];
    return (data ?? []) as MucDanhMuc[];
  });
}

/** Dịch vụ khám của phòng khám đang đăng nhập, sắp theo tên. */
export async function layDichVu(): Promise<MucDanhMuc[]> {
  const clinicId = await getClinicId();
  return nhoTheoPhongKham("dich-vu", clinicId ?? "", async () => {
    const supabase = await getSupabaseServer();
    const { data, error } = await supabase
      .from("service_type")
      .select("id, name")
      .order("name");
    if (error) return [];
    return (data ?? []) as MucDanhMuc[];
  });
}
