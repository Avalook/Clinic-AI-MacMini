// MÃ VỊ TRÍ LÀ "CA KHÁM" CỦA BÁC SĨ — `LICH_KHAM` (mẫu cũ) + mọi vị trí bác sĩ
// của lịch Kim Ngưu. Bản sao 1-1 của `MA_CA_KHAM_BAC_SI` (config_service.py) và
// hàm DB `la_ca_kham_bac_si`. Khai sẵn vì tài khoản đăng nhập không được đọc
// bảng `vi_tri_lam_viec` qua PostgREST (đo 17/09/2026: 403) — hỏi bảng ấy ở đây
// trả rỗng, và màn đặt lịch mất sạch bác sĩ.
export const MA_CA_KHAM_BAC_SI = [
  "LICH_KHAM",
  "T1_BS_NOITIET",
  "T1_TT_BS",
  "T1_TTNG_BS",
  "T1_SA_BS",
  "T4_SA_BS1",
  "T4_SA_BS2",
  "T4_SANCHAU_BS",
  "T4_SANCHAU_BSTT",
  "T4_SAN_BS",
] as const;
