// Hình dạng một dòng nhật ký, đúng như FastAPI trả về
// (services/audit_log_service.py).
//
// NĂM TRƯỜNG ĐÃ GIẢI NGHĨA XONG Ở BACKEND — `actor_name`, `subject_label`,
// `action_label`, `nguon_label`, `aggregate_label`. Màn hình hiện thẳng, không
// dựng lại. Đó là cả điểm của lần sửa này: trước đây màn hình tự dựng chúng từ
// dữ liệu thô, và đều sai.
//
// Hai trường cuối vừa chuyển về backend: chúng từng là hai `Record<string,
// string>` trong AuditLogBoard.tsx, mỗi bảng bảy mục cho một từ vựng hơn ba
// mươi giá trị, nên phần lớn dòng rơi xuống nhánh `?? nguon` và in ra địa chỉ
// mã nguồn.

export interface AuditEvent {
  id: string;
  occurred_at: string;
  event_type: string;

  /** Tên nhân viên. `null` = hệ thống (migration, seed, worker) — KHÔNG phải
   *  "không rõ ai", và hiện "Hệ thống" cho nó là đúng. */
  actor_name: string | null;
  actor_role: string | null;
  /** Để đếm số NGƯỜI. Trước đây màn hình đếm `new Set(source)` nên ra 14 —
   *  đó là 14 tên đường ghi, không phải 14 nhân viên. */
  actor_staff_id: string | null;

  /** Việc này về ai: tên bệnh nhân kèm mã, hoặc "Luật của BS. X", hoặc
   *  "Cấu hình phòng khám". Backend dựng, vì thứ tự ưu tiên giữa chúng là
   *  quyết định về nghĩa chứ không phải về trình bày. */
  subject_label: string;

  /** Tên việc bằng tiếng Việt. Rơi về chính mã khi chưa đặt tên — mã thô xấu
   *  nhưng tra cứu được, còn ô trống đọc thành "không có gì xảy ra". */
  action_label: string;

  /** Đường ghi ("api:booking", "dashboard", "workflow-kernel"). Thông tin có
   *  ích — nó chỉ không được đứng THAY tên người. Dùng để lọc/tìm; thứ hiện ra
   *  màn hình là `nguon_label`. */
  nguon_thao_tac: string | null;
  /** Tên MÀN, tiếng Việt. "Hệ thống" khi không có đường ghi. */
  nguon_label: string;

  aggregate_type: string;
  /** Loại đối tượng bằng tiếng Việt — "Tuần lịch trực", không phải
   *  "roster_week". */
  aggregate_label: string;
  aggregate_id: string;
  payload: Record<string, unknown> | null;
}
