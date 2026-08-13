// TÊN NGƯỜI TRONG LỊCH TRỰC — MỘT NGUỒN, MỘT CÁCH VIẾT.
//
// `work_roster.staff_name` là chuỗi TỰ DO nạp từ file Excel "BẢNG LÀM VIỆC",
// nên cùng một người hiện ra mỗi chỗ một kiểu. Đo trên prod ngày 08/08, riêng
// cột Lịch khám:
//
//     "Bác sĩ · BSNT. Lê Thiệu Quyết"  ─┐  cùng một staff_id
//     "BS QUYẾT"                       ─┘
//     "BS HÙNG"        → staff.full_name = "Bác sĩ · BSNT. Vũ Trọng Hùng"
//
// Người đọc bảng không biết hai dòng đầu có phải một người hay không, còn cột
// "Số BS" thì đếm theo staff_id nên nói 4 trong khi bảng bày ra 5 cái tên. Một
// con số và một danh sách cãi nhau ngay cạnh nhau.
//
// Logic này TỪNG chỉ có ở màn /schedule. Trang chủ đọc thẳng `staff_name` nên
// vẫn bày chuỗi Excel thô — hai màn cùng vẽ một bảng, hai cách viết tên.

import type { SupabaseClient } from "@supabase/supabase-js";
import { doctorName } from "./doctor-name";

interface CoTen {
  staff_id?: string | null;
  staff_name: string | null;
}

/**
 * Thay `staff_name` bằng tên chuẩn lấy từ `staff.full_name` theo `staff_id`.
 *
 * Dòng KHÔNG có staff_id (nhập tay từ Excel, chưa nối được vào ai) giữ nguyên
 * chuỗi cũ: bịa một cái tên chuẩn cho người chưa xác định được là tệ hơn hiện
 * đúng thứ đang có.
 */
export async function dongBoTenTrucNhat<T extends CoTen>(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  supabase: SupabaseClient<any, any, any>,
  rows: T[],
): Promise<T[]> {
  const ids = [...new Set(rows.map((r) => r.staff_id).filter(Boolean))];
  if (ids.length === 0) return rows;

  const { data } = await supabase
    .from("staff")
    .select("id, full_name")
    .in("id", ids as string[]);

  const theoId: Record<string, string> = {};
  for (const nv of (data as { id: string; full_name: string }[] | null) ?? []) {
    const ten = doctorName(nv.full_name);
    if (ten) theoId[nv.id] = ten;
  }
  return rows.map((r) => ({
    ...r,
    staff_name: (r.staff_id && theoId[r.staff_id]) || r.staff_name,
  }));
}
