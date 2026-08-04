// Hình dạng dữ liệu bảng điều phối — khớp đúng những gì
// `/api/v1/dispatch/*` trả về (services/dispatch_service.py).
//
// Prototype có kiểu riêng với dữ liệu giả (`data/mock-data.ts`): StationId là
// một union chuỗi cứng, Patient có `slaPercent`, `waitReason`… Những thứ đó là
// phát minh của bản dựng thử. Ở đây kiểu đi theo BACKEND, vì backend là thứ
// thật sự tồn tại — và nếu hai bên lệch nhau thì màn hình nói dối, không phải
// backend.

/** Một bệnh nhân đang trong phòng khám. */
export interface DispatchPatient {
  visit_id: string;
  patient_name: string | null;
  patient_code: string | null;
  clinic_patient_id: string | null;
  queue_number: string | null;
  specialty: string | null;
  doctor_name: string | null;
  current_node_code: string | null;
  current_node_name: string | null;
  room_id: string | null;
  room_code: string | null;
  room_name: string | null;
  /** Phút đã chờ Ở BƯỚC HIỆN TẠI. */
  wait_minutes: number;
  /** Phút đã ở trong phòng khám, tính từ lúc check-in. Khác hẳn cái trên. */
  total_minutes: number;
  threshold_minutes: number;
  done_steps: string[];
  route_steps: string[] | null;
  next_step: string | null;
  checked_in_at: string | null;
}

/** Một phòng và tải hiện tại của nó. */
export interface DispatchRoom {
  id: string;
  code: string;
  name: string;
  node_code: string;
  node_name: string | null;
  capacity: number;
  accepting: boolean;
  show_on_tv: boolean;
  /** Đang được phục vụ (bước đã bắt đầu). */
  serving: number;
  /** Đang chờ tới lượt. */
  waiting: number;
  max_wait: number;
  avg_wait: number;
  threshold_minutes: number;
  threshold_waiting: number;
  state: "ok" | "warning" | "critical";
}

export interface DispatchAlert {
  type: string;
  severity: "critical" | "warning";
  /** Câu tiếng Việt đọc được, không phải mã kỹ thuật. */
  message: string;
  room_code: string | null;
  patients: { name: string | null; code: string | null }[];
}

export interface RouteTemplate {
  code: string;
  name: string;
  steps: string[];
}

export interface DispatchHistoryRow {
  at: string;
  event_type: string;
  visit_id: string | null;
  from_node: string | null;
  to_node: string | null;
  from_room: string | null;
  to_room: string | null;
  reason: string | null;
  actor_name: string | null;
  patient_name: string | null;
  patient_code: string | null;
}

/** Tên bước đọc được, cho những chỗ chỉ có `node_code` trong tay. */
export const NODE_LABEL: Record<string, string> = {
  "LUOTKHAM-01": "Tiếp nhận",
  "LUOTKHAM-03": "Sinh hiệu",
  "LUOTKHAM-14": "Thanh toán",
  "KHAM-PHUKHOA": "Khám phụ khoa",
  "KHAM-SANKHOA": "Khám sản khoa",
  "KHAM-NOITIET": "Khám nội tiết",
  "KHAM-NAMKHOA": "Khám nam khoa",
  "KHAM-HIEMMUON-VOSINH": "Khám hiếm muộn",
  "DICHVU-SIEUAM": "Siêu âm",
  "DICHVU-LAYMAU-MAU": "Lấy máu",
  "DICHVU-DUYET-KETQUA": "Đọc kết quả",
  "THUOC-04": "Nhà thuốc",
};

export function nodeLabel(code: string | null): string {
  if (!code) return "—";
  return NODE_LABEL[code] ?? code;
}

/** "1 giờ 05 phút" thay vì "65" — cột tổng thời gian hay vượt một tiếng. */
export function humanMinutes(m: number): string {
  if (m < 60) return `${m} phút`;
  const h = Math.floor(m / 60);
  return `${h}h${String(m % 60).padStart(2, "0")}`;
}
