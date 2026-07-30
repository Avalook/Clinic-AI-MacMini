// "Cần làm hôm nay" (CSKH/Quản lý) — danh sách việc TỰ SINH từ dữ liệu, 4 khối:
//   ① Gọi xác nhận lịch NGÀY MAI (status SCHEDULED)
//   ② Lịch bị bác sĩ từ chối — cần phân lại (DOCTOR_DECLINED, từ hôm nay)
//   ③ BN đến hạn TÁI KHÁM (clinical_record.soap_plan.tai_kham — hợp đồng JSONB)
//   ④ Kết quả XN mới về hôm nay. Chỉ GROUP_A đã finalized mới được báo BN;
//      mọi trạng thái khác đều fail closed.
// Trang CHỈ ĐỌC: thao tác xác nhận / phân lại làm ở /tasks (ConfirmBoard) —
// không lặp lại logic ghi ở đây. CCCD KHÔNG select (D-identity).

import Link from "next/link";
import { getSupabaseServer } from "../../../lib/supabase-server";
import { requireNavAccess } from "../../../lib/clinic-session";
import {
  vnTodayRangeUtc,
  fmtDate,
  fmtTimeOrNone,
  nowMs,
  VN_TZ,
} from "../../../lib/datetime";
import { doctorName } from "../../../lib/doctor-name";
import { labReleaseDecision } from "../../../lib/lab-release";
import { fetchFromBackend } from "../../../lib/backend-proxy";
import CskhFollowupList, {
  type FollowupBucket,
} from "./CskhFollowupList";

export const dynamic = "force-dynamic";

const DAY_MS = 24 * 60 * 60 * 1000;

// Ngưỡng (SỐ NGÀY QUÁ HẠN) chia bucket nhắc gọi — khai 1 chỗ DUY NHẤT.
// Anchor số ngày = tai_kham.ngay (cùng anchor dueLimit khối ③) → quá hạn = today − ngay.
const FOLLOWUP_TIERS = [2, 10, 20, 30] as const;

/** Chia recalls QUÁ HẠN vào bucket theo số ngày quá hạn (>= ngưỡng cao nhất khớp). */
function buildFollowupBuckets(
  recalls: RecallRow[],
  todayYmd: string,
): FollowupBucket[] {
  const tiersDesc = [...FOLLOWUP_TIERS].sort((a, b) => b - a); // 30,20,10,2
  const buckets: FollowupBucket[] = tiersDesc.map((t) => ({
    tier: t,
    label: `Quá hạn ≥ ${t} ngày`,
    rows: [],
  }));
  for (const r of recalls) {
    const overdue = Math.floor(
      (Date.parse(todayYmd) - Date.parse(r.tai_kham.ngay)) / DAY_MS,
    );
    if (overdue < FOLLOWUP_TIERS[0]) continue; // chưa đủ ngưỡng nhắc gọi
    const b = buckets.find((bk) => overdue >= bk.tier);
    if (b) {
      b.rows.push({
        clinic_patient_id: r.clinic_patient_id,
        full_name: r.full_name,
        phone_primary: r.phone_primary,
        ngay: r.tai_kham.ngay,
        overdue_days: overdue,
      });
    }
  }
  return buckets;
}

// ---------- kiểu dữ liệu ----------

interface PatientLite {
  clinic_patient_id: string;
  full_name: string;
  phone_primary: string | null;
}

interface ApptRow {
  id: string;
  slot_start: string;
  patient: PatientLite | null;
  doctor: { full_name: string } | null;
  service: { name: string } | null;
}

interface LabRow {
  lab_result_id: string;
  test_name: string | null;
  triage_group: string | null;
  is_finalized: boolean;
  result_received_at: string | null;
  patient: PatientLite | null;
}

/** Hợp đồng JSONB với form bác sĩ: soap_plan.tai_kham = { ngay, xn[], ghi_chu }. */
interface TaiKham {
  ngay: string;
  xn: string[];
  ghi_chu: string;
}

