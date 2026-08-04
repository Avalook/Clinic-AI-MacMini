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
  is_active: boolean;
  floors: ConfigFloor[];
}

export interface NodeDef {
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
}

export interface ConfigService {
  service_type_id: string;
  code: string;
  name: string;
  is_active: boolean;
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
