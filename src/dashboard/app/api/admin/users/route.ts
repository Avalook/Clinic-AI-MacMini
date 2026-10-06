// Tài khoản đăng nhập của nhân viên (/settings/tai-khoan, /settings/new-user).
//
//   GET                                       → { emails: { staffId: email } }
//   POST   { email, password, staffId }      → tạo người dùng GoTrue + nối nhân viên
//   PATCH  { staffId, action: "reset_password", password }  → đặt lại mật khẩu
//   PATCH  { staffId, action: "change_email", email }        → đổi tên đăng nhập
//   PATCH  { staffId, action: "unlink" }      → thu hồi: gỡ nối + khoá
//                                               app_credential, rồi xoá GoTrue
//
// CHIA VIỆC (06/10/2026). File này CHỈ còn giữ lời gọi quản trị GoTrue — thứ
// duy nhất cần khoá service-role (ADR-0012). Không đọc/ghi bảng nào: ai thuộc
// phòng khám nào, nối/gỡ `staff.auth_user_id`, khoá `app_credential`, nhật ký
// đều ở FastAPI (`TaiKhoanService`, cửa `account.manage`, lọc theo phòng khám
// của người gọi). Mỗi lời gọi GoTrue đi SAU một lời gọi backend đã gác quyền
// và phạm vi cho đúng nhân viên ấy.
//
// SECURITY
// - SUPABASE_SERVICE_ROLE_KEY chỉ đọc từ môi trường máy chủ, không ra trình duyệt.
// - Thiếu khoá → mọi phương thức 503 (đóng cửa, không mở).

import { NextResponse } from "next/server";
import {
  emailTuTenDangNhap,
  loiTenDangNhap,
} from "../../../../lib/ten-dang-nhap";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import {
  docTuBackend,
  fetchFromBackend,
  proxyJsonToBackend,
} from "../../../../lib/backend-proxy";

const MIN_PASSWORD = 8;

interface TaiKhoan {
  id: string;
  full_name: string;
  auth_user_id: string | null;
}

// Đổi mật khẩu / đổi tên đăng nhập: GoTrue làm xong mới ghi. Ghi hỏng thì không
// huỷ thao tác đã xong, nhưng báo ra log máy chủ. Không gửi mật khẩu.
// (Tạo / thu hồi ghi nhật ký trong giao dịch của backend.)
async function ghiNhatKy(
  staffId: string,
  hanhDong: "doi_mat_khau" | "doi_ten_dang_nhap",
): Promise<void> {
  const res = await proxyJsonToBackend(
    "POST",
    `/api/v1/staff/${encodeURIComponent(staffId)}/nhat-ky-tai-khoan`,
    { hanh_dong: hanhDong },
  );
  if (res.status >= 300) {
    console.error("nhat_ky_tai_khoan_that_bai", staffId, hanhDong, res.status);
  }
}

/** Nhân viên cùng phòng khám (backend gác `account.manage` + phạm vi), hoặc lỗi. */
function docTaiKhoan(staffId: string) {
  return docTuBackend<TaiKhoan>(
    `/api/v1/staff/${encodeURIComponent(staffId)}/tai-khoan`,
  );
}

type AuthResult =
  | { ok: true; admin: SupabaseClient }
  | { ok: false; res: NextResponse };

