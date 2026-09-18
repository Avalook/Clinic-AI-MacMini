// Một dòng lịch khám mà biểu mẫu bệnh án (ClinicalRecordForm) nhận vào.
//
// Trước 18/09/2026 kiểu này nằm trong DoctorWorkBoard.tsx — màn "/tasks" cũ,
// nay đã gỡ (docs/SITEMAP.md mục C). Tách ra đây để các màn còn sống không
// phải import từ một màn đã chết.

export interface DoctorApptRow {
  id: string;
  slot_start: string;
  status: string;
  /** Số thứ tự khám (queue_number) — lễ tân cấp khi check-in. */
  queue_number?: string | null;
  /** "Khám lần đầu" | "Tái khám" | "" — suy từ lịch sử hẹn (server tính sẵn). */
  phan_loai?: string;
  /** THỨ TỰ GỌI — backend tính (services/queue_order.py). Màn hình chỉ xếp
   *  theo con số này, không tự tính lại. Trước đây mỗi màn gọi compareQueue()
   *  từ một bản chép của luật bằng TypeScript. */
  call_order?: number | null;
  /** Làn: -2 ƯT · -1 chờ đọc KQ · 0 có hẹn đúng giờ · 1 vãng lai/đến muộn */
  call_tier?: number | null;
  /** UU_TIEN | CHO_DOC_KQ | DAT_TRUOC_DUNG_GIO | DEN_TRUC_TIEP | DEN_TRE | CHUA_DEN */
  call_reason?: string | null;
  /** Có người đến TRƯỚC mà bị xếp SAU mình — chỗ cần một câu giải thích. */
  promoted?: boolean;
  promoted_over?: number;
  patient: {
    clinic_patient_id: string;
    patient_code: string;
    full_name: string;
    date_of_birth: string | null;
    phone_primary: string | null;
    phone_secondary: string | null;
    gender: string | null;
    ethnicity: string | null;
    nationality: string | null;
    occupation: string | null;
    patient_objection: string | null;
    address: string | null;
    guardian_name: string | null;
  } | null;
  service: {
    name: string;
    /** Mã phiếu khám chuyên khoa, backend CHỌN SẴN theo giới bệnh nhân
     *  (khám tiền hôn nhân: nữ ra PK, nam ra NK). `null` = dịch vụ này không
     *  có phiếu riêng — màn hình phải NÓI RA, không được ẩn im lặng.
     *
     *  KHÔNG BẮT BUỘC vì hai màn khác (lưới tuần ở Trang chủ, Danh sách bệnh
     *  nhân) dựng dòng từ truy vấn riêng chưa mang cột này. Thiếu nó thì rơi
     *  về cách đoán cũ theo tên dịch vụ — kém hơn, nhưng không vỡ. */
    form_code?: string | null;
  } | null;
  /** Kênh đặt — "WALK_IN" = vãng lai; còn lại = đặt hẹn online. */
  booking_channel?: string | null;
  /** Mốc giờ đến thật (visit.checked_in_at). */
  checked_in_at?: string | null;
  /** Đã có KQ lab về hết → chờ bác sĩ đọc. */
  b3_ready?: boolean | null;
}
