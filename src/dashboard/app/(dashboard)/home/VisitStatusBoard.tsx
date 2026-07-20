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
    return { label: "Đã thanh toán", style: "bg-[#dcfce7] text-[#15803d]" };
  if (visitStatus === "AMENDED")
    return { label: "Đã bổ sung", style: "bg-[#f3e8ff] text-[#7e22ce]" };
  if (visitStatus === "FINALIZED")
    return { label: "Đã chốt hồ sơ", style: "bg-[#dcfce7] text-[#15803d]" };
  if (apptStatus === "COMPLETED")
    return { label: "Đã khám xong — chờ thu", style: "bg-[#fef9c3] text-[#a16207]" };
  if (visitStatus === "IN_PROGRESS")
    return { label: "Đang khám", style: "bg-[#fef9c3] text-[#a16207]" };
  return { label: "Chờ khám", style: "bg-[#dbeafe] text-[#1d4ed8]" };
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
  "border-b border-[#ececec] px-4 py-2.5 text-left font-semibold text-[#525252]";
const TD = "border-b border-[#f3f3f3] px-4 py-3 align-middle text-[#171717]";

export default function VisitStatusBoard({ rows }: { rows: VisitStatusRow[] }) {
  return (
    <div className="overflow-auto rounded-xl border border-[#ececec] bg-white shadow-[0_1px_3px_rgba(0,0,0,0.04)]">
      <table className="w-full min-w-max border-collapse text-sm">
        <thead className="bg-[#fafafa]">
          <tr>
            {/* Ô đầu: thông tin BN gộp. Còn lại: thanh tiến trình 3 mốc. */}
            <th className={`${TH} min-w-[240px]`}>Bệnh nhân</th>
            <th className={`${TH} min-w-[340px]`}>Tiến trình buổi khám</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="px-4 py-6 text-center text-[#888888]" colSpan={2}>
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
                <tr key={r.visit_id} className="hover:bg-[#fafafa]">
                  {/* Ô 1 — thông tin gộp: tên BN + mã · bác sĩ · dịch vụ · trạng thái
                      (live badge) + đồng hồ chờ (đếm liên tục từ check-in). */}
                  <td className={TD}>
                    <div className="space-y-1">
                      <div className="flex items-baseline gap-1.5">
                        <span className="font-semibold text-[#171717]">
                          {r.patient?.full_name ?? "—"}
                        </span>
                        {r.patient?.patient_code && (
                          <span className="font-mono text-xs text-[#888888]">
                            {r.patient.patient_code}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-[#71717a]">
                        <span className="text-[#a1a1aa]">BS:</span>{" "}
                        {r.doctor?.full_name ?? "—"}
                        <span className="mx-1 text-[#d4d4d8]">·</span>
                        {r.service?.name ?? "—"}
                      </div>
                      <div className="flex flex-wrap items-center gap-2 pt-0.5">
                        <VisitBadge label={disp.label} style={disp.style} />
                        <WaitClock
                          checkedInAt={r.checked_in_at}
                          active={stillWaiting(r.status, apptStatus)}
                        />
                        <span className="text-[10px] text-[#bcbcbc] tabular-nums">
                          vào {fmtTime(r.checked_in_at ?? r.created_at)}
                        </span>
                        {examMin !== null && (
                          <span
                            className="rounded-full bg-[#eef2ff] px-2 py-0.5 text-[10px] font-medium text-[#4338ca] tabular-nums"
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
