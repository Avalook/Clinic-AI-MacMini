// Status pill for appointment.status. Colors are design tokens — do not drift.

const STATUS_STYLE: Record<string, string> = {
  SCHEDULED: "bg-[#dbeafe] text-[#1d4ed8]",
  CSKH_CONFIRMED: "bg-[#ccfbf1] text-[#0f766e]",
  CONFIRMED: "bg-success-bg text-success",
  CHECKED_IN: "bg-warning-bg text-warning",
  COMPLETED: "bg-surface-sunken text-ink-muted",
  CANCELLED: "bg-danger-bg text-danger",
  NO_SHOW: "bg-brand-100 text-status-cancelled",
  DOCTOR_DECLINED: "bg-[#ffedd5] text-[#c2410c]",
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
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style}`}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
