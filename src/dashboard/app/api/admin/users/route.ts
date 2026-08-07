// Admin-only account management endpoint.
//
//   GET                                       → { emails: { staffId: email } }
//   POST   { email, password, staffId }      → create Auth user + link staff
//   PATCH  { staffId, action: "reset_password", password }  → reset password
//   PATCH  { staffId, action: "change_email", email }        → đổi tên đăng nhập
//   PATCH  { staffId, action: "unlink" }      → revoke: null the FK + delete
//                                               the Auth user (staff row kept)
//
// Every method:
//   1. Verifies the caller's Supabase session and that the linked staff
//      row has primary_department === 'MANAGEMENT'. Anything else → 403.
//   2. Uses the service-role client for the privileged Auth ops.
//
// SECURITY
// - SUPABASE_SERVICE_ROLE_KEY is read from the server environment only.
//   It is never sent to the client.
// - Unknown methods get the default 405.
// - If SUPABASE_SERVICE_ROLE_KEY is unset, every method fails closed (503).

import { NextResponse } from "next/server";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import {
  resolveLinkedStaffAuthority,
  resolveSingleManagementClinic,
} from "../../../../lib/identity-authority";

const MIN_PASSWORD = 8;

type AuthResult =
  | { ok: true; admin: SupabaseClient; clinicId: string }
  | { ok: false; res: NextResponse };

// Shared gate: env present + caller authenticated + caller is MANAGEMENT.
// Returns a ready service-role client on success, or the error response.
async function authorizeAdmin(): Promise<AuthResult> {
  // Authenticate first. A clinic_role cookie is intentionally ignored because
  // cookies are client-controlled presentation state, not authorization.
  const callerClient = await getSupabaseServer();
  const {
    data: { user },
  } = await callerClient.auth.getUser();
  if (!user) {
    return {
      ok: false,
      res: NextResponse.json({ error: "Unauthorised" }, { status: 401 }),
    };
  }

  // Địa chỉ NỘI BỘ trước — route này chạy trong container, xem proxy.ts.
  const SUPABASE_URL =
    process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return {
      ok: false,
      res: NextResponse.json(
        { error: "Admin service is temporarily unavailable." },
        { status: 503 },
      ),
    };
  }

  const admin = createClient(SUPABASE_URL, SERVICE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data: callerStaff, error: callerStaffError } = await admin
    .from("staff")
    .select("id, auth_user_id, primary_department, is_active")
    .eq("auth_user_id", user.id)
    .maybeSingle();
  const callerIdentity = resolveLinkedStaffAuthority(user.id, callerStaff);
  if (callerStaffError || !callerIdentity) {
    return {
      ok: false,
      res: NextResponse.json({ error: "Forbidden" }, { status: 403 }),
    };
  }

  // clinic_membership.role is the tenant authority. primary_department is
  // descriptive staff data and may differ between clinics.
  const { data: memberships, error: membershipError } = await admin
    .from("clinic_membership")
    .select("clinic_id, role, is_active")
    .eq("staff_id", callerIdentity.id)
    .eq("is_active", true);
  const clinicId = resolveSingleManagementClinic(memberships ?? []);
  if (membershipError || !clinicId) {
    return {
      ok: false,
      res: NextResponse.json({ error: "Forbidden" }, { status: 403 }),
    };
  }

  return { ok: true, admin, clinicId };
}

async function requireTargetMembership(
  admin: SupabaseClient,
  staffId: string,
  clinicId: string,
): Promise<NextResponse | null> {
  const { data, error } = await admin
    .from("clinic_membership")
    .select("staff_id")
    .eq("staff_id", staffId)
    .eq("clinic_id", clinicId)
    .eq("is_active", true)
    .limit(1)
    .maybeSingle();
  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  if (!data) {
    // Do not reveal whether the id exists in another tenant.
    return NextResponse.json(
      { error: "Nhân viên không tồn tại trong phòng khám hiện tại." },
      { status: 404 },
    );
  }
  return null;
}

interface CreateBody {
  email?: string;
  password?: string;
  staffId?: string;
}

