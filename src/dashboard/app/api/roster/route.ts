// Lịch làm việc — ghi/xoá phân công.
//   POST   { week_start, work_date, shift, station, staff_id?, staff_name? }  → thêm 1 ô
//   DELETE { id }                                                            → xoá 1 ô
// Quản lý: xếp cho BẤT KỲ ai. Nhân sự khác (bác sĩ/lễ tân/điều dưỡng): chỉ TỰ
// đăng ký / xoá ca CỦA MÌNH (staff_id ép = chính mình) — feedback C4.
// Ghi qua service-role (work_roster chỉ có RLS SELECT, write phải bypass bằng key).

import { NextResponse } from "next/server";
import { configViaBackend, proxyJsonToBackend } from "../../../lib/backend-proxy";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { getSupabaseServer } from "../../../lib/supabase-server";
import {
  getClinicRole,
  getClinicStaffId,
  getActiveStaff,
} from "../../../lib/clinic-session";
import { isAdminRole } from "../../../lib/roles";
import { weekStartOf } from "../../../lib/roster";

type Auth =
  | {
      ok: true;
      admin: SupabaseClient;
      isAdmin: boolean;
      staffId: string | null;
      staffName: string;
    }
  | { ok: false; res: NextResponse };

async function authorize(): Promise<Auth> {
  const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!SUPABASE_URL || !SERVICE_KEY) {
    return {
      ok: false,
      res: NextResponse.json(
        { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
        { status: 503 },
      ),
    };
  }
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) {
    return { ok: false, res: NextResponse.json({ error: "Unauthorised" }, { status: 401 }) };
  }
  // Quyền "duyệt + tự duyệt + xếp cho người khác" CHỈ thuộc Quản lý hệ thống
  // (MANAGEMENT). Trưởng ca dưới quản lý → đăng ký ca như nhân viên (PENDING).
  const isAdmin = isAdminRole(await getClinicRole());
  const staffId = await getClinicStaffId();
  const staff = await getActiveStaff();
  const staffName = staff?.full_name ?? staff?.short_name ?? "";
  // Không phải quản lý mà chưa chọn danh tính → không tự đăng ký ca được.
  if (!isAdmin && !staffId) {
    return {
      ok: false,
      res: NextResponse.json({ error: "Chưa chọn danh tính nhân viên." }, { status: 403 }),
    };
  }
  const admin = createClient(SUPABASE_URL, SERVICE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return { ok: true, admin, isAdmin, staffId, staffName };
}

// Bác sĩ TRỰC CA của một ngày — nuôi sơ đồ đặt chỗ (chỉ hiện bác sĩ trực hôm đó).
//   GET ?date=YYYY-MM-DD → { doctors: [{ id, name }] }
// Lấy từ work_roster station LICH_KHAM đã DUYỆT; bỏ dòng thiếu staff_id (tên gõ
// tay không nối được với combobox bác sĩ). Đọc bằng phiên người gọi (work_roster
// có RLS SELECT) — không cần service-role.
export async function GET(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const date = (new URL(request.url).searchParams.get("date") ?? "").trim();
  if (!date) {
    return NextResponse.json({ error: "Missing date parameter" }, { status: 400 });
  }

  const { data, error } = await caller
    .from("work_roster")
    .select("staff_id, staff_name")
    .eq("work_date", date)
    .eq("station", "LICH_KHAM")
    .eq("status", "APPROVED")
    .not("staff_id", "is", null);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  // 1 bác sĩ có thể có nhiều dòng (SANG + CHIEU) → khử trùng theo staff_id.
  const seen = new Set<string>();
  const doctors: { id: string; name: string }[] = [];
  for (const r of (data as { staff_id: string; staff_name: string | null }[] | null) ?? []) {
    if (seen.has(r.staff_id)) continue;
    seen.add(r.staff_id);
    doctors.push({ id: r.staff_id, name: r.staff_name ?? "" });
  }
  return NextResponse.json({ doctors });
}

interface PostBody {
  week_start?: string;
  work_date?: string;
  shift?: string;
  station?: string;
  staff_id?: string | null;
  staff_name?: string;
  sort?: number;
}

