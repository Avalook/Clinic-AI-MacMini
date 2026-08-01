// Bảng "Trạng thái BN buổi khám" — READ-ONLY cho Lễ tân (front desk).
// List BN có buổi khám (visit) TẠO HÔM NAY, cột trạng thái theo enum visit.status
// (OPEN / IN_PROGRESS / FINALIZED / AMENDED — nguồn: migration 017_create_clinical_domain).
// CHỈ hiển thị, không nút ghi. Data server-fetch ở home/page.tsx, đọc thẳng Supabase
// (RLS SELECT visit_select_authenticated). Badge riêng cho visit — KHÔNG dùng StatusBadge
// (badge đó dành cho appointment.status, màu khác).

import { fmtTime } from "../../../lib/datetime";
import { ProgressStepper, WaitClock } from "./VisitProgress";

// Trạng thái HIỂN THỊ suy từ visit.status + appointment.status. "Khám xong" đọc từ
// appointment.COMPLETED (dashboard KHÔNG tự set visit.FINALIZED) — nếu chỉ nhìn
// visit.status thì BN đã khám xong vẫn kẹt ở "Đang khám".
function displayStatus(
  visitStatus: string,
  apptStatus: string | null,
  paid: boolean,
): { label: string; style: string } {
  if (paid)
    return { label: "Đã thanh toán", style: "bg-success-bg text-success" };
  if (visitStatus === "AMENDED")
    return { label: "Đã bổ sung", style: "bg-brand-50 text-brand-800" };
  if (visitStatus === "FINALIZED")
    return { label: "Đã chốt hồ sơ", style: "bg-success-bg text-success" };
  if (apptStatus === "COMPLETED")
    return { label: "Đã khám xong — chờ thu", style: "bg-warning-bg text-warning" };
  if (visitStatus === "IN_PROGRESS")
    return { label: "Đang khám", style: "bg-warning-bg text-warning" };
  return {
    label: "Chờ khám",
    style: "bg-status-in-progress-bg text-status-in-progress",
  };
}

// Đồng hồ chờ chạy tới khi KHÁM XONG (appt COMPLETED) / hồ sơ chốt. Sau đó dừng.
function stillWaiting(visitStatus: string, apptStatus: string | null): boolean {
  if (apptStatus === "COMPLETED") return false;
  if (visitStatus === "FINALIZED" || visitStatus === "AMENDED") return false;
  return visitStatus === "OPEN" || visitStatus === "IN_PROGRESS";
}

function VisitBadge({ label, style }: { label: string; style: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style}`}
    >
      {label}
    </span>
  );
}

export interface VisitStatusRow {
  visit_id: string;
  status: string;
  checked_in_at: string | null;
  created_at: string;
  patient: { full_name: string | null; patient_code: string | null } | null;
  doctor: { full_name: string | null } | null;
  service: { name: string | null } | null;
  /** appointment.status (join) — nguồn THẬT cho mốc "Khám xong" (COMPLETED). */
  appointment: { status: string | null } | null;
  /** Đã thu đủ mọi khâu (bảng payment) → mốc "Đã thanh toán" xanh. Server tính. */
  paid?: boolean;
  /** Mốc khám xong (mig 058) — dùng tính & hiện "khám N phút" cho board Lễ tân. */
  exam_completed_at?: string | null;
}

/** Thời lượng khám (phút) = khám xong − bắt đầu khám. null nếu thiếu mốc. */
function examMinutes(
  checkedInAt: string | null,
  examCompletedAt: string | null | undefined,
): number | null {
  if (!checkedInAt || !examCompletedAt) return null;
  const ms = Date.parse(examCompletedAt) - Date.parse(checkedInAt);
  if (!Number.isFinite(ms) || ms < 0) return null;
  return Math.round(ms / 60000);
}

const TH =
  "border-b border-line px-4 py-2.5 text-left font-semibold text-ink-soft";
const TD = "border-b border-line px-4 py-3 align-middle text-ink";

export default function VisitStatusBoard({ rows }: { rows: VisitStatusRow[] }) {
  return (
    <div className="overflow-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full min-w-max border-collapse text-sm">
        <thead className="bg-surface-muted">
          <tr>
            {/* Ô đầu: thông tin BN gộp. Còn lại: thanh tiến trình 3 mốc. */}
            <th className={`${TH} min-w-[240px]`}>Bệnh nhân</th>
            <th className={`${TH} min-w-[340px]`}>Tiến trình buổi khám</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="px-4 py-6 text-center text-ink-muted" colSpan={2}>
                Chưa có buổi khám nào hôm nay.
              </td>
            </tr>
          ) : (
            rows.map((r) => {
              const apptStatus = r.appointment?.status ?? null;
              const paid = r.paid ?? false;
              const disp = displayStatus(r.status, apptStatus, paid);
              const examMin = examMinutes(r.checked_in_at, r.exam_completed_at);
              return (
                <tr key={r.visit_id} className="hover:bg-surface-muted">
                  {/* Ô 1 — thông tin gộp: tên BN + mã · bác sĩ · dịch vụ · trạng thái
                      (live badge) + đồng hồ chờ (đếm liên tục từ check-in). */}
                  <td className={TD}>
                    <div className="space-y-1">
                      <div className="flex items-baseline gap-1.5">
                        <span className="font-semibold text-ink">
                          {r.patient?.full_name ?? "—"}
                        </span>
                        {r.patient?.patient_code && (
                          <span className="font-mono text-xs text-ink-muted">
                            {r.patient.patient_code}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-ink-muted">
                        <span className="text-ink-faint">BS:</span>{" "}
                        {r.doctor?.full_name ?? "—"}
                        <span className="mx-1 text-line-strong">·</span>
                        {r.service?.name ?? "—"}
                      </div>
                      <div className="flex flex-wrap items-center gap-2 pt-0.5">
                        <VisitBadge label={disp.label} style={disp.style} />
                        <WaitClock
                          checkedInAt={r.checked_in_at}
                          active={stillWaiting(r.status, apptStatus)}
                        />
                        <span className="text-[10px] text-ink-faint tabular-nums">
                          vào {fmtTime(r.checked_in_at ?? r.created_at)}
                        </span>
                        {examMin !== null && (
                          <span
                            className="rounded-chip bg-status-in-progress-bg px-2 py-0.5 text-[10px] font-medium text-status-in-progress tabular-nums"
                            title="Thời gian khám (khám xong − bắt đầu khám)"
                          >
                            khám {examMin} phút
                          </span>
                        )}
                      </div>
                    </div>
                  </td>
                  {/* Ô 2 — thanh tiến trình kiểu Grab (Đang khám → Khám xong → Đã thanh toán). */}
                  <td className={TD}>
                    <ProgressStepper
                      visitStatus={r.status}
                      apptStatus={apptStatus}
                      paid={paid}
                    />
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
