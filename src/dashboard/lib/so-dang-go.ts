// Số lượng quầy đang gõ ở ô "Số lượng" của `ChinhDonQuay` — sống NGOÀI cây React,
// tách theo lượt (cùng lý do với `lib/nhap-lay-them`).
//
// VÌ SAO (prod 27/11/2026: sửa số mà tổng tiền không tính lại). Số đang gõ từng là
// state của khung: khung gắn lại (prod 16/11: 30 lần / 25′) là mất, và mỗi lần lưu
// xong một dòng khung xoá trắng số đang gõ ở MỌI dòng → dòng sau rời ô thấy trống,
// không gửi gì. Ở đây: gắn lại vẫn còn; lưu xong chỉ bỏ nháp của đúng dòng vừa lưu,
// và chỉ khi nó vẫn là số đã gửi (quầy gõ tiếp thì giữ).
//
// Không lưu xuống đĩa: chỉ cần sống qua lần gắn lại trong tab, không qua F5.

export type SoDangGo = Readonly<Record<string, string>>;

/** Lượt chưa gõ gì — CÙNG một tham chiếu mỗi lần đọc (useSyncExternalStore đòi). */
export const SO_RONG: SoDangGo = Object.freeze({});

export interface KhoSoDangGo {
  doc(visitId: string): SoDangGo;
  ghi(visitId: string, dongId: string, chu: string): void;
  /** Lưu xong (hoặc bị từ chối) số `chu` — bỏ nháp dòng đó nếu vẫn đúng `chu`. */
  boNeuBang(visitId: string, dongId: string, chu: string): void;
  nghe(fn: () => void): () => void;
}

export function taoKhoSoDangGo(): KhoSoDangGo {
  const kho = new Map<string, SoDangGo>();
  const nguoiNghe = new Set<() => void>();
  const bao = () => nguoiNghe.forEach((fn) => fn());
  return {
    doc: (visitId) => kho.get(visitId) ?? SO_RONG,
    ghi(visitId, dongId, chu) {
      kho.set(visitId, { ...(kho.get(visitId) ?? SO_RONG), [dongId]: chu });
      bao();
    },
    boNeuBang(visitId, dongId, chu) {
      const cu = kho.get(visitId);
      if (!cu || cu[dongId] !== chu) return;
      const con = { ...cu };
      delete con[dongId];
      if (Object.keys(con).length === 0) kho.delete(visitId);
      else kho.set(visitId, con);
      bao();
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
export const khoSoDangGo = taoKhoSoDangGo();

/** Ô số lượng có cần gửi không. `null` = không (ô trống, số không đổi so với
 *  `dangCo` của máy chủ). Gõ chữ ("2 hộp") thì trả câu báo thay vì gửi rỗng —
 *  máy chủ vẫn là nơi quyết số hợp lệ (> 0, ≥ số đã giao…). */
export function soCanGui(
  chu: string | undefined,
  dangCo: string | null,
): { so: number } | { loi: string } | null {
  const v = (chu ?? "").trim().replace(",", ".");
  if (!v) return null;
  const so = Number(v);
  if (!Number.isFinite(so)) {
    return { loi: "Ô số lượng chỉ gõ số (vd 2 hoặc 1,5) — đơn vị chọn ở ô bên cạnh." };
  }
  if (dangCo !== null && so === Number(dangCo.replace(",", "."))) return null;
  return { so };
}
