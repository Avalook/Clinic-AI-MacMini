// Màn chọn phòng khám — chỉ xuất hiện khi tài khoản có từ 2 membership trở lên.
//
// Ai chỉ làm một nơi (hôm nay là tất cả 35 người của Dr4Women) không bao giờ
// thấy màn này: getStaffContext() tự giải quyết và trả về "resolved".

import { redirect } from "next/navigation";
import ClinicPicker, { type ClinicChoice } from "./ClinicPicker";
import {
  getStaffContext,
  type StaffContext,
} from "../../../lib/current-staff";
import { ROLE_LABEL, departmentToRole, roleLanding } from "../../../lib/roles";
import { getSupabaseServer } from "../../../lib/supabase-server";

export default async function ChooseClinicPage({
  searchParams,
}: {
  searchParams: Promise<{ switch?: string }>;
}) {
  const context = await getStaffContext();
  if (context.status === "anonymous") redirect("/login");

  const wantsSwitch = (await searchParams).switch !== undefined;
  const choices = pickable(context, wantsSwitch);
  if (!choices) {
    // Đã chọn xong (hoặc chỉ có một nơi) — không để màn này thành một cửa thừa
    // giữa đăng nhập và việc.
    redirect(
      roleLanding(
        departmentToRole(
          context.status === "resolved" ? context.staff.clinic_role : null,
        ),
      ),
    );
  }

  const supabase = await getSupabaseServer();
  const { data } = await supabase
    .from("clinic")
    .select("id, name")
    .in(
      "id",
      choices.map((membership) => membership.clinic_id),
    );
  const names = new Map(
    ((data as { id: string; name: string }[] | null) ?? []).map((clinic) => [
      clinic.id,
      clinic.name,
    ]),
  );

  const options: ClinicChoice[] = choices.map((membership) => {
    const role = departmentToRole(membership.role);
    return {
      clinicId: membership.clinic_id,
      // Tên phòng khám đọc qua RLS; nếu không thấy thì vẫn phải chọn được, nên
      // rơi về nhãn chung thay vì bỏ hẳn lựa chọn khỏi danh sách.
      name: names.get(membership.clinic_id) ?? "Phòng khám",
      roleLabel: role ? ROLE_LABEL[role] : membership.role,
    };
  });

  return <ClinicPicker choices={options} />;
}

/** Danh sách để chọn, hoặc null khi không có gì để hỏi. */
function pickable(context: StaffContext, wantsSwitch: boolean) {
  if (context.status === "must_choose_clinic") return context.choices;
  // ?switch=1 là đường đổi ca giữa chừng: đã chọn rồi vẫn hỏi lại, nhưng chỉ
  // khi thật sự có nhiều hơn một nơi để đổi sang.
  if (context.status === "resolved" && wantsSwitch && context.choices.length > 1)
    return context.choices;
  return null;
}
