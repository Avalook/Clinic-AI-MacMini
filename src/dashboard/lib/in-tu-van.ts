// Chữ bác sĩ tư vấn ghi, in ở mục A của phiếu khám (Tuyền 18/11/2026).
// Tách khỏi `phieu-kham.ts` vì tệp đó đã quá trần kích thước.
import type { DauPhieu, MucPhieu, ONhap } from "./phieu-kham";

/** Các đoạn ghi chú tư vấn cần in cho một mục — cùng nguồn `dau.tu_van` với màn
 *  khám (`KhoiTuVan`). Bỏ đoạn trống, và bỏ đoạn GIỐNG HỆT một ô đã gõ trong mục:
 *  bác sĩ hay chép một nội dung vào cả ô tư vấn lẫn "Ghi chú bổ sung", in hai lần
 *  là thừa. Khác dù một chữ thì vẫn in cả hai — không đoán ô nào đúng hơn. */
export function ghiChuTuVanIn(
  tuVan: DauPhieu["tu_van"] | undefined,
  m: Pick<MucPhieu, "block">,
  duLieu: Record<string, ONhap>,
): string[] {
  const daGo = new Set(
    m.block
      .map((o) => duLieu[o.ma]?.gia_tri)
      .filter((g): g is string => typeof g === "string")
      .map((g) => g.trim()),
  );
  return (tuVan ?? []).map((g) => g.noi_dung.trim()).filter((t) => t !== "" && !daGo.has(t));
}