interface RecallRow {
  clinic_patient_id: string;
  full_name: string;
  phone_primary: string | null;
  tai_kham: TaiKham;
}

interface RecallProjection {
  clinic_patient_id: string;
  full_name: string;
  phone_primary: string | null;
  due_date: string;
  repeat_tests: string[];
  instruction: string;
}

// Nhãn nhóm XN bác sĩ dặn làm lại khi tái khám.
const XN_LABEL: Record<string, string> = {
  HM: "Hormone",
  SH: "Sinh hóa",
  SA: "Siêu âm",
  DXA: "DXA",
  PS: "Pap smear",
};

/** "YYYY-MM-DD" theo giờ VN của (hôm nay + offsetDays). */
function vnYmd(offsetDays = 0): string {
  return new Date(nowMs() + offsetDays * DAY_MS).toLocaleDateString("en-CA", {
    timeZone: VN_TZ,
  });
}

// ---------- UI con ----------

function SectionHeader({
  title,
  count,
  sub,
}: {
  title: string;
  count: number;
  sub?: string;
}) {
  return (
    <div className="mb-2">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-[#171717]">
        {title}
        <span className="inline-flex min-w-[1.5rem] items-center justify-center rounded-full bg-[#f4f4f5] px-1.5 py-0.5 text-xs font-semibold text-[#171717]">
          {count}
        </span>
      </h2>
      {sub && <p className="text-xs text-[#888888]">{sub}</p>}
    </div>
  );
}

function EmptyRow({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-[#e4e4e7] bg-white px-4 py-6 text-center text-sm text-[#888888]">
      {text}
    </div>
  );
}

function TasksLink() {
  return (
    <Link
      href="/tasks"
      className="shrink-0 rounded-md border border-[#e4e4e7] px-2 py-1 text-xs font-medium text-[#171717] hover:bg-[#f4f4f5]"
    >
      Mở board →
    </Link>
  );
}

// ---------- trang ----------

export default async function CskhTodayPage() {
  await requireNavAccess("/cskh-today");
  const supabase = await getSupabaseServer();

  const { startUtc: todayStart, endUtc: todayEnd } = vnTodayRangeUtc();
  // Ngày mai (giờ VN) = [hết hôm nay, +24h).
  const tomorrowStart = todayEnd;
  const tomorrowEnd = new Date(
    new Date(todayEnd).getTime() + DAY_MS,
  ).toISOString();
  const APPT_SELECT = `
    id, slot_start,
    patient:patient!clinic_patient_id ( clinic_patient_id, full_name, phone_primary ),
    doctor:staff!doctor_id ( full_name ),
    service:service_type!service_type_id ( name )
  `;

  const [tomorrowRes, declinedRes, recallProjection, labRes] =
    await Promise.all([
    // ① Lịch NGÀY MAI chưa gọi xác nhận.
    supabase
      .from("appointment")
      .select(APPT_SELECT)
      .eq("status", "SCHEDULED")
      .gte("slot_start", tomorrowStart)
      .lt("slot_start", tomorrowEnd)
      .order("slot_start", { ascending: true })
      .limit(200),
    // ② Bác sĩ từ chối — từ hôm nay trở đi, cần phân lại.
    supabase
      .from("appointment")
      .select(APPT_SELECT)
      .eq("status", "DOCTOR_DECLINED")
      .gte("slot_start", todayStart)
      .order("slot_start", { ascending: true })
      .limit(200),
    // ③ FastAPI reads the note and returns only the recall instruction CSKH
    // needs; the SOAP document never crosses this boundary.
    fetchFromBackend<RecallProjection[]>("/api/v1/cskh/recalls"),
    // ④ Kết quả XN nhận HÔM NAY.
    supabase
      .from("lab_result")
      .select(
        `lab_result_id, test_name, triage_group, is_finalized, result_received_at,
         patient:patient!clinic_patient_id ( clinic_patient_id, full_name, phone_primary )`,
      )
      .gte("result_received_at", todayStart)
      .lt("result_received_at", todayEnd)
      .order("result_received_at", { ascending: false })
      .limit(200),
    ]);

  const error = tomorrowRes.error ?? declinedRes.error ?? labRes.error;

  const tomorrowAppts = (tomorrowRes.data as ApptRow[] | null) ?? [];
  const declinedAppts = (declinedRes.data as ApptRow[] | null) ?? [];
  const labResults = (labRes.data as LabRow[] | null) ?? [];

  const recalls: RecallRow[] = (recallProjection ?? []).map((row) => ({
    clinic_patient_id: row.clinic_patient_id,
    full_name: row.full_name,
    phone_primary: row.phone_primary,
    tai_kham: {
      ngay: row.due_date,
      xn: row.repeat_tests,
      ghi_chu: row.instruction,
    },
  }));

  // BN QUÁ HẠN tái khám (chưa đặt lịch mới) → chia bucket 2/10/20/30 ngày để nhắc gọi.
  const followupBuckets = buildFollowupBuckets(recalls, vnYmd(0));
  const followupTotal = followupBuckets.reduce((n, b) => n + b.rows.length, 0);

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-xl font-semibold text-[#171717]">Cần làm hôm nay</h1>
        <p className="text-sm text-[#888888]">
          Việc CSKH tự sinh từ dữ liệu · {fmtDate(new Date())} · thao tác xác
          nhận / phân lại lịch làm ở &quot;Công việc của tôi&quot;.
        </p>
      </header>

      {error && (
        <div className="rounded-md bg-[#fee2e2] px-3 py-2 text-sm text-[#dc2626]">
          {error.message}
        </div>
      )}
      {recallProjection === null && (
        <div className="rounded-md bg-[#fff7ed] px-3 py-2 text-sm text-[#9a3412]">
          Không tải được danh sách tái khám từ máy chủ. Các phần khác vẫn hoạt
          động; vui lòng báo quản trị viên nếu cảnh báo này còn xuất hiện.
        </div>
      )}

      {/* ① Gọi xác nhận lịch NGÀY MAI */}
      <section>
        <SectionHeader
          title={`Gọi xác nhận lịch NGÀY MAI (${fmtDate(tomorrowStart)})`}
          count={tomorrowAppts.length}
          sub="Lịch còn ở trạng thái Chờ xác nhận — gọi khách chốt trước giờ hẹn."
        />
        {tomorrowAppts.length === 0 ? (
          <EmptyRow text="Không có lịch ngày mai cần gọi xác nhận." />
        ) : (
          <ul className="divide-y divide-[#e4e4e7] rounded-lg border border-[#e4e4e7] bg-white">
            {tomorrowAppts.map((a) => (
              <li key={a.id} className="flex items-center gap-3 px-4 py-2.5">
                <span className="w-20 shrink-0 text-sm font-semibold text-[#171717]">
                  {fmtTimeOrNone(a.slot_start)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[#171717]">
                    {a.patient?.full_name ?? "(không rõ tên)"}
                    <span className="ml-2 font-normal text-[#888888]">
                      {a.patient?.phone_primary ?? "— chưa có SĐT"}
                    </span>
                  </p>
                  <p className="truncate text-xs text-[#888888]">
                    {a.service?.name ?? "Chưa chọn dịch vụ"}
                    {a.doctor?.full_name ? ` · ${doctorName(a.doctor.full_name)}` : ""}
                  </p>
                </div>
                <TasksLink />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ② Lịch bị bác sĩ từ chối */}
      <section>
        <SectionHeader
          title="Lịch bị bác sĩ từ chối — cần phân lại"
          count={declinedAppts.length}
          sub="Từ hôm nay trở đi · phân lại bác sĩ ở board (cột Đã huỷ / Từ chối)."
        />
        {declinedAppts.length === 0 ? (
          <EmptyRow text="Không có lịch nào bị bác sĩ từ chối." />
        ) : (
          <ul className="divide-y divide-[#e4e4e7] rounded-lg border border-[#e4e4e7] bg-white">
            {declinedAppts.map((a) => (
              <li key={a.id} className="flex items-center gap-3 px-4 py-2.5">
                <span className="w-28 shrink-0 text-sm font-semibold text-[#171717]">
                  {fmtDate(a.slot_start)} {fmtTimeOrNone(a.slot_start)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[#171717]">
                    {a.patient?.full_name ?? "(không rõ tên)"}
                    <span className="ml-2 font-normal text-[#888888]">
                      {a.patient?.phone_primary ?? "— chưa có SĐT"}
                    </span>
                  </p>
                  <p className="truncate text-xs text-[#dc2626]">
                    BS đã từ chối: {a.doctor?.full_name ?? "(không rõ)"}
                  </p>
                </div>
                <TasksLink />
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ③ BN đến hạn TÁI KHÁM */}
      <section>
        <SectionHeader
          title="Bệnh nhân đến hạn TÁI KHÁM"
          count={recalls.length}
          sub="Bác sĩ dặn tái khám trong 7 ngày tới (hoặc đã quá hạn) mà BN chưa có lịch hẹn mới."
        />
        {recalls.length === 0 ? (
          <EmptyRow text="Chưa có BN đến hạn tái khám trong 7 ngày tới." />
        ) : (
          <ul className="divide-y divide-[#e4e4e7] rounded-lg border border-[#e4e4e7] bg-white">
            {recalls.map((r) => (
              <li
                key={r.clinic_patient_id}
                className="flex items-center gap-3 px-4 py-2.5"
              >
                <span className="w-24 shrink-0 text-sm font-semibold text-[#171717]">
                  {fmtDate(r.tai_kham.ngay)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[#171717]">
                    {r.full_name}
                    <span className="ml-2 font-normal text-[#888888]">
                      {r.phone_primary ?? "— chưa có SĐT"}
                    </span>
                  </p>
                  <p className="truncate text-xs text-[#888888]">
                    {r.tai_kham.xn.length > 0 && (
                      <>
                        XN cần làm lại:{" "}
                        {r.tai_kham.xn
                          .map((x) => XN_LABEL[x] ?? x)
                          .join(", ")}
                      </>
                    )}
                    {r.tai_kham.xn.length > 0 && r.tai_kham.ghi_chu && " · "}
                    {r.tai_kham.ghi_chu}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ③b BN quá hạn tái khám — nhắc gọi (bucket 2/10/20/30 ngày) */}
      <section>
        <SectionHeader
          title="Bệnh nhân quá hạn — cần nhắc gọi"
          count={followupTotal}
          sub="Quá hạn ngày tái khám bác sĩ dặn mà chưa đặt lịch mới. Bấm “Đã gọi” để ghi nhật ký CSKH."
        />
        <CskhFollowupList buckets={followupBuckets} />
      </section>

      {/* ④ Kết quả XN mới về hôm nay */}
      <section>
        <SectionHeader
          title="Kết quả XN mới về hôm nay"
          count={labResults.length}
          sub="Chỉ GROUP_A đã hoàn tất mới được báo BN; mọi trạng thái khác đều bị chặn."
        />
        {labResults.length === 0 ? (
          <EmptyRow text="Chưa có kết quả XN mới hôm nay." />
        ) : (
          <ul className="divide-y divide-[#e4e4e7] rounded-lg border border-[#e4e4e7] bg-white">
            {labResults.map((l) => {
              const release = labReleaseDecision(
                l.triage_group,
                l.is_finalized,
              );
              return (
                <li
                  key={l.lab_result_id}
                  className="flex items-center gap-3 px-4 py-2.5"
                >
                <span className="w-14 shrink-0 text-sm font-semibold text-[#171717]">
                  {fmtTimeOrNone(l.result_received_at)}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-[#171717]">
                    {l.patient?.full_name ?? "(không rõ tên)"}
                    <span className="ml-2 font-normal text-[#888888]">
                      {l.patient?.phone_primary ?? "— chưa có SĐT"}
                    </span>
                  </p>
                  <p className="truncate text-xs text-[#888888]">
                    {l.test_name ?? "Xét nghiệm"}
                  </p>
                </div>
                  <span className={release.className}>{release.label}</span>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
