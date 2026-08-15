// Bảng "Trạng thái BN buổi khám" — READ-ONLY cho Lễ tân (front desk).
// List BN có buổi khám (visit) TẠO HÔM NAY, cột trạng thái theo visit.status
// (OPEN / IN_PROGRESS / INCOMPLETE / FINALIZED / AMENDED).
// CHỈ hiển thị, không nút ghi. Data server-fetch ở home/page.tsx, đọc thẳng Supabase
// (RLS SELECT visit_select_authenticated). Badge riêng cho visit — KHÔNG dùng StatusBadge
// (badge đó dành cho appointment.status, màu khác).

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
  // Khách về giữa chừng. Phải đứng TRƯỚC mọi nhánh khác trừ "đã thanh toán":
  // không có nhánh này thì nó rơi xuống `return` cuối và hiện "Chờ khám" cho
  // một người đã ra về — Lễ tân sẽ đi gọi tên họ.
  if (visitStatus === "INCOMPLETE")
    return { label: "Khám dở — chờ gọi lại", style: "bg-danger-bg text-danger" };
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
  // Danh sách TRẮNG: chỉ hai trạng thái này là còn đang chờ. Viết theo kiểu
  // danh sách đen ("khác FINALIZED thì còn chờ") thì trạng thái mới nào cũng
  // lọt vào, và đồng hồ chờ của người đã về nhà sẽ đếm tới vô hạn.
  return visitStatus === "OPEN" || visitStatus === "IN_PROGRESS";
}

function VisitBadge({ label, style }: { label: string; style: string }) {
  // Cùng hình dạng với Chip (chữ nhật mềm, không viền) nhưng giữ style map
  // riêng: "Chờ khám" dùng cặp màu status-in-progress không có trong ChipTone.
  return (
    <span
      className={`inline-flex items-center rounded-chip px-2 py-0.5 text-label font-medium ${style}`}
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
  /** Lúc bác sĩ KÝ bệnh án — mốc kết thúc khám. Đọc `finalized_at` chứ không
   *  phải `exam_completed_at`: baseline khai cả hai cột cho cùng một việc,
   *  nhưng chỉ cột này được ghi (clinical_sign_service), và cột kia thậm chí
   *  không tồn tại trên prod. */
  finalized_at?: string | null;
  /** Lúc bệnh án đầu tiên của lượt được mở — mốc "Đang khám". Server gắn vào
   *  từ /api/v1/visits/progress. Trống khi chưa ai mở bệnh án. */
  exam_started_at?: string | null;
  /** Lúc thu xong khâu cuối — mốc "Đã thanh toán". Cùng nguồn với trên. */
  paid_at?: string | null;
}

/** Thời lượng khám (phút) = khám xong − bắt đầu khám. null nếu thiếu mốc. */
function examMinutes(
  checkedInAt: string | null,
  finalizedAt: string | null | undefined,
): number | null {
  if (!checkedInAt || !finalizedAt) return null;
  const ms = Date.parse(finalizedAt) - Date.parse(checkedInAt);
  if (!Number.isFinite(ms) || ms < 0) return null;
  return Math.round(ms / 60000);
}

// KHÔNG kẻ đường ngăn giữa các dòng (Quang chốt 06/08 — "bỏ các đường kẻ bảng
// đi, để trắng cho nhìn thoáng"). Dòng nào ra dòng nào vẫn phân biệt được nhờ
// khoảng thở dọc và nền sáng lên khi rê chuột.
const TH = "px-4 pb-2 pt-3 text-left font-semibold text-ink-soft";
const TD = "px-4 py-4 align-middle text-ink";

export default function VisitStatusBoard({ rows }: { rows: VisitStatusRow[] }) {
  return (
    <div className="overflow-auto rounded-card border border-line bg-surface shadow-card">
      <table className="w-full min-w-max border-collapse text-sm">
        <thead>
          <tr>
            {/* Ô đầu: thông tin BN gộp. Còn lại: thanh tiến trình 4 mốc. */}
            <th className={`${TH} min-w-60`}>Bệnh nhân</th>
            <th className={`${TH} min-w-85`}>Tiến trình buổi khám</th>
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
              const examMin = examMinutes(r.checked_in_at, r.finalized_at);
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
                        {examMin !== null && (
                          <span
                            className="rounded-chip bg-status-in-progress-bg px-2 py-0.5 text-label font-medium text-status-in-progress tabular-nums"
                            title="Thời gian khám (khám xong − bắt đầu khám)"
                          >
                            khám {examMin} phút
                          </span>
                        )}
                      </div>
                    </div>
                  </td>
                  {/* Ô 2 — thanh tiến trình (Check-in → Đang khám → Khám xong
                      → Đã thanh toán), có giờ dưới mỗi mốc. */}
                  <td className={TD}>
                    <ProgressStepper
                      visitStatus={r.status}
                      apptStatus={apptStatus}
                      paid={paid}
                      times={{
                        checkedInAt: r.checked_in_at,
                        examStartedAt: r.exam_started_at ?? null,
                        examFinishedAt: r.finalized_at ?? null,
                        paidAt: r.paid_at ?? null,
                      }}
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
