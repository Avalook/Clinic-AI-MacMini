// Lưu số đếm kiểm kê ca — phần quyết định, KHÔNG React, test bằng hàng đợi thật
// (`tests/kiem-ca-tu-luu-boundary.test.mts`). Móc React ở `tu-luu-kiem-ca.tsx`.
//
// MỘT ĐƯỜNG GHI (soát 20/11). Bản đầu có hai đường: tự lưu, và "Lưu nháp"/"Chốt" tự
// POST bản CHỤP lúc bấm → gõ thêm trong lúc chờ thì bản chụp cũ đè số mới. Nay mọi
// lần ghi đi qua MỘT hàng đợi, và mỗi lần gửi đọc trạng thái MỚI NHẤT ngay lúc gửi.

import { LOI_MAT_KET_NOI, nenThuLai, type KetQuaGui } from "../../../../lib/tu-luu.ts";

export interface DongGui {
  drug_catalog_id: string;
  don_vi: string;
  dem: string | null;
  dem_luc: string | null;
}

/** Trạng thái màn đọc lúc gửi. `null` = chưa có phiếu / không ghi được. */
export interface ManDem {
  pid: string;
  /** Bản sửa của phiếu đã chốt: máy chủ từ chối bỏ dòng đã đếm (422). */
  laBanSua: boolean;
  /** Các dòng màn đang cho đếm (khoá, thuốc, đơn vị). */
  hang: { khoa: string; thuoc: string; dv: string }[];
  nhap: Record<string, string>;
  gioGo: Record<string, string>;
}

/**
 * Dòng gửi lưu. Ô từng có trong nháp (đã gõ, hoặc nạp từ phiếu) mà nay TRỐNG →
 * gửi `dem: null` = bỏ dòng. Không dựa vào "phiếu đã có dòng chưa": xoá ô ngay sau
 * khi gõ, lúc lần lưu đầu còn đang bay, thì phiếu trong tay chưa có dòng ấy và bản
 * cũ chỉ lặng lẽ bỏ qua — máy chủ giữ số, ô thì trống (soát 20/11).
 * `boTrong` (tự lưu ở bản sửa): không gửi ô trống, để một ô đang xoá-gõ-lại không
 * làm cả lô bị 422.
 */
export function dongCanGui(m: ManDem, boTrong: boolean): DongGui[] {
  return m.hang
    .filter((d) => {
      const co = (m.nhap[d.khoa] ?? "").trim() !== "";
      return co || (!boTrong && d.khoa in m.nhap);
    })
    .map((d) => ({
      drug_catalog_id: d.thuoc,
      don_vi: d.dv,
      dem: (m.nhap[d.khoa] ?? "").trim() || null,
      dem_luc: m.gioGo[d.khoa] ?? null,
    }));
}

export interface PhanHoi {
  status: number;
  data: unknown;
}

/** Hàm gửi cho hàng đợi: đọc `doc()` NGAY LÚC GỬI. 409 (phiếu đã chốt / đổi ở
 *  máy khác) → `tuChoi` để màn bỏ phần chưa lưu và nạp lại, không hỏi "Rời trang?"
 *  mãi. */
export function taoGuiDem({
  doc,
  laThuCong,
  post,
  daLuu,
  tuChoi,
}: {
  doc: () => ManDem | null;
  laThuCong: () => boolean;
  post: (pid: string, dong: DongGui[], keepalive: boolean) => Promise<PhanHoi | null>;
  daLuu: (pid: string, phieu: unknown) => void;
  tuChoi: (pid: string) => void;
}): (keepalive: boolean) => Promise<KetQuaGui> {
  return async (keepalive) => {
    const m = doc();
    if (!m) return { ok: true };
    const dong = dongCanGui(m, m.laBanSua && !laThuCong());
    if (dong.length === 0) return { ok: true };
    const r = await post(m.pid, dong, keepalive);
    if (!r) return { ok: false, loi: LOI_MAT_KET_NOI, thuLai: true };
    if (r.status >= 400) {
      const d = r.data as { message?: string; detail?: unknown } | null;
      const cau = d?.message ?? (typeof d?.detail === "string" ? d.detail : null);
      if (r.status === 409) tuChoi(m.pid);
      return { ok: false, loi: cau ?? "Không lưu được số đếm.", thuLai: nenThuLai(r.status) };
    }
    daLuu(m.pid, r.data);
    return { ok: true };
  };
}

export interface HangLuu {
  danhDau: () => void;
  luuNgay: () => Promise<boolean>;
}

/** "Lưu nháp" / trước "Chốt": đi CHUNG hàng đợi (không POST riêng), đánh dấu để
 *  chắc chắn gửi một lượt kể cả khi chưa gõ gì sau lần nạp. */
export async function luuTay(q: HangLuu, datThuCong: (b: boolean) => void): Promise<boolean> {
  datThuCong(true);
  try {
    q.danhDau();
    return await q.luuNgay();
  } finally {
    datThuCong(false);
  }
}

/** Đổi ca / ngày / mở phiếu khác / dùng số ca trước: XẢ phần chưa lưu của phiếu
 *  đang mở TRƯỚC, rồi mới đổi — không để bản chưa gửi bị thay bằng phiếu mới. */
export async function doiPhieu(q: HangLuu, lam: () => void | Promise<void>): Promise<void> {
  await q.luuNgay();
  await lam();
}