export async function POST(request: Request) {
  const auth = await authorize();
  if (!auth.ok) return auth.res;

  let body: PostBody;
  try {
    body = (await request.json()) as PostBody;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const week_start = (body.week_start ?? "").trim();
  const work_date = (body.work_date ?? "").trim();
  const station = (body.station ?? "").trim();
  const shift = body.shift === "SANG" || body.shift === "CHIEU" ? body.shift : "FULL";

  // Quản lý XẾP CHO NGƯỜI KHÁC khi gửi kèm staff_id (qua /schedule/edit). Mọi
  // trường hợp còn lại — gồm Quản lý TỰ đăng ký trên bảng (không gửi staff_id) —
  // ép staff_id/name = chính người gọi. Nhờ vậy bảng đăng ký không cần gửi tên.
  const assignOther = auth.isAdmin && !!body.staff_id;
  const staff_id = assignOther ? body.staff_id || null : auth.staffId;
  const staff_name = assignOther
    ? (body.staff_name ?? "").trim()
    : auth.staffName;

  if (!week_start || !work_date || !station || !staff_name) {
    return NextResponse.json(
      { error: "Thiếu tuần / ngày / vị trí / nhân viên." },
      { status: 400 },
    );
  }

  // W5 (ADR-0012). week_start is derived from work_date on the server for the
  // same reason it is here. Off until CONFIG_VIA_BACKEND=1.
  if (configViaBackend()) {
    return proxyJsonToBackend("POST", "/api/v1/roster/shifts", {
      work_date,
      station,
      shift,
      staff_id: assignOther ? staff_id : null,
      staff_name: assignOther ? staff_name : null,
      sort: body.sort ?? 0,
    });
  }

  const { data, error } = await auth.admin
    .from("work_roster")
    .insert({
      // Tính week_start TỪ work_date (không tin client) — tránh lệch tuần khi
      // form còn giữ ngày cũ lúc người dùng chuyển tuần (state không reset).
      week_start: weekStartOf(work_date),
      work_date,
      shift,
      station,
      staff_id,
      staff_name,
      sort: body.sort ?? 0,
      // Quản lý xếp lịch → duyệt luôn. Nhân viên tự đăng ký → chờ duyệt, chưa
      // hiện trên lịch chung tới khi quản lý duyệt (xem PATCH bên dưới).
      status: auth.isAdmin ? "APPROVED" : "PENDING",
    })
    .select("id")
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true, id: data.id });
}

// Quản lý duyệt / từ chối ca tự đăng ký (PENDING). Body: { id, action }.
//  - approve → status = APPROVED (hiện lên lịch chung).
//  - reject  → status = REJECTED (ẩn khỏi lịch chung, lưu lại để đối chiếu).
export async function PATCH(request: Request) {
  const auth = await authorize();
  if (!auth.ok) return auth.res;
  if (!auth.isAdmin) {
    return NextResponse.json(
      { error: "Chỉ quản lý được duyệt ca." },
      { status: 403 },
    );
  }

  let body: { id?: string; action?: string; reason?: string };
  try {
    body = (await request.json()) as {
      id?: string;
      action?: string;
      reason?: string;
    };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id." }, { status: 400 });
  if (body.action !== "approve" && body.action !== "reject") {
    return NextResponse.json({ error: "action không hợp lệ." }, { status: 400 });
  }
  const status = body.action === "approve" ? "APPROVED" : "REJECTED";
  // Từ chối → lưu lý do (cắt gọn để người đăng ký biết). Duyệt → xoá lý do cũ
  // (phòng khi ca từng bị từ chối rồi quản lý đổi ý duyệt lại).
  const reject_reason =
    body.action === "reject" ? (body.reason ?? "").trim() || null : null;

  if (configViaBackend()) {
    return proxyJsonToBackend("PATCH", `/api/v1/roster/shifts/${id}`, {
      decision: body.action,
      reason: body.reason ?? null,
    });
  }

  const { error } = await auth.admin
    .from("work_roster")
    .update({ status, reject_reason, updated_at: new Date().toISOString() })
    .eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}

export async function DELETE(request: Request) {
  const auth = await authorize();
  if (!auth.ok) return auth.res;

  let body: { id?: string };
  try {
    body = (await request.json()) as { id?: string };
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const id = (body.id ?? "").trim();
  if (!id) return NextResponse.json({ error: "Thiếu id." }, { status: 400 });

  // Không phải quản lý → chỉ được xoá ô CỦA MÌNH.
  if (!auth.isAdmin) {
    const { data: row } = await auth.admin
      .from("work_roster")
      .select("staff_id")
      .eq("id", id)
      .maybeSingle();
    if (!row || row.staff_id !== auth.staffId) {
      return NextResponse.json(
        { error: "Chỉ được xoá ca của chính mình." },
        { status: 403 },
      );
    }
  }

  if (configViaBackend()) {
    return proxyJsonToBackend("DELETE", `/api/v1/roster/shifts/${id}`, {});
  }

  const { error } = await auth.admin.from("work_roster").delete().eq("id", id);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
