/** Bộ phận Siêu âm — hình dạng dữ liệu, khớp 1-1 với ultrasound_board_service.py.
 *
 *  Đặt riêng để cả trang server và các thành phần client cùng đọc một khai báo.
 *  Hai bản sao là hai chỗ để lệch khi backend thêm cột.
 */

export interface SonoQueueItem {
  work_item_id: string;
  visit_id: string;
  stt: number;
  queue_number: string | null;
  patient_name: string | null;
  patient_code: string | null;
  clinic_patient_id: string | null;
  gender: string | null;
  birth_year: number | null;
  service_name: string | null;
  appointment_at: string | null;
  indication_doctor: string | null;
  room_code: string | null;
  room_name: string | null;
  room_floor: string | null;
  status: string;
  wait_minutes: number;
  /** Bốn ô, và ô cuối LUÔN là phép AND của ba ô trên — backend tính, không
   *  phải một cột lưu sẵn. Giao diện chỉ vẽ lại. */
  readiness: {
    checked_in: boolean;
    identified: boolean;
    indication_valid: boolean;
    may_perform: boolean;
  };
}

export interface SonoRoom {
  id: string;
  code: string;
  name: string;
  floor: string | null;
  capacity: number;
  accepting: boolean;
  serving: number;
  waiting: number;
}

export interface SonoRecord {
  ultrasound_id: string;
  visit_id: string | null;
  clinic_patient_id: string | null;
  patient_name: string | null;
  patient_code: string | null;
  gender: string | null;
  birth_year: number | null;
  ultrasound_type: string | null;
  findings: Record<string, unknown> | null;
  impression: string | null;
  /** Luôn rỗng hôm nay: chưa có kho tệp nào được dựng cho ảnh siêu âm. */
  image_refs: string[];
  gestational_age_weeks: number | null;
  performed_at: string | null;
  performed_by_name: string | null;
  signed_at: string | null;
  signed_by_name: string | null;
  room_name: string | null;
  room_floor: string | null;
  updated_at: string | null;
}

export interface SonoPatientGroup {
  clinic_patient_id: string | null;
  patient_name: string | null;
  patient_code: string | null;
  gender: string | null;
  birth_year: number | null;
  report_count: number;
  reports: SonoRecord[];
}
