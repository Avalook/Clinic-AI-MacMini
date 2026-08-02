"use server";

// Chọn phòng khám đang làm việc cho phiên này.
//
// Ô chọn là *bộ chọn*, không phải thẩm quyền: giá trị gửi lên chỉ được phép
// trỏ tới một membership mà chính tài khoản này đang có. Vì vậy ở đây vẫn phải
// đọc lại clinic_membership từ auth.uid() rồi mới ghi cookie — không tin
// formData, đúng như ADR-0009.

import { redirect } from "next/navigation";
import { setActiveClinicId } from "../../../lib/active-clinic";
import {
  resolveActiveMembership,
  resolveLinkedStaffAuthority,
} from "../../../lib/identity-authority";
import { departmentToRole, roleLanding } from "../../../lib/roles";
import { getSupabaseServer } from "../../../lib/supabase-server";

export async function chooseClinic(
  _prev: { error: string } | null,
  formData: FormData,
): Promise<{ error: string } | null> {
  const clinicId = String(formData.get("clinic_id") ?? "").trim();
  if (!clinicId) return { error: "Chọn một phòng khám." };

  const supabase = await getSupabaseServer();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: staff } = await supabase
    .from("staff")
    .select("id, primary_department, is_active, auth_user_id")
    .eq("auth_user_id", user.id)
    .maybeSingle();
  const identity = resolveLinkedStaffAuthority(user.id, staff);
  if (!identity) redirect("/login");

  const { data: memberships, error } = await supabase
    .from("clinic_membership")
    .select("clinic_id, role, is_active")
    .eq("staff_id", identity.id)
    .eq("is_active", true);
  if (error) return { error: "Không đọc được danh sách phòng khám." };

  const selection = resolveActiveMembership(memberships ?? [], clinicId);
  if (selection.status !== "resolved") {
    // Người dùng bấm một lựa chọn không còn thuộc về họ (quản lý vừa gỡ
    // membership, hoặc trang mở từ hôm qua). Không phải lỗi để đổ cho họ.
    return { error: "Bạn không còn làm việc ở phòng khám này." };
  }

  await setActiveClinicId(selection.membership.clinic_id);
  redirect(roleLanding(departmentToRole(selection.membership.role)));
}
