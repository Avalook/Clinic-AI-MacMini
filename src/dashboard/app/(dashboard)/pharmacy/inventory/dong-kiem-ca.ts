// Dòng cần đếm ở Kiểm đầu / cuối ca: mọi (thuốc, đơn vị) có lô QUẦY CÒN THUỐC, cộng các
// dòng đã nằm trong phiếu đang mở. Lô quầy tồn 0 không vào: trưa 16/11 chuyển tồn quầy
// về kho để lại 145 lô QUẦY rỗng, màn đòi đếm ~100 thuốc quầy không có (Tuyền: quầy chỉ
// hiện thuốc đã chuyển sang).

export type LoKiem = {
  drug_catalog_id: string | null;
  unit: string;
  noi_chua?: string | null;
  quantity_on_hand: number | string;
  drug?: { name_base?: string | null; name_raw?: string | null; variant?: string | null } | null;
};

export type DongPhieuKiem = { drug_catalog_id: string; don_vi: string; ten: string };

export type DongCanDem = { khoa: string; thuoc: string; ten: string; dv: string };

export const khoaDong = (thuoc: string, dv: string) => `${thuoc}|${dv.trim().toLowerCase()}`;

export function dongCanDem(batches: LoKiem[], dongPhieu: DongPhieuKiem[]): DongCanDem[] {
  const m = new Map<string, DongCanDem>();
  for (const b of batches) {
    if (b.noi_chua === "KHO" || !b.drug_catalog_id || !(Number(b.quantity_on_hand) > 0)) continue;
    const k = khoaDong(b.drug_catalog_id, b.unit);
    if (m.has(k)) continue;
    const bien = b.drug?.variant ? ` (${b.drug.variant})` : "";
    m.set(k, {
      khoa: k,
      thuoc: b.drug_catalog_id,
      ten: `${b.drug?.name_base ?? b.drug?.name_raw ?? "—"}${bien}`,
      dv: b.unit,
    });
  }
  for (const d of dongPhieu) {
    const k = khoaDong(d.drug_catalog_id, d.don_vi);
    if (!m.has(k)) m.set(k, { khoa: k, thuoc: d.drug_catalog_id, ten: d.ten, dv: d.don_vi });
  }
  return [...m.values()].sort((a, b) => a.ten.localeCompare(b.ten, "vi"));
}
