// Admin-only — list every unlinked staff row so the operator can pick
// one and create + link a Supabase Auth user in a single form. The
// actual create+link happens server-side (app/api/admin/users) so the
// SERVICE_ROLE_KEY never leaves the dashboard process.

import { redirect } from "next/navigation";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import {
  hasServiceRoleKey,
  SERVICE_ROLE_ENV,
} from "../../../../lib/supabase-service";
import { getClinicRole } from "../../../../lib/clinic-session";
import { isAdminRole } from "../../../../lib/roles";
import NewUserForm from "./NewUserForm";

export const dynamic = "force-dynamic";

interface UnlinkedStaff {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
}

const DEPT_LABEL: Record<string, string> = {
  DOCTOR: "Bác sĩ",
  ULTRASOUND_DOCTOR: "Bác sĩ Siêu âm",
  NURSE_ULTRASOUND: "Điều dưỡng",
  RECEPTION: "Lễ tân",
  CSKH: "CSKH",
  MANAGEMENT: "Quản lý",
  CASHIER: "Thu ngân",
  CASHIER_THUOC: "Thu ngân thuốc",
  CASHIER_DV: "Thu ngân dịch vụ",
  TKYK: "Thư ký Y khoa",
  TRUONG_CA: "Trưởng ca",
};

export default async function NewUserPage() {
  const role = await getClinicRole();
  if (!isAdminRole(role)) redirect("/home");

  const supabase = await getSupabaseServer();
  const { data, error } = await supabase
    .from("staff")
    .select("id, full_name, short_name, primary_department")
    .is("auth_user_id", null)
    .eq("is_active", true)
    .order("full_name", { ascending: true });

  const unlinked = (data as UnlinkedStaff[] | null) ?? [];
  const options = unlinked.map((s) => ({
    id: s.id,
    label: `${s.full_name} (${DEPT_LABEL[s.primary_department] ?? s.primary_department})`,
  }));
  // Surface the env-var gap so the operator sees the failure mode
  // before they fill the form (the API returns 503 too — this is a
  // friendlier preview).
  const hasServiceKey = hasServiceRoleKey();

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-xl font-semibold text-[#171717]">
          Thêm tài khoản đăng nhập
        </h1>
        <p className="text-sm text-[#888888]">
          Tạo Supabase Auth user và link với một nhân viên hiện có.
        </p>
      </header>

      {!hasServiceKey && (
        <div className="rounded-md bg-[#fef9c3] px-3 py-2 text-sm text-[#a16207]">
          ⚠️ <code className="text-xs font-mono">{SERVICE_ROLE_ENV}</code>{" "}
          chưa được cấu hình trên server. Form bên dưới sẽ trả lỗi 503 đến
          khi key được thêm vào <code className="text-xs font-mono">.env</code>{" "}
          và restart dashboard. Lấy key từ Supabase dashboard → Settings → API
          → service_role.
        </div>
      )}

      {error && (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          {error.message}
        </div>
      )}

      {unlinked.length === 0 ? (
        <div className="rounded-md border border-[#e4e4e7] bg-white px-4 py-6 text-sm text-[#888888]">
          Mọi nhân viên active đã được link với tài khoản. Để link thêm,
          tạo staff mới trong Notion + chạy{" "}
          <code className="text-xs font-mono">
            build_seeds_from_notion.py
          </code>{" "}
          rồi mở lại trang này.
        </div>
      ) : (
        <NewUserForm staffOptions={options} />
      )}
    </div>
  );
}
