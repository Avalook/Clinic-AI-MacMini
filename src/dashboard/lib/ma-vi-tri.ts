// Mã vị trí cơ sở thứ hai trở đi → "mã mẫu" Kim Ngưu (08/10/2026, Hào Nam).
// Bản TS y hệt `clinicai/core/ma_vi_tri.py`: `HN__T1_LETAN` → `T1_LETAN`,
// `HN__T1_THUNGAN__2` → `T1_THUNGAN`. Mọi bảng tra viết cứng theo mã Kim Ngưu
// (nhóm thanh bên, ca khám bác sĩ) tra qua hàm này.
export function maMau(ma: string): string {
  return ma.replace(/^[A-Z0-9]+__/, "").replace(/__\d+$/, "");
}
