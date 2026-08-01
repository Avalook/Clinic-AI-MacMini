// Status pill for appointment.status. Colors are design tokens — do not drift.

const STATUS_STYLE: Record<string, string> = {
  SCHEDULED: "bg-status-ready-bg text-status-ready",
  CSKH_CONFIRMED: "bg-status-assigned-bg text-status-assigned",
  CONFIRMED: "bg-status-completed-bg text-status-completed",
  CHECKED_IN: "bg-warning-bg text-warning",
  COMPLETED: "bg-status-completed-bg text-status-completed",
  CANCELLED: "bg-danger-bg text-danger",
  NO_SHOW: "bg-status-cancelled-bg text-status-cancelled",
  DOCTOR_DECLINED: "bg-warning-bg text-warning",
};

// Nhãn tiếng Việt cho mọi trạng thái (chuyên nghiệp hơn mã code trần).
const STATUS_LABEL: Record<string, string> = {
  SCHEDULED: "Chờ xác nhận",
  CSKH_CONFIRMED: "Chờ bác sĩ",
  CONFIRMED: "Đã xác nhận",
  CHECKED_IN: "Đã đến",
  COMPLETED: "Đã khám xong",
  CANCELLED: "Đã hủy",
  NO_SHOW: "Không đến",
  DOCTOR_DECLINED: "Đã từ chối",
};

export default function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLE[status] ?? "bg-surface-sunken text-ink-muted";
  return (
    <span
      className={`inline-flex items-center rounded-chip px-2 py-0.5 text-xs font-medium ${style}`}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
