// /api/payment — chốt / hoàn tác thu tiền 1 khâu của 1 lượt khám.
//   POST   { visitId, clinicPatientId?, kind, amount? }  → đánh dấu ĐÃ THU (upsert PAID).
//   DELETE { visitId, kind }                             → hoàn tác (xoá dòng).
// kind = 'thuoc' | 'dich_vu'. Gate: vai thu ngân + kind thuộc quyền của vai đó
// (CASHIER_THUOC→thuoc, CASHIER_DV→dich_vu, CASHIER→cả hai). Ghi qua service-role
// (payment chỉ có RLS SELECT). KHÔNG đụng visit/appointment/lâm sàng.

import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { getSupabaseService } from "../../../lib/supabase-service";
import { getClinicRole, getClinicStaffId } from "../../../lib/clinic-session";
import { isCashierRole, type ClinicRole } from "../../../lib/roles";
import { paymentViaBackend, proxyJsonToBackend } from "../../../lib/backend-proxy";

type Kind = "thuoc" | "dich_vu";

// Khâu thu ngân được phép theo vai (khớp cashierModes ở tasks/page.tsx).
function allowedKinds(role: ClinicRole | null): Kind[] {
  if (role === "CASHIER_THUOC") return ["thuoc"];
  if (role === "CASHIER_DV") return ["dich_vu"];
  if (role === "CASHIER" || role === "MANAGEMENT") return ["thuoc", "dich_vu"];
  return [];
}

async function guard(kind: unknown) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) {
    return { res: NextResponse.json({ error: "Unauthorised" }, { status: 401 }) };
  }
  const role = await getClinicRole();
  if (!isCashierRole(role) && role !== "MANAGEMENT") {
    return { res: NextResponse.json({ error: "Chỉ thu ngân được thao tác thanh toán." }, { status: 403 }) };
  }
  if (kind !== "thuoc" && kind !== "dich_vu") {
    return { res: NextResponse.json({ error: "kind phải là thuoc / dich_vu." }, { status: 400 }) };
  }
  if (!allowedKinds(role).includes(kind)) {
    return { res: NextResponse.json({ error: `Vai này không thu khâu ${kind}.` }, { status: 403 }) };
  }
  const db = getSupabaseService();
  if (!db) {
    return { res: NextResponse.json({ error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình." }, { status: 503 }) };
  }
  return { user, role, db, kind: kind as Kind };
}

export async function POST(request: Request) {
  if (paymentViaBackend()) {
    let raw: unknown;
    try {
      raw = await request.json();
    } catch {
      return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
    }
    const p = (raw ?? {}) as {
      visitId?: string;
      clinicPatientId?: string;
      kind?: string;
      amount?: number;
    };
    return proxyJsonToBackend("POST", "/api/v1/payments", {
      visit_id: p.visitId,
      clinic_patient_id: p.clinicPatientId || null,
      kind: p.kind,
      amount: p.amount,
    });
  }
  let body: { visitId?: string; clinicPatientId?: string; kind?: string; amount?: number };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const g = await guard(body.kind);
  if ("res" in g) return g.res;
  const { db, kind } = g;

  const visitId = (body.visitId ?? "").trim();
  if (!visitId) return NextResponse.json({ error: "Thiếu visitId." }, { status: 400 });

  // Chốt an toàn tiền: CHỈ được thu khi BÁC SĨ ĐÃ KHÁM XONG lượt này
  // (appointment.status = COMPLETED). Chặn tại server để dù board có lỡ hiện
  // (cache/đua) hay gọi API trực tiếp cũng không thu được lúc bác sĩ chưa xong.
  // Không tìm thấy visit/appointment → chặn (không thu "mù"). DELETE (hoàn tác)
  // KHÔNG gán điều kiện này.
  {
    const { data: vrow } = await db
      .from("visit")
      .select("appointment:appointment!appointment_id ( status )")
      .eq("visit_id", visitId)
      .maybeSingle();
    const apptRaw = (vrow as { appointment?: unknown } | null)?.appointment;
    const appt = (Array.isArray(apptRaw) ? apptRaw[0] : apptRaw) as
      | { status?: string | null }
      | null
      | undefined;
    if (appt?.status !== "COMPLETED") {
      return NextResponse.json(
        { error: "Bác sĩ chưa khám xong lượt này — chưa thể thu tiền." },
        { status: 409 },
      );
    }
  }

  const staffId = await getClinicStaffId();
  const amount =
    typeof body.amount === "number" && Number.isFinite(body.amount) && body.amount >= 0
      ? Math.round(body.amount)
      : null;

  const { error } = await db.from("payment").upsert(
    {
      visit_id: visitId,
      clinic_patient_id: (body.clinicPatientId ?? "").trim() || null,
      kind,
      status: "PAID",
      amount,
      paid_by_staff_id: staffId,
      paid_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    { onConflict: "visit_id,kind" },
  );
  if (error) {
    // Bảng chưa tồn tại (migration 056 chưa apply) → báo rõ thay vì lỗi mơ hồ.
    const undefinedTable = error.code === "42P01";
    return NextResponse.json(
      {
        error: undefinedTable
          ? "Bảng payment chưa được tạo (chạy migration 056)."
          : error.message,
      },
      { status: undefinedTable ? 503 : 500 },
    );
  }
  return NextResponse.json({ ok: true });
}

export async function DELETE(request: Request) {
  if (paymentViaBackend()) {
    let raw: unknown;
    try {
      raw = await request.json();
    } catch {
      return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
    }
    const p = (raw ?? {}) as { visitId?: string; kind?: string };
    return proxyJsonToBackend("DELETE", "/api/v1/payments", {
      visit_id: p.visitId,
      kind: p.kind,
    });
  }
  let body: { visitId?: string; kind?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const g = await guard(body.kind);
  if ("res" in g) return g.res;
  const { db, kind } = g;

  const visitId = (body.visitId ?? "").trim();
  if (!visitId) return NextResponse.json({ error: "Thiếu visitId." }, { status: 400 });

  const { error } = await db.from("payment").delete().eq("visit_id", visitId).eq("kind", kind);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ ok: true });
}
