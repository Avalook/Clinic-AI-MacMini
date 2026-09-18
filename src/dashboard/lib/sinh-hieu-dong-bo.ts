// SINH HIỆU ĐIỀU DƯỠNG ĐO → MỌI CHỖ ĐỌC (17/09/2026).
//
// Điều dưỡng lưu một dòng `vital_measurement`. Bệnh án và phiếu khám chuyên khoa
// là hai nơi khác nhau, mỗi nơi có ô sinh hiệu riêng — trước đây không nơi nào
// đọc bảng đo, nên bác sĩ mở bàn khám thấy ô trống dù điều dưỡng đã đo xong.
// Chỉ chuyển dạng dữ liệu; không có luật nghiệp vụ.

export interface DongSinhHieu {
  systolic: number | null;
  diastolic: number | null;
  pulse: number | null;
  temperature: number | string | null;
  weight_kg: number | string | null;
  height_cm: number | string | null;
  respiratory_rate: number | null;
  spo2: number | null;
  bmi: number | string | null;
  pain_score: number | null;
}

const chu = (v: unknown): string =>
  v === null || v === undefined || v === "" ? "" : String(Number(v));

/** Dạng khoá mà bệnh án (soap_objective.vitals) và các phiếu khám dùng. */
export function sinhHieuTheoKhoaPhieu(m: DongSinhHieu | null): Record<string, string> {
  if (!m) return {};
  const ra: Record<string, string> = {
    mach: chu(m.pulse),
    nhiet_do: chu(m.temperature),
    huyet_ap:
      m.systolic !== null && m.diastolic !== null ? `${m.systolic}/${m.diastolic}` : "",
    nhip_tho: chu(m.respiratory_rate),
    spo2: chu(m.spo2),
    can_nang: chu(m.weight_kg),
    chieu_cao: chu(m.height_cm),
    bmi: chu(m.bmi),
    muc_do_dau: chu(m.pain_score),
  };
  return Object.fromEntries(Object.entries(ra).filter(([, v]) => v !== ""));
}

export const COT_SINH_HIEU =
  "systolic, diastolic, pulse, temperature, weight_kg, height_cm, respiratory_rate, spo2, bmi, pain_score, created_at";
