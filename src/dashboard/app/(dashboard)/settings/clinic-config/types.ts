// Hình dạng do clinic_config_service trả về. Giữ khớp với `_group_locations`
// và `staff()` ở đó — đổi một bên mà quên bên kia thì màn hình hiện trống chứ
// không báo lỗi.

export interface ConfigRoom {
  room_id: string;
  code: string;
  name: string | null;
  capacity: number | null;
  is_active: boolean;
  /** Bước CHÍNH của phòng. Không bỏ được khỏi `serves` (backend chặn). */
  primary_node: string | null;
  /** Mọi bước phòng này phục vụ. "Phòng siêu âm" = có DICHVU-SIEUAM ở đây. */
  serves: string[];
  /** Nhóm việc phòng này là PHÒNG CHUYÊN ★ (07/10/2026): tick sẵn khi phòng
   *  Nhận chỉ định chưa hướng dẫn, quầy gợi ý hướng dẫn. Không thu hẹp gì. */
  chuyen?: string[];
  /** Dịch vụ gắn RIÊNG cho phòng (30/09/2026). Dịch vụ có ở đây thì chỉ các
   *  phòng được gắn làm được — máy chủ quyết khi xếp phòng. */
  dich_vu: DichVuPhong[];
}

export interface DichVuPhong {
  ma: string;
  ten: string;
  node: string | null;
}

/** Một dịch vụ trong ô chọn — `chi_lam_o` = các phòng đang được gắn riêng. */
export interface DichVuChonDuoc {
  ma: string;
  ten: string;
  ma_kv: string | null;
  chi_lam_o: string[];
}

/** Nhóm việc CHỌN ĐƯỢC cho phòng — máy chủ đã lọc (không node quản trị). */
export interface ViecChonDuoc {
  node: string;
  ten: string;
  loai: "KHAM" | "DICHVU";
  dich_vu: DichVuChonDuoc[];
}

export interface ConfigFloor {
  /** `null` = CHƯA KHAI tầng, khác với tầng tên rỗng. */
  floor: string | null;
  rooms: ConfigRoom[];
}

export interface ConfigLocation {
  location_id: string;
  code: string;
  name: string;
  /** Địa chỉ cơ sở (27/09/2026 — sửa được ở màn Cấu trúc phòng khám). */
  address?: string | null;
  is_active: boolean;
  floors: ConfigFloor[];
}

export interface NodeDef {
  code: string;
  name: string;
}

/** Dịch vụ / nhóm khám không có phòng ĐANG BẬT nào làm được (30/09/2026: chỉ
 *  việc khách đến phòng, không tính việc quản trị, đối tác làm trọn). */
export interface ConfigMissing {
  code: string;
  name: string;
  loi: "CONFIG_MISSING";
}

/** Nhóm dịch vụ có phòng làm được mà CHƯA phòng nào đánh ★ (chỉ nhắc). */
export interface ChuaPhongChuyen {
  code: string;
  name: string;
}

export interface ConfigStaff {
  staff_id: string;
  full_name: string;
  short_name: string | null;
  role: string;
  location_name: string | null;
  nodes: string[];
  /** Bác sĩ mà thư ký (TKYK) này đi cùng — quản lý phân (20260915000020). */
  bac_si?: string[];
}

export interface ConfigService {
  service_type_id: string;
  code: string;
  name: string;
  is_active: boolean;
  /** Phí khám khi chưa chọn dịch vụ khám con. */
  gia_mac_dinh: number;
  /** `null` = dịch vụ không có phiếu khám chuyên khoa (thủ thuật, tư vấn).
   *  Khác với "chưa khai" — màn bác sĩ nói ra điều đó thay vì để trống. */
  form_code: string | null;
  /** Chỉ khai khi nội dung khám khác nhau theo giới. Hôm nay đúng một dịch vụ:
   *  khám tiền hôn nhân — nữ khám phụ khoa, nam khám nam khoa. */
  form_code_nam: string | null;
}

export interface FormDef {
  form_code: string;
  title: string;
}
