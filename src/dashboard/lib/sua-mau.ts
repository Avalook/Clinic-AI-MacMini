// Trình sửa mẫu kết quả (27/09/2026) — phần THUẦN, test bằng node.
//
// LUẬT GIỮ MÃ: `ma` của ô là khoá của dữ liệu đã điền (`du_lieu[ma]`). Đổi tên ô
// KHÔNG đổi `ma` — phiếu cũ, báo cáo, bản in vẫn đọc đúng. Chỉ ô / mục / cột MỚI
// mới được sinh mã, và mã sinh ra không trùng mã nào đang có trong CẢ mẫu (máy
// chủ cũng chặn trùng — đây là để người sửa không phải gặp lỗi ấy).
//
// Luật khung thật (kiểu ô, lựa chọn, mặc định…) nằm ở máy chủ
// (`phieu_kham/kiem_khung_mau.py`); ở đây chỉ NHẮC trước để đỡ một vòng gửi.

export type KieuO = "text" | "doan_van" | "so" | "ngay" | "chon";

export const NHAN_KIEU: Record<KieuO, string> = {
  text: "Chữ ngắn",
  doan_van: "Đoạn văn",
  so: "Số",
  ngay: "Ngày",
  chon: "Chọn một",
};

export interface CotMau {
  ma: string;
  ten: string;
  /** Khoá vẽ ở trình duyệt (không gửi đi). */
  k?: string;
}

export interface OMau {
  /** Rỗng = ô MỚI: mã sinh lúc xuất bản từ tên cuối cùng (`ganMaMoi`). */
  ma: string;
  k?: string;
  ten: string;
  kieu: KieuO;
  chon?: string[];
  /** Cách vẽ ô chọn ("o_tick" = ô tích nhanh). Màn sửa chưa có chỗ đổi — chỉ
   *  GIỮ khi sửa mẫu, không thì xuất bản lại là mất (29/09/2026). */
  hien_thi?: "o_tick";
  goi_y?: string;
  /** Chữ; hoặc theo cột ({ma_cột: chữ}) khi mục là bảng. */
  mac_dinh?: string | Record<string, string>;
}

export interface MucMau {
  ma: string;
  k?: string;
  ten: string;
  cot?: CotMau[];
  block: OMau[];
}

/** "Buồng trứng trái (mm)" → "buong_trung_trai_mm". */
export function slugMa(ten: string): string {
  const s = ten
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 48);
  return s || "o";
}

/** Mã mới không trùng `daCo` — thêm hậu tố _2, _3… nếu cần. */
export function maMoi(ten: string, daCo: ReadonlySet<string>): string {
  const goc = slugMa(ten);
  if (!daCo.has(goc)) return goc;
  for (let i = 2; ; i++) {
    const m = `${goc.slice(0, 44)}_${i}`;
    if (!daCo.has(m)) return m;
  }
}

/** Mọi mã ô trong mẫu (mã ô phải duy nhất trên CẢ mẫu). */
export function maOTrongMau(khung: readonly MucMau[]): Set<string> {
  return new Set(khung.flatMap((m) => m.block.map((o) => o.ma)));
}

/**
 * Sinh mã cho mục / ô / cột MỚI (mã rỗng) từ TÊN CUỐI CÙNG — sinh lúc bấm
 * "+ Thêm" thì mã thành "o_moi_3" vô nghĩa. Mã cũ giữ nguyên. Ô duy nhất trên
 * cả mẫu; mục duy nhất giữa các mục; cột duy nhất trong bảng của nó.
 */
export function ganMaMoi(khung: readonly MucMau[]): MucMau[] {
  const maO = new Set(khung.flatMap((m) => m.block.map((o) => o.ma).filter(Boolean)));
  const maMuc = new Set(khung.map((m) => m.ma).filter(Boolean));
  return khung.map((m) => {
    const ma = m.ma || maMoi(m.ten, maMuc);
    maMuc.add(ma);
    const maCot = new Set((m.cot ?? []).map((c) => c.ma).filter(Boolean));
    const cot = m.cot?.map((c) => {
      const mc = c.ma || maMoi(c.ten, maCot);
      maCot.add(mc);
      return { ...c, ma: mc };
    });
    const block = m.block.map((o) => {
      const mo = o.ma || maMoi(o.ten, maO);
      maO.add(mo);
      return { ...o, ma: mo };
    });
    return { ...m, ma, ...(cot ? { cot } : {}), block };
  });
}

