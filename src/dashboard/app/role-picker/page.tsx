// Màn chọn danh tính — ngay sau cổng mật khẩu phòng khám. Liệt kê TẤT CẢ nhân
// viên (nhóm theo chức danh); mỗi người bấm đúng tên mình → vào không gian làm
// việc riêng. Vai trò suy ra từ chức danh ở server (actions.ts).

import { getSupabaseServer } from "../../lib/supabase-server";
import StaffPicker, { type StaffPerson } from "./StaffPicker";

export const dynamic = "force-dynamic";

export default async function RolePickerPage() {
  const supabase = await getSupabaseServer();
  const { data } = await supabase
    .from("staff")
    .select("id, full_name, short_name, primary_department")
    .eq("is_active", true)
    .order("full_name", { ascending: true });

  const staff = (data as StaffPerson[] | null) ?? [];
  return <StaffPicker staff={staff} />;
}