// Create a new Auth user and link it to an existing, unlinked staff row.
// Tên đăng nhập của từng nhân viên. `auth.users` chỉ khoá dịch vụ đọc được, và
// ADR-0012 cấm file khác với ra khoá đó — nên nó phải đi qua đúng route này.
// MỘT lượt gọi cho cả bảng, không phải mỗi dòng một lượt.
export async function GET() {
  const auth = await authorizeAdmin();
  if (!auth.ok) return auth.res;
  const { admin, clinicId } = auth;

  const [{ data: users }, { data: staff }] = await Promise.all([
    admin.auth.admin.listUsers({ perPage: 1000 }),
    admin
      .from("clinic_membership")
      .select("staff:staff!staff_id(id, auth_user_id)")
      .eq("clinic_id", clinicId)
      .eq("is_active", true),
  ]);

  const theoUid = new Map(
    (users?.users ?? []).map((u) => [u.id, u.email ?? ""]),
  );
  const emails: Record<string, string> = {};
  for (const row of staff ?? []) {
    // Nhúng nhiều-một của PostgREST trả về OBJECT, nhưng kiểu sinh ra khai là
    // mảng — nhận cả hai để không lệ thuộc vào chỗ đó.
    const raw = (row as { staff: unknown }).staff;
    const s = (Array.isArray(raw) ? raw[0] : raw) as
      | { id: string; auth_user_id: string | null }
      | undefined;
    if (!s?.auth_user_id) continue;
    const mail = theoUid.get(s.auth_user_id);
    if (mail) emails[s.id] = mail;
  }
  return NextResponse.json({ ok: true, emails });
}

export async function POST(request: Request) {
  const auth = await authorizeAdmin();
  if (!auth.ok) return auth.res;
  const { admin, clinicId } = auth;

  let body: CreateBody;
  try {
    body = (await request.json()) as CreateBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const email = (body.email ?? "").trim();
  const password = body.password ?? "";
  const staffId = (body.staffId ?? "").trim();
  if (!email || !email.includes("@")) {
    return NextResponse.json({ error: "Email không hợp lệ." }, { status: 400 });
  }
  if (password.length < MIN_PASSWORD) {
    return NextResponse.json(
      { error: `Mật khẩu phải có ít nhất ${MIN_PASSWORD} ký tự.` },
      { status: 400 },
    );
  }
  if (!staffId) {
    return NextResponse.json(
      { error: "Phải chọn nhân viên để link." },
      { status: 400 },
    );
  }

  const membershipError = await requireTargetMembership(
    admin,
    staffId,
    clinicId,
  );
  if (membershipError) return membershipError;

  // Target staff exists + still unlinked?
  const { data: targetStaff, error: targetErr } = await admin
    .from("staff")
    .select("id, full_name, auth_user_id")
    .eq("id", staffId)
    .maybeSingle();
  if (targetErr) {
    return NextResponse.json({ error: targetErr.message }, { status: 500 });
  }
  if (!targetStaff) {
    return NextResponse.json(
      { error: "Nhân viên không tồn tại." },
      { status: 404 },
    );
  }
  if (targetStaff.auth_user_id) {
    return NextResponse.json(
      { error: "Nhân viên này đã được link với tài khoản khác." },
      { status: 409 },
    );
  }

  // Create the Auth user (auto-confirmed so the operator can hand over the
  // credentials immediately).
  const created = await admin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  });
  if (created.error || !created.data.user) {
    return NextResponse.json(
      { error: created.error?.message ?? "Failed to create user" },
      { status: 500 },
    );
  }
  const newUserId = created.data.user.id;

  // Link staff.auth_user_id. Rollback the Auth user on failure so we don't
  // strand an unlinkable account.
  const linkRes = await admin
    .from("staff")
    .update({ auth_user_id: newUserId })
    .eq("id", staffId)
    .is("auth_user_id", null)
    .select("id")
    .maybeSingle();
  if (linkRes.error || !linkRes.data) {
    await admin.auth.admin.deleteUser(newUserId);
    return NextResponse.json(
      {
        error:
          "Linked staff row update failed; the Auth user was rolled back. " +
          (linkRes.error?.message ?? "Staff was linked concurrently."),
      },
      { status: linkRes.error ? 500 : 409 },
    );
  }

  return NextResponse.json({
    ok: true,
    userId: newUserId,
    email,
    staffId,
    staffName: targetStaff.full_name,
  });
}

interface PatchBody {
  staffId?: string;
  action?: "reset_password" | "change_email" | "unlink";
  password?: string;
  email?: string;
}

