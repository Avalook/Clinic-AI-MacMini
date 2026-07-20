// Status pill for appointment.status. Colors are design tokens — do not drift.

const STATUS_STYLE: Record<string, string> = {
  SCHEDULED: "bg-[#dbeafe] text-[#1d4ed8]",
  CSKH_CONFIRMED: "bg-[#ccfbf1] text-[#0f766e]",
  CONFIRMED: "bg-[#dcfce7] text-[#15803d]",
  CHECKED_IN: "bg-[#fef9c3] text-[#a16207]",
  COMPLETED: "bg-[#f4f4f5] text-[#71717a]",
  CANCELLED: "bg-[#fee2e2] text-[#dc2626]",
  NO_SHOW: "bg-[#fce7f3] text-[#9d174d]",
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
  const style = STATUS_STYLE[status] ?? "bg-[#f4f4f5] text-[#71717a]";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${style}`}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
