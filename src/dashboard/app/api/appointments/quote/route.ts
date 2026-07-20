// GET /api/appointments/quote?date=YYYY-MM-DD&location_id=...&doctor_id=...
// Capacity Phase 1 (T-20260629-CAP-01) — trả ngân sách + tải hiện có theo từng khung-giờ VN
// để CinemaSlotPicker tô màu ô lịch. KHÔNG đặt lịch, chỉ đọc (read-only quote).
import { NextResponse } from "next/server";
import { getSupabaseServer } from "../../../../lib/supabase-server";
import { getSupabaseService } from "../../../../lib/supabase-service";
import {
  vnBlockOf,
  resolveBudget,
  usageOf,
  cellState,
  type BudgetRow,
  type ApptLite,
} from "../../../../lib/capacity";

const BUDGET_COLS =
  "location_id, doctor_id, weekday, hour_start, thanh_budget_min, sono_budget_min, online_quota_min, walkin_quota_min, buffer_min, new_cap, max_total";

export async function GET(request: Request) {
  const caller = await getSupabaseServer();
  const {
    data: { user },
  } = await caller.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorised" }, { status: 401 });

  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date"); // YYYY-MM-DD (VN)
  const location_id = searchParams.get("location_id");
  const doctor_id = searchParams.get("doctor_id"); // optional

  if (!date || !location_id) {
    return NextResponse.json(
      { error: "Thiếu date / location_id." },
      { status: 400 },
    );
  }

  const db = getSupabaseService();
  if (!db) {
    return NextResponse.json(
      { error: "SUPABASE_SERVICE_ROLE_KEY chưa cấu hình trên server." },
      { status: 503 },
    );
  }

  const startOfDay = new Date(`${date}T00:00:00+07:00`).toISOString();
  const endOfDay = new Date(`${date}T23:59:59+07:00`).toISOString();

  // weekday VN của ngày (lấy từ giữa trưa để tránh lệch biên).
  const { weekday } = vnBlockOf(new Date(`${date}T12:00:00+07:00`).toISOString());

  const [{ data: budgetRows }, apptRes] = await Promise.all([
    db.from("block_budget").select(BUDGET_COLS).eq("location_id", location_id),
    (() => {
      let q = db
        .from("appointment")
        .select("slot_start, patient_kind, thanh_min, booking_channel")
        .eq("location_id", location_id)
        .gte("slot_start", startOfDay)
        .lte("slot_start", endOfDay)
        .not("status", "eq", "CANCELLED")
        .not("status", "eq", "NO_SHOW");
      if (doctor_id) q = q.eq("doctor_id", doctor_id);
      return q;
    })(),
  ]);

  const rows = (budgetRows as BudgetRow[] | null) ?? [];
  const appts = (apptRes.data as (ApptLite & { slot_start: string })[] | null) ?? [];

  // Nhóm appt theo khung-giờ VN.
  const byHour = new Map<number, ApptLite[]>();
  for (const a of appts) {
    const { hour_start } = vnBlockOf(a.slot_start);
    const arr = byHour.get(hour_start) ?? [];
    arr.push(a);
    byHour.set(hour_start, arr);
  }

  // Trả mọi hour_start có cấu hình ngân sách ở cơ sở này.
  const hours = Array.from(new Set(rows.map((r) => r.hour_start))).sort(
    (x, y) => x - y,
  );
  const blocks = hours.map((hour_start) => {
    const budget = resolveBudget(rows, {
      location_id,
      doctor_id,
      weekday,
      hour_start,
    });
    const existing = byHour.get(hour_start) ?? [];
    const usage = usageOf(existing);
    return {
      hour_start,
      budget, // null ⇒ fail-open (UI coi như free)
      usage,
      state: budget ? cellState(budget, usage) : "free",
    };
  });

  return NextResponse.json({ date, location_id, doctor_id, weekday, blocks });
}