/** Những điều nên sửa trước khi xuất bản — không chặn, máy chủ mới là luật. */
export function nhacTruocXuatBan(khung: readonly MucMau[]): string[] {
  const ra: string[] = [];
  if (khung.length === 0) ra.push("Mẫu chưa có mục nào.");
  for (const m of khung) {
    if (!m.ten.trim()) ra.push("Có mục chưa đặt tên.");
    if (m.block.length === 0) ra.push(`Mục “${m.ten || "(chưa tên)"}” chưa có ô nào.`);
    if (m.cot && m.cot.some((c) => !c.ten.trim())) ra.push(`Bảng “${m.ten}” có cột chưa đặt tên.`);
    for (const o of m.block) {
      if (!o.ten.trim()) ra.push(`Mục “${m.ten}” có ô chưa đặt tên.`);
      if (o.kieu === "chon" && !(o.chon ?? []).some((x) => x.trim())) {
        ra.push(`Ô “${o.ten}” kiểu chọn chưa có lựa chọn.`);
      }
    }
  }
  const coKetLuan = khung.some(
    (m) => /kết luận/i.test(m.ten) || m.block.some((o) => /kết luận/i.test(o.ten)),
  );
  if (khung.length > 0 && !coKetLuan) {
    ra.push("Mẫu chưa có mục Kết luận (được phép nếu mẫu gốc không có).");
  }
  return [...new Set(ra)];
}

/** Bỏ trường rỗng trước khi gửi: lựa chọn trống, gợi ý trống, mặc định trống. */
export function donKhung(khung: readonly MucMau[]): MucMau[] {
  return khung.map((m) => ({
    ma: m.ma,
    ten: m.ten.trim(),
    ...(m.cot && m.cot.length ? { cot: m.cot.map((c) => ({ ma: c.ma, ten: c.ten.trim() })) } : {}),
    block: m.block.map((o) => {
      const ra: OMau = { ma: o.ma, ten: o.ten.trim(), kieu: o.kieu };
      if (o.kieu === "chon") ra.chon = (o.chon ?? []).map((x) => x.trim()).filter(Boolean);
      if (o.kieu === "chon" && o.hien_thi === "o_tick") ra.hien_thi = "o_tick";
      if (o.goi_y?.trim()) ra.goi_y = o.goi_y.trim();
      if (typeof o.mac_dinh === "string" && o.mac_dinh.trim()) ra.mac_dinh = o.mac_dinh.trim();
      if (o.mac_dinh && typeof o.mac_dinh === "object" && m.cot?.length) {
        const cot = new Set(m.cot.map((c) => c.ma));
        const md = Object.fromEntries(
          Object.entries(o.mac_dinh).filter(([k, v]) => cot.has(k) && v.trim()),
        );
        if (Object.keys(md).length) ra.mac_dinh = md;
      }
      return ra;
    }),
  }));
}

/**
 * Tên mục để HIỆN ở phiếu kết quả / màn xem / bản in — `null` = không vẽ tiêu
 * đề. Mẫu dựng từ PDF không có tiêu đề mục từng mang chữ giữ chỗ "(không có
 * tiêu đề mục)" (Phiếu soi âm hộ v3, 26/09/2026); bản mới đã đặt tên, nhưng
 * phiếu ghim bản cũ vẫn mang chữ ấy — không in nó ra cho khách đọc.
 */
export function tenMucHien(ten: unknown): string | null {
  if (typeof ten !== "string") return null;
  const t = ten.normalize("NFC").trim();
  if (!t) return null;
  if (/^\(?\s*không có tiêu đề(\s+mục)?\s*\)?$/iu.test(t)) return null;
  return t;
}
