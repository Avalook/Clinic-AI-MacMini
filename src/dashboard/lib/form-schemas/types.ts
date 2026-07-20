// Định dạng schema cho ENGINE form khám chuyên khoa (config-driven).
// Engine đọc schema theo service_code → tự sinh form, KHÔNG hard-code từng form.
// Giá trị form lưu phẳng vào form_data JSONB: { [field.key]: value }.

export type FieldType =
  | "text"
  | "textarea"
  | "number"
  | "date"
  | "radio" // chọn 1 trong options (value = string)
  | "checkbox" // 1 ô bật/tắt (value = boolean)
  | "checkbox_group" // chọn nhiều (value = string[])
  | "conditional"; // textarea chi tiết, chỉ hiện khi parent khớp

export interface FieldOption {
  value: string;
  label: string;
}

export interface FormField {
  key: string;
  label: string;
  type: FieldType;
  /** Cho radio / checkbox_group. */
  options?: FieldOption[];
  /** Hậu tố đơn vị cho number (vd "tuổi", "ngày", "kg"). */
  unit?: string;
  placeholder?: string;
  /** Field chiếm trọn hàng (textarea/conditional luôn full). */
  fullWidth?: boolean;
  /** Hiện field này CHỈ khi field cha (parent.key) khớp parent.equals.
   *  - radio/text: so khớp bằng (===)
   *  - checkbox_group: parent.equals nằm trong mảng đã chọn
   *  - checkbox: parent.equals là boolean. */
  parent?: { key: string; equals: string | boolean };
}

export interface FormSection {
  title: string;
  fields: FormField[];
}

export interface FormSchema {
  service_code: string;
  title: string;
  sections: FormSection[];
}

/** Giá trị 1 field trong form_data. */
export type FieldValue = string | number | boolean | string[] | null | undefined;
export type FormData = Record<string, FieldValue>;
