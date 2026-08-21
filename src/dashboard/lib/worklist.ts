/**
 * Types and pure helpers for a workspace queue.
 *
 * No session, no fetch, no server-only imports — the queue board is a client
 * component and importing this must not pull cookies() into the browser
 * bundle. The fetch lives in lib/worklist-server.ts.
 */

export interface WorklistPatient {
  clinic_patient_id: string | null;
  patient_code: string | null;
  full_name: string | null;
  date_of_birth: string | null;
  gender: string | null;
  phone_primary: string | null;
}

export interface WorklistItem {
  id: string;
  node_code: string;
  node_name: string | null;
  status: "PENDING" | "IN_PROGRESS" | "COMPLETED" | "SKIPPED" | "CANCELLED";
  priority: string;
  version: number;
  visit_id: string | null;
  appointment_id: string | null;
  assigned_to: string | null;
  assigned_role: string | null;
  actor_roles: string[];
  actionable_by_me: boolean;
  blocked: boolean;
  due_at: string | null;
  created_at: string | null;
  started_at: string | null;
  patient: WorklistPatient;
  queue_number: string | null;
  slot_start: string | null;
  booking_channel: string | null;
  is_priority_slot: boolean;
  /** Loại dịch vụ khám của lượt — để bàn khám mở đúng biểu mẫu. */
  service_code: string | null;
  service_name: string | null;
  /** Mã biểu mẫu khám: PK / SK / NT / NK / HMVS. `null` = dịch vụ không phải
   *  một loại khám. Nhiều dịch vụ dùng chung một biểu mẫu. */
  form_code: string | null;
  checked_in_at: string | null;
  /** Lúc khách được GỌI VÀO KHÁM — quỹ thời gian riêng, không phải giờ check-in.
   *  null = chưa gọi. Xem `visit.exam_started_at` (migration 20260820000001). */
  exam_started_at?: string | null;
}

/** Số phút khách ĐÃ CHỜ — và đồng hồ này DỪNG khi được gọi vào khám.
 *
 *  HAI QUỸ THỜI GIAN, KHÔNG PHẢI MỘT (Tuyền 20/08/2026): check-in lúc 18:00,
 *  gọi vào khám lúc 18:10 thì khách chờ đúng 10 phút — dù 19:00 mới khám xong.
 *  Bản cũ đếm tới hiện tại bất kể đã gọi hay chưa, nên "thời gian chờ" của một
 *  người đang nằm trên bàn khám vẫn tăng đều: con số ấy không trả lời được câu
 *  hỏi nào của quầy, và làm hỏng luôn số liệu phân tích về sau. */
export function waitedMinutes(item: WorklistItem, now: Date = new Date()): number {
  const from = item.checked_in_at ?? item.created_at;
  if (!from) return 0;
  const den = item.exam_started_at ? new Date(item.exam_started_at) : now;
  return Math.max(0, Math.round((den.getTime() - new Date(from).getTime()) / 60000));
}

/** Số phút ĐANG KHÁM — đồng hồ thứ hai, chạy từ lúc được gọi vào.
 *
 *  Chưa gọi thì trả `null` chứ không trả 0: "chưa bắt đầu" và "vừa bắt đầu" là
 *  hai chuyện khác nhau, và màn hình phải nói được sự khác ấy. */
export function examMinutes(
  item: WorklistItem,
  now: Date = new Date(),
): number | null {
  if (!item.exam_started_at) return null;
  const from = new Date(item.exam_started_at).getTime();
  return Math.max(0, Math.round((now.getTime() - from) / 60000));
}

/** "1994 · Nữ · 32 tuổi", the subtitle used on every patient card in the design. */
export function patientLine(p: WorklistPatient): string {
  const bits: string[] = [];
  if (p.date_of_birth) {
    const year = new Date(p.date_of_birth).getFullYear();
    bits.push(String(year));
    const age = new Date().getFullYear() - year;
    if (p.gender) bits.push(p.gender);
    bits.push(`${age} tuổi`);
  } else if (p.gender) {
    bits.push(p.gender);
  }
  return bits.join(" · ");
}