// Manage an already-linked account: reset its password, or revoke it
// entirely (unlink + delete the Auth user, keeping the staff row).
export async function PATCH(request: Request) {
  const auth = await authorizeAdmin();
  if (!auth.ok) return auth.res;
  const { admin, clinicId } = auth;

  let body: PatchBody;
  try {
    body = (await request.json()) as PatchBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const staffId = (body.staffId ?? "").trim();
  const action = body.action;
  if (!staffId) {
    return NextResponse.json({ error: "Thiếu staffId." }, { status: 400 });
  }

  const membershipError = await requireTargetMembership(
    admin,
    staffId,
    clinicId,
  );
  if (membershipError) return membershipError;

  const { data: target, error: targetErr } = await admin
    .from("staff")
    .select("id, full_name, auth_user_id")
    .eq("id", staffId)
    .maybeSingle();
  if (targetErr) {
    return NextResponse.json({ error: targetErr.message }, { status: 500 });
  }
  if (!target) {
    return NextResponse.json(
      { error: "Nhân viên không tồn tại." },
      { status: 404 },
    );
  }
  if (!target.auth_user_id) {
    return NextResponse.json(
      { error: "Nhân viên này chưa có tài khoản đăng nhập." },
      { status: 409 },
    );
  }

  if (action === "reset_password") {
    const password = body.password ?? "";
    if (password.length < MIN_PASSWORD) {
      return NextResponse.json(
        { error: `Mật khẩu phải có ít nhất ${MIN_PASSWORD} ký tự.` },
        { status: 400 },
      );
    }
    const { error } = await admin.auth.admin.updateUserById(
      target.auth_user_id,
      { password },
    );
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    return NextResponse.json({
      ok: true,
      action,
      staffName: target.full_name,
    });
  }

  if (action === "change_email") {
    const email = (body.email ?? "").trim().toLowerCase();
    if (!email || !email.includes("@")) {
      return NextResponse.json(
        { error: "Tên đăng nhập phải là một địa chỉ email." },
        { status: 400 },
      );
    }
    // `email_confirm: true` đi kèm là BẮT BUỘC. Đổi email mà không xác nhận
    // luôn thì GoTrue treo địa chỉ mới ở trạng thái chờ và gửi thư xác nhận —
    // phòng khám không có hòm thư nào để nhận, nên người đó mất đường vào cho
    // tới khi ai đó sửa tay trong database.
    const { error } = await admin.auth.admin.updateUserById(
      target.auth_user_id,
      { email, email_confirm: true },
    );
    if (error) {
      // GoTrue trả 422 khi email đã có người dùng. Nói ra bằng tiếng Việt chứ
      // đừng để quản lý đọc "email address has already been registered".
      const trung = /already/i.test(error.message);
      return NextResponse.json(
        {
          error: trung
            ? `Tên đăng nhập ${email} đã có người dùng.`
            : error.message,
        },
        { status: trung ? 409 : 500 },
      );
    }
    return NextResponse.json({
      ok: true,
      action,
      email,
      staffName: target.full_name,
    });
  }

  if (action === "unlink") {
    // Null the FK first so the staff row is never left pointing at a
    // deleted Auth user, then delete the Auth user to revoke login.
    const upd = await admin
      .from("staff")
      .update({ auth_user_id: null })
      .eq("id", staffId)
      .eq("auth_user_id", target.auth_user_id)
      .select("id")
      .maybeSingle();
    if (upd.error || !upd.data) {
      return NextResponse.json(
        {
          error:
            upd.error?.message ??
            "Tài khoản đã thay đổi; vui lòng tải lại trước khi gỡ.",
        },
        { status: upd.error ? 500 : 409 },
      );
    }
    const del = await admin.auth.admin.deleteUser(target.auth_user_id);
    if (del.error) {
      // FK already cleared; the orphan Auth user can be removed in the
      // console. Surface it rather than pretend full success.
      return NextResponse.json(
        {
          ok: true,
          action,
          staffName: target.full_name,
          warning:
            "Đã gỡ liên kết, nhưng xoá tài khoản Auth lỗi: " + del.error.message,
        },
        { status: 200 },
      );
    }
    return NextResponse.json({
      ok: true,
      action,
      staffName: target.full_name,
    });
  }

  return NextResponse.json(
    { error: "action không hợp lệ (reset_password | unlink)." },
    { status: 400 },
  );
}
