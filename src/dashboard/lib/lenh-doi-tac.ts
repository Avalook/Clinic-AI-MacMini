// Thân lệnh của POST /api/doi-tac/lenh — tách khỏi route để test được (route Next
// không được export tên khác GET/POST). Chỉ kiểm hình dạng; luật ở `DoiTacService`.
//
// Bẫy đã cắn (bấm staging 16/10/2026): route dựng lại thân chỉ với ly_do +
// xac_nhan nên `mo_lai_phong` rơi mất — Hoàn tác nhận mẫu ở Phòng đối tác gỡ mốc
// đối tác nhưng lần làm của phòng vẫn "Đã xong". Thêm trường mới vào thân lệnh
// thì thêm ở đây.

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

const LENH = new Set(["tra-ket-qua", "huy-tra-ket-qua", "huy-nhan-mau"]);

export type LenhDoiTac = {
  lenh: string;
  chi_dinh_id: string;
  du_lieu: Record<string, unknown>;
};

/** null = lệnh hoặc mã việc không hợp lệ. */
export function docLenhDoiTac(than: unknown): LenhDoiTac | null {
  const t = (than && typeof than === "object" ? than : {}) as Record<string, unknown>;
  const lenh = typeof t.lenh === "string" ? t.lenh : "";
  const id = typeof t.chi_dinh_id === "string" ? t.chi_dinh_id : "";
  if (!LENH.has(lenh) || !UUID_RE.test(id)) return null;
  if (lenh === "tra-ket-qua") return { lenh, chi_dinh_id: id, du_lieu: {} };
  const du_lieu: Record<string, unknown> = {
    ly_do: typeof t.ly_do === "string" ? t.ly_do : null,
    xac_nhan: t.xac_nhan === true,
  };
  if (lenh === "huy-nhan-mau") du_lieu.mo_lai_phong = t.mo_lai_phong === true;
  return { lenh, chi_dinh_id: id, du_lieu };
}
