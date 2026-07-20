// Settings — Admin-only staff overview. The current Phase 1 demo need
// is for an operator to see which staff rows are linked to a Supabase
// Auth account (the green dot) so they can run
// ``scripts/seed/link_staff_to_auth.py`` for the missing ones.

import Link from "next/link";
import { redirect } from "next/navigation";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { isAdminRole } from "../../../lib/roles";
import AccountActions from "./AccountActions";

export const dynamic = "force-dynamic";

interface StaffRow {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
  employment_type: string;
  is_active: boolean;
  auth_user_id: string | null;
}

// Friendly label per Supabase CHECK enum.
const DEPT_LABEL: Record<string, string> = {
  DOCTOR: "Bác sĩ",
  ULTRASOUND_DOCTOR: "Bác sĩ Siêu âm",
  NURSE_ULTRASOUND: "Điều dưỡng",
  RECEPTION: "Lễ tân",
  CSKH: "CSKH",
  MANAGEMENT: "Quản lý",
};

const TH = "px-4 py-2.5 font-medium";
const TD = "px-4 py-2.5";

export default async function SettingsPage() {
  const role = await getClinicRole();
  if (!isAdminRole(role)) redirect("/home");

  const supabase = await getSupabaseServer();
  const { data, error } = await supabase
    .from("staff")
    .select(
      "id, full_name, short_name, primary_department, employment_type, " +
        "is_active, auth_user_id",
    )
    .order("primary_department", { ascending: true })
    .order("full_name", { ascending: true });

  const rows = (data as StaffRow[] | null) ?? [];
  const linked = rows.filter((r) => r.auth_user_id !== null).length;

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-[#171717]">Cài đặt</h1>
          <p className="text-sm text-[#888888]">
            Nhân viên + trạng thái liên kết tài khoản đăng nhập.
          </p>
        </div>
        <Link
          href="/settings/new-user"
          className="shrink-0 rounded-md bg-[#ec4899] px-3.5 py-1.5 text-sm font-medium text-white transition-colors duration-150 hover:bg-[#db2777]"
        >
          + Thêm tài khoản
        </Link>
      </header>

      <div className="rounded-md border border-[#e4e4e7] bg-white px-4 py-3 text-sm text-[#4d4d4d]">
        <span className="font-medium text-[#171717]">{linked}</span> /{" "}
        <span className="font-medium text-[#171717]">{rows.length}</span>{" "}
        nhân viên đã được link với tài khoản đăng nhập. Bấm{" "}
        <span className="font-medium text-[#171717]">+ Thêm tài khoản</span>{" "}
        để tạo login mới, hoặc dùng nút thao tác ở mỗi dòng để đặt lại mật
        khẩu / gỡ tài khoản — tất cả ngay trong dashboard, không cần vào
        console Supabase.
      </div>

      {error && (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          {error.message}
        </div>
      )}

      {/* Mobile: card list (<md). */}
      <ul className="space-y-2 md:hidden">
        {rows.map((r) => (
          <li
            key={r.id}
            className="rounded-lg border border-[#e4e4e7] bg-white p-3 shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-medium text-[#171717]">{r.full_name}</p>
                <p className="text-xs text-[#71717a]">
                  {DEPT_LABEL[r.primary_department] ?? r.primary_department}
                  {" · "}
                  <span className="text-[#888888]">{r.employment_type}</span>
                </p>
              </div>
              {r.is_active ? (
                <span className="inline-flex shrink-0 items-center gap-1 text-xs text-[#15803d]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#22c55e]" />
                  Active
                </span>
              ) : (
                <span className="shrink-0 text-xs text-[#888888]">Inactive</span>
              )}
            </div>
            <div className="mt-2 flex items-center justify-between gap-2">
              {r.auth_user_id ? (
                <span className="inline-flex items-center gap-1 text-xs text-[#15803d]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#22c55e]" />
                  Đã link
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs text-[#a16207]">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#eab308]" />
                  Chưa link
                </span>
              )}
              {r.auth_user_id ? (
                <AccountActions staffId={r.id} staffName={r.full_name} />
              ) : (
                <Link
                  href="/settings/new-user"
                  className="text-xs text-[#ec4899] hover:underline"
                >
                  Tạo tài khoản
                </Link>
              )}
            </div>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="rounded-lg border border-[#e4e4e7] bg-white px-4 py-6 text-center text-sm text-[#888888]">
            Chưa có nhân viên.
          </li>
        )}
      </ul>

      {/* Desktop: table (≥md). */}
      <div className="hidden overflow-auto rounded-lg border border-[#f3cfe0] bg-white shadow-[0_1px_3px_rgba(236,72,153,0.08)] max-h-[88vh] min-h-[180px] md:block">
        <table className="min-w-full divide-y divide-[#f6e0ec] text-sm">
          <thead className="sticky top-0 z-10 bg-[#fce7f3] text-left text-[11px] font-semibold uppercase tracking-wide text-[#9d2463]">
            <tr>
              <th className={TH}>Họ tên</th>
              <th className={TH}>Vai trò</th>
              <th className={TH}>Hợp đồng</th>
              <th className={TH}>Active</th>
              <th className={TH}>Login</th>
              <th className={TH}>Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#f6e0ec]">
            {rows.map((r) => (
              <tr
                key={r.id}
                className="transition-colors duration-150 hover:bg-[#fdf2f8]"
              >
                <td className={`${TD} text-[#171717]`}>
                  {r.full_name}
                  {r.short_name && r.short_name !== r.full_name && (
                    <span className="ml-2 text-xs text-[#888888]">
                      {r.short_name}
                    </span>
                  )}
                </td>
                <td className={`${TD} text-[#4d4d4d]`}>
                  {DEPT_LABEL[r.primary_department] ?? r.primary_department}
                </td>
                <td className={`${TD} text-xs text-[#71717a]`}>
                  {r.employment_type}
                </td>
                <td className={TD}>
                  {r.is_active ? (
                    <span className="inline-flex items-center gap-1 text-xs text-[#15803d]">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#22c55e]" />
                      Active
                    </span>
                  ) : (
                    <span className="text-xs text-[#888888]">Inactive</span>
                  )}
                </td>
                <td className={TD}>
                  {r.auth_user_id ? (
                    <span className="inline-flex items-center gap-1 text-xs text-[#15803d]">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#22c55e]" />
                      Đã link
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs text-[#a16207]">
                      <span className="h-1.5 w-1.5 rounded-full bg-[#eab308]" />
                      Chưa link
                    </span>
                  )}
                </td>
                <td className={TD}>
                  {r.auth_user_id ? (
                    <AccountActions staffId={r.id} staffName={r.full_name} />
                  ) : (
                    <Link
                      href="/settings/new-user"
                      className="text-xs text-[#ec4899] hover:underline"
                    >
                      Tạo tài khoản
                    </Link>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-[#888888]">
                  Chưa có nhân viên.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
