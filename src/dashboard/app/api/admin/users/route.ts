// Admin-only account management endpoint.
//
//   POST   { email, password, staffId }      → create Auth user + link staff
//   PATCH  { staffId, action: "reset_password", password }  → reset password
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
import { getClinicRole } from "../../../../lib/clinic-session";

const MIN_PASSWORD = 8;

type AuthResult =
  | { ok: true; admin: SupabaseClient }
  | { ok: false; res: NextResponse };

// Shared gate: env present + caller authenticated + caller is MANAGEMENT.
// Returns a ready service-role client on success, or the error response.
async function authorizeAdmin(): Promise<AuthResult> {
  const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return {
      ok: false,
      res: NextResponse.json(
        {
          error:
            "SUPABASE_SERVICE_ROLE_KEY is not configured on the server. " +
            "Add it to src/dashboard/.env.local and restart the dashboard.",
        },
        { status: 503 },
      ),
    };
  }

  // Must hold the shared clinic session (RLS) AND have picked the MANAGEMENT
  // role at /role-picker. Role is app-state in a cookie, not staff linkage.
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
  if ((await getClinicRole()) !== "MANAGEMENT") {
    return {
      ok: false,
      res: NextResponse.json({ error: "Forbidden" }, { status: 403 }),
    };
  }

  const admin = createClient(SUPABASE_URL, SERVICE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return { ok: true, admin };
}

interface CreateBody {
  email?: string;
  password?: string;
  staffId?: string;
}

// Create a new Auth user and link it to an existing, unlinked staff row.
export async function POST(request: Request) {
  const auth = await authorizeAdmin();
  if (!auth.ok) return auth.res;
  const { admin } = auth;

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
    .is("auth_user_id", null);
  if (linkRes.error) {
    await admin.auth.admin.deleteUser(newUserId);
    return NextResponse.json(
      {
        error:
          "Linked staff row update failed; the Auth user was rolled back. " +
          linkRes.error.message,
      },
      { status: 500 },
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
  action?: "reset_password" | "unlink";
  password?: string;
}

// Manage an already-linked account: reset its password, or revoke it
// entirely (unlink + delete the Auth user, keeping the staff row).
export async function PATCH(request: Request) {
  const auth = await authorizeAdmin();
  if (!auth.ok) return auth.res;
  const { admin } = auth;

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

  if (action === "unlink") {
    // Null the FK first so the staff row is never left pointing at a
    // deleted Auth user, then delete the Auth user to revoke login.
    const upd = await admin
      .from("staff")
      .update({ auth_user_id: null })
      .eq("id", staffId);
    if (upd.error) {
      return NextResponse.json({ error: upd.error.message }, { status: 500 });
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
