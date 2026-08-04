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
import { isAdminRole, ROLE_LABEL, type ClinicRole } from "../../../../lib/roles";
import NewUserForm from "./NewUserForm";

export const dynamic = "force-dynamic";

interface UnlinkedStaff {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
}

// Nhãn vai dùng ROLE_LABEL của lib/roles.ts. Trước đây file này (và
// settings/page.tsx) mỗi nơi giữ một bản DEPT_LABEL riêng, và CẢ HAI đều
// thiếu PHARMACIST — vai đã chạy từ khi có màn /pharmacy. Hệ quả: màn tạo
// user và màn danh sách nhân viên hiện chữ "PHARMACIST" thô cho dược sĩ.
// Cùng một lỗi đã xảy ra ở ROLE_VI trong WorkItemActions.tsx: một bảng nhãn
// chép tay là một bảng nhãn sẽ thiếu vai tiếp theo.

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
    label: `${s.full_name} (${ROLE_LABEL[s.primary_department as ClinicRole] ?? s.primary_department})`,
  }));
  // Surface the env-var gap so the operator sees the failure mode
  // before they fill the form (the API returns 503 too — this is a
  // friendlier preview).
  const hasServiceKey = hasServiceRoleKey();

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      <header>
        <h1 className="text-xl font-semibold text-ink lg:text-2xl">
          Thêm tài khoản đăng nhập
        </h1>
        <p className="mt-1 text-sm text-ink-muted">
          Tạo Supabase Auth user và link với một nhân viên hiện có.
        </p>
      </header>

      {!hasServiceKey && (
        <div className="rounded-card border border-warning bg-warning-bg px-4 py-3 text-sm text-warning">
          ⚠️ <code className="text-xs font-mono">{SERVICE_ROLE_ENV}</code>{" "}
          chưa được cấu hình trên server. Form bên dưới sẽ trả lỗi 503 đến
          khi key được thêm vào <code className="text-xs font-mono">.env</code>{" "}
          và restart dashboard. Lấy key từ Supabase dashboard → Settings → API
          → service_role.
        </div>
      )}

      {error && (
        <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
          {error.message}
        </div>
      )}

      {unlinked.length === 0 ? (
        <div className="rounded-card border border-line bg-surface px-4 py-8 text-sm text-ink-muted shadow-card">
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
    </main>
  );
}
