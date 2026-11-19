// Bản nháp "Lấy thêm thuốc" của quầy — sống NGOÀI cây React, tách theo lượt.
//
// VÌ SAO (prod 16/11/2026). Nháp (thuốc vừa chọn + số lượng + cách dùng) từng là
// state của `ChinhDonQuay`. Log Caddy 16:05–16:30: một máy quầy làm mới /pharmacy
// 64 lần và khung này bị GẮN LẠI 30 lần — mỗi lần mất sạch thứ đang gõ; ba lượt bán
// lẻ mở mà 0 dòng thuốc, 13 lượt "Thêm" bị 422 vì số lượng tới máy chủ rỗng. Giữ
// nháp ở đây thì khung gắn lại bao nhiêu lần (ở cấp nào) nháp và lời từ chối vẫn còn.
//
// VÌ SAO KHÔNG DÙNG `lib/luu-nhap` (localStorage). Nó khoá theo `staffId` vì máy
// quầy dùng chung và nháp nằm trên đĩa — khung này không có `staffId`. Ở đây chỉ
// cần sống qua lần gắn lại, không cần qua F5: bộ nhớ của tab là đủ, và thuốc của
// khách không nằm lại trên đĩa máy trạm.
//
// Đọc bằng `useSyncExternalStore`: hai khung cùng một lượt thấy CÙNG một nháp.

import type { DongThuoc } from "./phieu-kham";

export interface NhapLayThem {
  dong: DongThuoc[];
  /** Lời từ chối của lần lưu gần nhất (vd 422 thiếu số lượng) — hiện cạnh nút. */
  loi: string | null;
}

/** Lượt chưa có nháp — CÙNG một tham chiếu mỗi lần đọc (useSyncExternalStore đòi). */
export const NHAP_RONG: NhapLayThem = Object.freeze({ dong: [], loi: null }) as NhapLayThem;

export interface KhoNhapLayThem {
  doc(visitId: string): NhapLayThem;
  ghi(visitId: string, moi: Partial<NhapLayThem>): void;
  /** Lưu xong — bỏ nháp của lượt. */
  bo(visitId: string): void;
  nghe(fn: () => void): () => void;
}

export function taoKhoNhapLayThem(): KhoNhapLayThem {
  const kho = new Map<string, NhapLayThem>();
  const nguoiNghe = new Set<() => void>();
  const bao = () => nguoiNghe.forEach((fn) => fn());
  return {
    doc: (visitId) => kho.get(visitId) ?? NHAP_RONG,
    ghi(visitId, moi) {
      const sau: NhapLayThem = { ...(kho.get(visitId) ?? NHAP_RONG), ...moi };
      if (sau.dong.length === 0 && sau.loi === null) kho.delete(visitId);
      else kho.set(visitId, sau);
      bao();
    },
    bo(visitId) {
      if (kho.delete(visitId)) bao();
    },
    nghe(fn) {
      nguoiNghe.add(fn);
      return () => {
        nguoiNghe.delete(fn);
      };
    },
  };
}

/** Kho dùng chung của tab — mọi `ChinhDonQuay` đọc/ghi qua đây. */
export const khoNhapLayThem = taoKhoNhapLayThem();
