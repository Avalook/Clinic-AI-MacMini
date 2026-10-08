// Hàm THUẦN của màn phiếu kết quả (`_lam-viec/PhieuKetQua.tsx`) — tách ra để
// test được (đợt 3, 27/09/2026).

/** Khoá phẳng của một ô bảng trong trạng thái màn hình: `ma::cột`. */
export const KHOA_BANG = "::";

/** Mã mẫu PHIẾU ĐIỀU TRỊ (máy chủ: `phieu_kham/mau_dieu_tri.py`) — mẫu này vẽ
 *  bằng `PhieuDieuTri` (ô chữ gọn, không Hoàn tất), ở bàn khám lẫn phòng. */
export const MAU_PHIEU_DIEU_TRI = "PHIEU_DIEU_TRI";

/** Máy chủ → màn: ô bảng {cột: giá trị} tách thành các khoá `ma::cột`. */
export function tachGiaTri(
  duLieu: Record<string, { gia_tri: unknown; nguon: string }>,
): Record<string, string> {
  const ra: Record<string, string> = {};
  for (const [k, v] of Object.entries(duLieu ?? {})) {
    const g = v?.gia_tri;
    if (g && typeof g === "object" && !Array.isArray(g)) {
      for (const [c, x] of Object.entries(g as Record<string, unknown>)) {
        ra[`${k}${KHOA_BANG}${c}`] = x == null ? "" : String(x);
      }
    } else ra[k] = g == null ? "" : String(g);
  }
  return ra;
}

/** Màn → máy chủ: gộp `ma::cột` về {ma: {gia_tri: {cột: giá trị}}}; bỏ ô rỗng. */
export function gopGiaTri(
  moi: Record<string, string>,
): Record<string, { gia_tri: unknown; nguon: string }> {
  const ra: Record<string, { gia_tri: unknown; nguon: string }> = {};
  const bang: Record<string, Record<string, string>> = {};
  for (const [k, v] of Object.entries(moi)) {
    if (v === "") continue;
    const i = k.indexOf(KHOA_BANG);
    if (i < 0) ra[k] = { gia_tri: v, nguon: "USER" };
    else (bang[k.slice(0, i)] ??= {})[k.slice(i + KHOA_BANG.length)] = v;
  }
  for (const [k, cot] of Object.entries(bang)) ra[k] = { gia_tri: cot, nguon: "USER" };
  return ra;
}

/**
 * `con_trong` máy chủ trả sau Hoàn tất là danh sách TÊN ô (không phải mã), theo
 * đúng thứ tự khung (`form_engine_service._con_trong`). Đi song song khung để
 * gắn lại mã — cần mã để [link] cuộn tới đúng ô. Hai ô trùng tên vẫn đúng vì
 * đi theo thứ tự, không tra theo tên. Tên lạ / rác → bỏ qua, không ném.
 */
export function ghepConTrong(
  khung: readonly { block?: readonly { ma: string; ten?: string }[] | null }[],
  conTrong: unknown,
): { ma: string; ten: string }[] {
  if (!Array.isArray(conTrong)) return [];
  const ten = conTrong.filter((x): x is string => typeof x === "string" && x !== "");
  const ra: { ma: string; ten: string }[] = [];
  let i = 0;
  for (const muc of khung ?? []) {
    for (const o of muc?.block ?? []) {
      if (i >= ten.length) return ra;
      if ((o.ten ?? o.ma) === ten[i]) {
        ra.push({ ma: o.ma, ten: ten[i] });
        i += 1;
      }
    }
  }
  return ra;
}

/** Mẫu PHIẾU ĐIỀU TRỊ? Nhận mã mẫu có hoặc không tiền tố (`PHIEU_DIEU_TRI`,
 *  `KQ_PHIEU_DIEU_TRI` — mã phiếu, `MAU_PHIEU_DIEU_TRI`). Rỗng / rác → false. */
export function laMauDieuTri(mau: string | null | undefined): boolean {
  return typeof mau === "string" && mau.replace(/^(KQ_|MAU_)/, "") === "PHIEU_DIEU_TRI";
}

/** Câu báo ở phòng dịch vụ sau khi Hoàn tất / [Xong] phiếu (07/10/2026). Phiếu
 *  điều trị đóng được dịch vụ → "Đã xong <tên dịch vụ>" (đó là buổi điều trị,
 *  không phải "phiếu kết quả"); mẫu khác giữ câu cũ. */
export function cauHoanTatPhieu(x: {
  mau: string | null | undefined;
  tenDichVu: string | null | undefined;
  daDongDichVu: boolean;
  viSao: string | null;
  laLanSua: boolean;
  conTrong: readonly string[];
}): string {
  const nhacTrong = x.conTrong.length
    ? ` Còn ${x.conTrong.length} mục trống: ${x.conTrong.join(", ")} (chỉ nhắc).`
    : "";
  if (x.laLanSua) return "Đã ghi bản sửa của kết quả." + nhacTrong;
  if (x.daDongDichVu && laMauDieuTri(x.mau)) {
    return `Đã xong ${x.tenDichVu?.trim() || "dịch vụ"}.` + nhacTrong;
  }
  return (
    (x.daDongDichVu
      ? "Đã hoàn tất phiếu, đóng dịch vụ và báo có kết quả."
      : `Đã hoàn tất phiếu. Dịch vụ CHƯA đóng: ${x.viSao ?? "không rõ lý do"}.`) + nhacTrong
  );
}
