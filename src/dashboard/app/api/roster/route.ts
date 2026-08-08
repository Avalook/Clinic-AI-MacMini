// Lịch làm việc — ghi/xoá phân công, và CHỐT một tuần.
//   GET    ?date=YYYY-MM-DD          → bác sĩ trực hôm đó (chỉ tuần ĐÃ ÁP DỤNG)
//   GET    ?tu=…&den=…               → những tuần đã áp dụng trong khoảng
//   GET    ?staff_id=…               → vị trí người này được xếp vào
//   POST   { week_start, work_date, … }  → thêm 1 ô
//   POST   { apply_week: "YYYY-MM-DD" }  → chốt cả tuần
//   DELETE { id }                        → xoá 1 ô
// Quản lý: xếp cho BẤT KỲ ai. Nhân sự khác (bác sĩ/lễ tân/điều dưỡng): chỉ TỰ
// đăng ký / xoá ca CỦA MÌNH (staff_id ép = chính mình) — feedback C4.
// Ghi qua service-role (work_roster chỉ có RLS SELECT, write phải bypass bằng key).

import { NextResponse } from "next/server";
import { fetchFromBackend, proxyJsonToBackend } from "../../../lib/backend-proxy";
import { getSupabaseServer } from "../../../lib/supabase-server";
import {
  getClinicRole,
  getClinicStaffId,
  getActiveStaff,
} from "../../../lib/clinic-session";
import { isAdminRole } from "../../../lib/roles";

/** Thứ Hai của tuần chứa `iso`. Cùng quy ước với week_start_of ở backend. */
function weekStartOf(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  const isoDow = ((d.getUTCDay() + 6) % 7) + 1; // 1 = thứ Hai
  d.setUTCDate(d.getUTCDate() - (isoDow - 1));
  return d.toISOString().slice(0, 10);
}

type Auth =
  | {
      ok: true;
      isAdmin: boolean;
      staffId: string | null;
      staffName: string;
    }
  | { ok: false; res: NextResponse };

async function authorize(): Promise<Auth> {
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
  return { ok: true, isAdmin, staffId, staffName };
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

  const sp = new URL(request.url).searchParams;

  // Nhánh 1: khoảng tuần → trả về những tuần ĐÃ ÁP DỤNG, để lưới lịch biết tuần
  // nào còn là dự kiến.
  const tu = (sp.get("tu") ?? "").trim();
  const den = (sp.get("den") ?? "").trim();
  if (tu && den) {
    const { data, error } = await caller
      .from("roster_week")
      .select("week_start")
      .gte("week_start", tu)
      .lte("week_start", den);
    if (error) return NextResponse.json({ error: error.message }, { status: 500 });
    return NextResponse.json({
      weeks: ((data as { week_start: string }[] | null) ?? []).map(
        (r) => r.week_start,
      ),
    });
  }

  // Nhánh 2: vị trí hợp lệ của MỘT nhân viên. Đi qua FastAPI vì cùng câu trả
  // lời ấy là thứ `add_shift` dùng để từ chối — hỏi hai nguồn là sớm muộn giao
  // diện sẽ mời một vị trí mà backend không nhận.
  const nhanSu = (sp.get("staff_id") ?? "").trim();
  if (nhanSu) {
    const data = await fetchFromBackend<{ tram: string[]; chua_khai: boolean }>(
      `/api/v1/roster/stations?staff_id=${encodeURIComponent(nhanSu)}`,
    );
    if (data === null) {
      return NextResponse.json(
        { error: "Không đọc được phạm vi vị trí." },
        { status: 503 },
      );
    }
    return NextResponse.json(data);
  }

  const date = (sp.get("date") ?? "").trim();
  if (!date) {
    return NextResponse.json({ error: "Missing date parameter" }, { status: 400 });
  }

  // CHỈ TUẦN ĐÃ ÁP DỤNG mới trả về bác sĩ trực.
  //
  // Sơ đồ đặt lịch vẽ hàng theo danh sách này; danh sách rỗng thì nó rơi về
  // "hiện mọi bác sĩ" — đúng thứ ta muốn cho một tuần chưa chốt. Trả về danh
  // sách lấy từ bản nháp thì màn hình nói chắc nịch ai trực ngày 12/12 trong
  // khi phòng khám chưa quyết. Xem migration 20260808000001.
  const tuan = weekStartOf(date);
  const { data: daApDung } = await caller
    .from("roster_week")
    .select("week_start")
    .eq("week_start", tuan)
    .maybeSingle();
  if (!daApDung) return NextResponse.json({ doctors: [], du_kien: true });

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
  return NextResponse.json({ doctors, du_kien: false });
}

interface PostBody {
  /** Chốt cả tuần (thứ Hai). Chỉ quản lý. */
  apply_week?: string;
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

  // Chốt cả tuần — việc khác hẳn với thêm một ô, nên tách nhánh ngay đầu.
  const apply_week = (body.apply_week ?? "").trim();
  if (apply_week) {
    if (!auth.isAdmin) {
      return NextResponse.json(
        { error: "Chỉ quản lý mới áp dụng được lịch trực." },
        { status: 403 },
      );
    }
    return proxyJsonToBackend("POST", "/api/v1/roster/weeks/apply", {
      week_start: apply_week,
    });
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

  // TÊN không còn nằm trong danh sách bắt buộc: từ 20260809000002 backend đọc
  // tên và chức danh THẲNG TỪ DATABASE theo staff_id, và bỏ qua chuỗi client
  // gửi lên. Bắt buộc nó ở đây chỉ tạo ra một lỗi 400 cho một trường không ai
  // dùng nữa.
  if (!week_start || !work_date || !station || (assignOther ? !staff_id : !staff_name)) {
    return NextResponse.json(
      { error: "Thiếu tuần / ngày / vị trí / nhân viên." },
      { status: 400 },
    );
  }

  // week_start is derived from work_date in FastAPI, for the same reason it
  // was derived here: the form keeps the previously viewed week in state, so a
  // client-supplied value files shifts under a week nobody was editing.
  return proxyJsonToBackend("POST", "/api/v1/roster/shifts", {
    work_date,
    station,
    shift,
    staff_id: assignOther ? staff_id : null,
    staff_name: assignOther ? staff_name : null,
    sort: body.sort ?? 0,
  });
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
  // Từ chối → lưu lý do; duyệt → xoá lý do cũ (phòng khi quản lý đổi ý). Cả hai
  // do RosterService quyết định, route chỉ chuyển nguyên văn.
  return proxyJsonToBackend("PATCH", `/api/v1/roster/shifts/${id}`, {
    decision: body.action,
    reason: body.reason ?? null,
  });
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

  // "Chỉ được xoá ca của chính mình" là luật của RosterService.remove — nó đọc
  // chủ ca trong cùng transaction với lệnh xoá, nên không có khe đua.
  return proxyJsonToBackend("DELETE", `/api/v1/roster/shifts/${id}`, {});
}
