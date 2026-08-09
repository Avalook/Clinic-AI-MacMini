// Danh sách bác sĩ để đổ vào ô chọn — MỘT chỗ, cho cả bảy màn.
//
// VẤN ĐỀ NÓ THAY THẾ. Bảy trang tự viết cùng một truy vấn:
//
//     supabase.from("staff")
//       .select("id, full_name")
//       .in("primary_department", ["DOCTOR", "ULTRASOUND_DOCTOR"])
//       .eq("is_active", true)
//
// `staff.primary_department` là vai TOÀN CỤC của một con người — thuộc tính mô
// tả họ là ai nói chung. Nhưng quyền hạn trong hệ thống này đến từ
// `clinic_membership.role`: vai của họ TRONG MỘT PHÒNG KHÁM cụ thể. identity.py
// nói thẳng điều đó ("A doctor may be MANAGEMENT at clinic A and DOCTOR at
// clinic B"), và mọi quyết định phân quyền phía backend đọc membership.
//
// Ba hệ quả của việc hỏi sai cột:
//
//   1. THIẾU NGƯỜI. Ai có membership DOCTOR ở phòng khám này nhưng
//      primary_department ghi khác (đổi vai, kiêm nhiệm, nhập liệu ban đầu) sẽ
//      KHÔNG hiện trong ô chọn — không thể đặt lịch cho họ, và không có thông
//      báo nào nói vì sao.
//
//   2. THỪA NGƯỜI. Ngược lại, ai mang nhãn DOCTOR toàn cục nhưng ở phòng khám
//      này chỉ là CSKH vẫn hiện ra như một bác sĩ nhận lịch được.
//
//   3. KHÔNG SCOPE THEO PHÒNG KHÁM. Bản cũ lọc `staff` trực tiếp, mà `staff` là
//      bảng con người dùng chung; nó chỉ dựa vào RLS của staff. Truy vấn dưới
//      đây đi qua `clinic_membership`, và RLS của bảng đó giới hạn theo
//      current_clinic_ids() — nên phạm vi phòng khám là kết quả của cấu trúc
//      truy vấn chứ không phải một điều kiện ai đó phải nhớ viết thêm.
//
// Hai điều kiện "còn hoạt động" đều cần: `staff.is_active` (người này còn làm ở
// đây không) và `clinic_membership.is_active` (còn thuộc phòng khám này không).
// Bản cũ chỉ kiểm cái đầu.

import { doctorName } from "./doctor-name";
import { getSupabaseServer } from "./supabase-server";

/** Vai KHÁM BỆNH — người nhận được một lịch hẹn.
 *
 *  KHÔNG phải DOCTOR_DESK_ROLES (roles.ts): thư ký y khoa ngồi cùng bàn khám và
 *  nhập hộ hồ sơ, nhưng lịch hẹn không đặt cho thư ký. Đây là "ai khám", không
 *  phải "ai thao tác ở màn bác sĩ". */
export const BOOKABLE_DOCTOR_ROLES = ["DOCTOR", "ULTRASOUND_DOCTOR"] as const;

export interface DoctorOption {
  id: string;
  label: string;
}

interface DoctorRow {
  id: string;
  full_name: string | null;
}

/**
 * Bác sĩ đang hoạt động của phòng khám đang đăng nhập, sắp theo tên.
 *
 * Trả mảng rỗng khi đọc lỗi — người gọi vẽ ô chọn trống thay vì đổ trang. Ô
 * chọn trống nhìn thấy được; một trang lỗi thì che mất mọi thứ khác trên màn.
 */
export async function listBookableDoctors(): Promise<DoctorOption[]> {
  const supabase = await getSupabaseServer();

  // `clinic_membership!inner(...)` = INNER JOIN: chỉ giữ staff CÓ membership
  // khớp điều kiện. Không có `!inner` thì PostgREST làm LEFT JOIN và các bộ lọc
  // trên bảng nhúng chỉ lọc phần nhúng, còn dòng staff vẫn ở lại — tức mọi nhân
  // viên đều lọt vào danh sách bác sĩ.
  const { data, error } = await supabase
    .from("staff")
    .select("id, full_name, clinic_membership!inner(role, is_active)")
    .in("clinic_membership.role", BOOKABLE_DOCTOR_ROLES as readonly string[])
    .eq("clinic_membership.is_active", true)
    .eq("is_active", true)
    .order("full_name");

  if (error) return [];

  // TÊN HIỂN THỊ CHUẨN HOÁ NGAY TẠI NGUỒN. Mọi màn dùng danh sách này (lưới
  // đặt lịch, modal đổi lịch, ô lọc bác sĩ) vì thế nói cùng một cái tên — thay
  // vì mỗi màn tự gọi doctorName() và một màn nào đó quên.
  return ((data as DoctorRow[] | null) ?? []).map((r) => ({
    id: r.id,
    label: doctorName(r.full_name) || "—",
  }));
}