// Cổng chung: có phiên + có khoá + người gọi có quyền account.manage. Backend gác
// lại ở từng lời gọi; cổng này để không lời gọi GoTrue nào chạy trước khi biết.
async function authorizeAdmin(): Promise<AuthResult> {
  // Cookie clinic_role do trình duyệt giữ — không phải bằng chứng quyền.
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
  // Tên biến lấy qua ngoặc vuông: chốt bí mật trước commit bắt mẫu `_KEY = <chuỗi>`
  // và đọc nhầm một THAM CHIẾU biến môi trường thành bí mật ghi cứng.
  const khoaDichVu = process.env["SUPABASE_SERVICE_ROLE_KEY"];
  if (!SUPABASE_URL || !khoaDichVu) {
    return {
      ok: false,
      res: NextResponse.json(
        { error: "Admin service is temporarily unavailable." },
        { status: 503 },
      ),
    };
  }

  // LEGO 19 "Nhân sự & phân quyền": hỏi QUYỀN `account.manage` ở backend (nguồn
  // sự thật duy nhất về quyền và phòng khám), bằng phiên của chính người gọi.
  const quyen = await fetchFromBackend<{ quyen: string[] }>("/api/v1/phan-quyen/toi");
  if (!quyen?.quyen.includes("account.manage")) {
    return {
      ok: false,
      res: NextResponse.json({ error: "Forbidden" }, { status: 403 }),
    };
  }

  const admin = createClient(SUPABASE_URL, khoaDichVu, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return { ok: true, admin };
}

interface CreateBody {
  email?: string;
  password?: string;
  staffId?: string;
}

// Tên đăng nhập của từng nhân viên. `auth.users` chỉ khoá dịch vụ đọc được, và
// ADR-0012 cấm file khác với ra khoá đó — nên nó phải đi qua đúng route này.
// MỘT lượt gọi cho cả bảng, không phải mỗi dòng một lượt.
export async function GET() {
  const auth = await authorizeAdmin();
  if (!auth.ok) return auth.res;
  const { admin } = auth;

  const [{ data: users }, nhanVien] = await Promise.all([
    admin.auth.admin.listUsers({ perPage: 1000 }),
    docTuBackend<TaiKhoan[]>("/api/v1/staff/tai-khoan"),
  ]);
  if (!nhanVien.ok) return nhanVien.res;

  const theoUid = new Map(
    (users?.users ?? []).map((u) => [u.id, u.email ?? ""]),
  );
  const emails: Record<string, string> = {};
  for (const s of nhanVien.data) {
    if (!s.auth_user_id) continue;
    const mail = theoUid.get(s.auth_user_id);
    if (mail) emails[s.id] = mail;
  }
  return NextResponse.json({ ok: true, emails });
}

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
  const loiNick = loiTenDangNhap(body.email ?? "");
  if (loiNick) {
    return NextResponse.json({ error: loiNick }, { status: 400 });
  }
  const email = emailTuTenDangNhap(body.email ?? "");
  const password = body.password ?? "";
  const staffId = (body.staffId ?? "").trim();
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

  // Cùng phòng khám + còn chưa nối? Hỏi trước để không tạo người dùng GoTrue
  // thừa trong ca thường gặp; backend vẫn kiểm lại lúc nối (khoá dòng).
  const doc = await docTaiKhoan(staffId);
  if (!doc.ok) return doc.res;
  if (doc.data.auth_user_id) {
    return NextResponse.json(
      { error: "Nhân viên này đã được link với tài khoản khác." },
      { status: 409 },
    );
  }

  // Tự xác nhận email để quản lý giao thông tin đăng nhập ngay.
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

  // Nối + mở lại app_credential đã thu hồi (hoàn tác) + nhật ký: một giao dịch.
  // Hỏng thì xoá người dùng GoTrue vừa tạo, không để tài khoản mồ côi.
  const noi = await proxyJsonToBackend(
    "POST",
    `/api/v1/staff/${encodeURIComponent(staffId)}/tai-khoan/noi`,
    { auth_user_id: newUserId },
  );
  if (!noi.ok) {
    await admin.auth.admin.deleteUser(newUserId);
    const loi = (await noi.json().catch(() => ({}))) as { error?: string };
    return NextResponse.json(
      {
        error:
          "Không nối được nhân viên; tài khoản vừa tạo đã được xoá. " +
          (loi.error ?? ""),
      },
      { status: noi.status },
    );
  }

  return NextResponse.json({
    ok: true,
    userId: newUserId,
    email,
    staffId,
    staffName: doc.data.full_name,
  });
}

interface PatchBody {
  staffId?: string;
  action?: "reset_password" | "change_email" | "unlink";
  password?: string;
  email?: string;
}

// Tài khoản đã nối: đặt lại mật khẩu, đổi tên đăng nhập, hoặc thu hồi.
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

  const doc = await docTaiKhoan(staffId);
  if (!doc.ok) return doc.res;
  const target = doc.data;
  const authUserId = target.auth_user_id;
  if (!authUserId) {
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
    const { error } = await admin.auth.admin.updateUserById(authUserId, {
      password,
    });
    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }
    await ghiNhatKy(staffId, "doi_mat_khau");
    return NextResponse.json({
      ok: true,
      action,
      staffName: target.full_name,
    });
  }

  if (action === "change_email") {
    // Tên trần được: đuôi do `emailTuTenDangNhap` gắn, cùng hàm mà màn đăng
    // nhập dùng — nên nick quản lý đặt ở đây gõ vào đâu cũng vào được.
    const loi = loiTenDangNhap(body.email ?? "");
    if (loi) return NextResponse.json({ error: loi }, { status: 400 });
    const email = emailTuTenDangNhap(body.email ?? "");
    // `email_confirm: true` đi kèm là BẮT BUỘC. Đổi email mà không xác nhận
    // luôn thì GoTrue treo địa chỉ mới ở trạng thái chờ và gửi thư xác nhận —
    // phòng khám không có hòm thư nào để nhận, nên người đó mất đường vào cho
    // tới khi ai đó sửa tay trong database.
    const { error } = await admin.auth.admin.updateUserById(authUserId, {
      email,
      email_confirm: true,
    });
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
    await ghiNhatKy(staffId, "doi_ten_dang_nhap");
    return NextResponse.json({
      ok: true,
      action,
      email,
      staffName: target.full_name,
    });
  }

  if (action === "unlink") {
    // Backend TRƯỚC (gỡ nối + khoá app_credential + nhật ký, một giao dịch,
    // 409 nếu tài khoản đã đổi từ lúc đọc), GoTrue SAU. Xoá GoTrue hỏng thì
    // người dùng ấy không còn nối nhân viên nào — không vào được gì.
    const thuHoi = await proxyJsonToBackend(
      "POST",
      `/api/v1/staff/${encodeURIComponent(staffId)}/tai-khoan/thu-hoi`,
      { auth_user_id: authUserId },
    );
    if (!thuHoi.ok) return thuHoi;
    const del = await admin.auth.admin.deleteUser(authUserId);
    if (del.error) {
      return NextResponse.json(
        {
          ok: true,
          action,
          staffName: target.full_name,
          warning:
            "Đã thu hồi, nhưng xoá tài khoản GoTrue lỗi: " + del.error.message,
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
    { error: "action không hợp lệ (reset_password | change_email | unlink)." },
    { status: 400 },
  );
}
