// Settings — Admin-only staff overview. The current Phase 1 demo need
// is for an operator to see which staff rows are linked to a Supabase
// Auth account (the green dot) so they can run
// ``scripts/seed/link_staff_to_auth.py`` for the missing ones.

import Link from "next/link";
import { redirect } from "next/navigation";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getClinicRole } from "../../../lib/clinic-session";
import { isAdminRole, ROLE_LABEL, type ClinicRole } from "../../../lib/roles";
import { getBookingPolicy } from "../../../lib/booking-policy";
import AccountActions from "./AccountActions";
import BookingPolicyCard from "./BookingPolicyCard";
import FeatureModeCard from "./FeatureModeCard";
import { getFeatureMode } from "../../../lib/feature-mode";

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
// Nhãn vai dùng ROLE_LABEL của lib/roles.ts. Trước đây file này (và
// settings/page.tsx) mỗi nơi giữ một bản DEPT_LABEL riêng, và CẢ HAI đều
// thiếu PHARMACIST — vai đã chạy từ khi có màn /pharmacy. Hệ quả: màn tạo
// user và màn danh sách nhân viên hiện chữ "PHARMACIST" thô cho dược sĩ.
// Cùng một lỗi đã xảy ra ở ROLE_VI trong WorkItemActions.tsx: một bảng nhãn
// chép tay là một bảng nhãn sẽ thiếu vai tiếp theo.

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

  // Luật đặt lịch của phòng khám — hiển thị + cho phép Trưởng ca/Quản lý sửa.
  const bookingPolicy = await getBookingPolicy();

  const rows = (data as StaffRow[] | null) ?? [];
  const linked = rows.filter((r) => r.auth_user_id !== null).length;
  const featureMode = await getFeatureMode();

  return (
    <main className="page-in min-w-0 space-y-5 p-4 lg:p-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl font-semibold text-ink lg:text-2xl">Cài đặt tài khoản</h1>
          <p className="mt-1 text-sm text-ink-muted">
            Nhân viên + trạng thái liên kết tài khoản đăng nhập.
          </p>
        </div>
        <Link
          href="/settings/new-user"
          className="shrink-0 rounded-control bg-brand-600 px-4 py-2 text-sm font-medium text-surface transition-colors duration-150 hover:bg-brand-700"
        >
          + Thêm tài khoản
        </Link>
      </header>

      <div className="rounded-card border border-line bg-brand-50 px-4 py-3 text-sm text-ink-soft shadow-card">
        <span className="font-medium text-ink">{linked}</span> /{" "}
        <span className="font-medium text-ink">{rows.length}</span>{" "}
        nhân viên đã được link với tài khoản đăng nhập. Bấm{" "}
        <span className="font-medium text-ink">+ Thêm tài khoản</span>{" "}
        để tạo login mới, hoặc dùng nút thao tác ở mỗi dòng để đặt lại mật
        khẩu / gỡ tài khoản — tất cả ngay trong dashboard, không cần vào
        console Supabase.
      </div>

      <FeatureModeCard currentMode={featureMode} />

      <BookingPolicyCard policy={bookingPolicy} />

      {error && (
        <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
          {error.message}
        </div>
      )}

      {/* Mobile: card list (<md). */}
      <ul className="space-y-2 md:hidden">
        {rows.map((r) => (
          <li
            key={r.id}
            className="rounded-card border border-line bg-surface p-4 shadow-card"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="font-medium text-ink">{r.full_name}</p>
                <p className="text-xs text-ink-muted">
                  {ROLE_LABEL[r.primary_department as ClinicRole] ?? r.primary_department}
                  {" · "}
                  <span className="text-ink-muted">{r.employment_type}</span>
                </p>
              </div>
              {r.is_active ? (
                <span className="inline-flex shrink-0 items-center gap-1 text-xs text-success">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  Active
                </span>
              ) : (
                <span className="shrink-0 text-xs text-ink-muted">Inactive</span>
              )}
            </div>
            <div className="mt-2 flex items-center justify-between gap-2">
              {r.auth_user_id ? (
                <span className="inline-flex items-center gap-1 text-xs text-success">
                  <span className="h-1.5 w-1.5 rounded-full bg-success" />
                  Đã link
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-xs text-warning">
                  <span className="h-1.5 w-1.5 rounded-full bg-warning" />
                  Chưa link
                </span>
              )}
              {r.auth_user_id ? (
                <AccountActions staffId={r.id} staffName={r.full_name} />
              ) : (
                <Link
                  href="/settings/new-user"
                  className="text-xs text-brand-600 hover:underline"
                >
                  Tạo tài khoản
                </Link>
              )}
            </div>
          </li>
        ))}
        {rows.length === 0 && (
          <li className="rounded-card border border-line bg-surface px-4 py-8 text-center text-sm text-ink-muted shadow-card">
            Chưa có nhân viên.
          </li>
        )}
      </ul>

      {/* Desktop: table (≥md). */}
      <div className="hidden min-h-[180px] max-h-[88vh] overflow-x-auto overflow-y-auto rounded-card border border-line bg-surface shadow-card md:block">
        <table className="min-w-full divide-y divide-brand-100 text-sm">
          <thead className="sticky top-0 z-10 bg-brand-100 text-left text-[11px] font-semibold uppercase tracking-wide text-brand-800">
            <tr>
              <th className={TH}>Họ tên</th>
              <th className={TH}>Vai trò</th>
              <th className={TH}>Hợp đồng</th>
              <th className={TH}>Active</th>
              <th className={TH}>Login</th>
              <th className={TH}>Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-100">
            {rows.map((r) => (
              <tr
                key={r.id}
                className="transition-colors duration-150 hover:bg-brand-50"
              >
                <td className={`${TD} text-ink`}>
                  {r.full_name}
                  {r.short_name && r.short_name !== r.full_name && (
                    <span className="ml-2 text-xs text-ink-muted">
                      {r.short_name}
                    </span>
                  )}
                </td>
                <td className={`${TD} text-ink-soft`}>
                  {ROLE_LABEL[r.primary_department as ClinicRole] ?? r.primary_department}
                </td>
                <td className={`${TD} text-xs text-ink-muted`}>
                  {r.employment_type}
                </td>
                <td className={TD}>
                  {r.is_active ? (
                    <span className="inline-flex items-center gap-1 text-xs text-success">
                      <span className="h-1.5 w-1.5 rounded-full bg-success" />
                      Active
                    </span>
                  ) : (
                    <span className="text-xs text-ink-muted">Inactive</span>
                  )}
                </td>
                <td className={TD}>
                  {r.auth_user_id ? (
                    <span className="inline-flex items-center gap-1 text-xs text-success">
                      <span className="h-1.5 w-1.5 rounded-full bg-success" />
                      Đã link
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-xs text-warning">
                      <span className="h-1.5 w-1.5 rounded-full bg-warning" />
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
                      className="text-xs text-brand-600 hover:underline"
                    >
                      Tạo tài khoản
                    </Link>
                  )}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-ink-muted">
                  Chưa có nhân viên.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
