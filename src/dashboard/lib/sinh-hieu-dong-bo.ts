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

/** Một dòng trong khối "Sinh hiệu" CHỈ XEM của phiếu chuyên khoa. */
export interface ONhanSinhHieu {
  nhan: string;
  gia_tri: string;
}

/** Số đo điều dưỡng (vital_measurement) → dòng hiển thị, theo thứ tự trên phiếu. */
export function sinhHieuHienThi(m: DongSinhHieu | null): ONhanSinhHieu[] {
  const k = sinhHieuTheoKhoaPhieu(m);
  return (
    [
      ["huyet_ap", "Huyết áp", "mmHg"],
      ["mach", "Mạch", "lần/phút"],
      ["nhiet_do", "Nhiệt độ", "°C"],
      ["nhip_tho", "Nhịp thở", "lần/phút"],
      ["spo2", "SpO₂", "%"],
      ["can_nang", "Cân nặng", "kg"],
      ["chieu_cao", "Chiều cao", "cm"],
      ["bmi", "BMI", ""],
      ["muc_do_dau", "Mức độ đau", "/10"],
    ] as const
  )
    .filter(([khoa]) => k[khoa])
    .map(([khoa, nhan, dv]) => ({ nhan, gia_tri: dv ? `${k[khoa]} ${dv}` : k[khoa] }));
}

/** Ô sinh hiệu CŨ phiếu chuyên khoa từng tự chứa (trước S0-3, 18/09/2026).
 *  Chỉ để đọc lại hồ sơ cũ khi lượt ấy không có số đo — không còn ô nhập. */
const O_SINH_HIEU_PHIEU_CU: readonly (readonly [string, string])[] = [
  ["huyet_ap", "Huyết áp"],
  ["kls_huyet_ap", "Huyết áp"],
  ["nhip_tim", "Nhịp tim"],
  ["kls_mach", "Mạch"],
  ["nhiet_do", "Nhiệt độ"],
  ["nhip_tho", "Nhịp thở"],
  ["can_nang", "Cân nặng"],
  ["kls_can_nang", "Cân nặng"],
  ["kls_chieu_cao", "Chiều cao"],
  ["bmt", "BMT (ghi tay)"],
];

export function sinhHieuPhieuCu(formData: Record<string, unknown>): ONhanSinhHieu[] {
  return O_SINH_HIEU_PHIEU_CU.flatMap(([khoa, nhan]) => {
    const v = formData[khoa];
    return v === undefined || v === null || String(v).trim() === ""
      ? []
      : [{ nhan, gia_tri: String(v).trim() }];
  });
}

export const COT_SINH_HIEU =
  "systolic, diastolic, pulse, temperature, weight_kg, height_cm, respiratory_rate, spo2, bmi, pain_score, created_at";
