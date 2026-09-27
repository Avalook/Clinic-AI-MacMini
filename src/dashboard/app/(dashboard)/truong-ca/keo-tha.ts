// KÉO KHÁCH SANG PHÒNG CÙNG CHỨC NĂNG (Tuyền 28/09/2026: "cho người dùng nhấn
// vào khách và kéo sang được màn cùng chức năng").
//
// Không có luật mới ở đây: "phòng nào nhận được" và "đổi được không" đọc từ
// ĐÚNG hai nguồn popup đang dùng — `dispatch-read?what=chi-dinh` (chỉ định của
// lượt, cờ đổi phòng, phòng làm được) và `goi-y-phong` (ứng viên đời mới). Thả
// xuống = gọi ĐÚNG lệnh của popup (`xep-phong-v1` / `xep-phong`); máy chủ vẫn
// kiểm quyền, cổng tiền, revision và từ chối bằng câu của nó.

import { docBang, guiThaoTac } from "../_lam-viec/api";
import { chuyenDuoc, khoaGuiLai, type ChiDinh } from "./ChiDinhCuaBacSi";
import type { DispatchPatient } from "./types";

export interface DichDen {
  visitId: string;
  tenDichVu: string;
  /** Mã phòng (uuid) nhận được chỉ định này — trừ phòng đang đứng. */
  phong: Set<string>;
  gui: (roomId: string) => Promise<{ ok: true } | { ok: false; loi: string }>;
}

export async function timDichDen(
  p: DispatchPatient,
): Promise<DichDen | { loi: string }> {
  const r = await fetch(`/api/dispatch-read?what=chi-dinh&visit_id=${p.visit_id}`, {
    cache: "no-store",
  }).catch(() => null);
  const j = (await r?.json().catch(() => null)) as { ok?: boolean; items?: ChiDinh[] } | null;
  if (!j || j.ok === false || !Array.isArray(j.items)) {
    return { loi: "Không đọc được chỉ định của khách." };
  }
  // Chỉ định khách đang chờ Ở CHÍNH PHÒNG NÀY — thứ duy nhất "kéo đi" có nghĩa.
  const x = j.items.find((c) => !c.xong && !c.doi_tac && c.room_id === p.room_id);
  if (!x) return { loi: "Khách không có chỉ định nào đổi phòng được ở phòng này." };

  if (x.selection_status !== null) {
    if (!x.doi_phong_duoc) return { loi: `${x.service_name}: lúc này không đổi phòng được.` };
    const g = await docBang<{
      recommendation_ref: string;
      candidates: { room_id: string }[];
    }>("goi-y-phong", { chi_dinh: x.id });
    if (!g.ok) return { loi: g.loi };
    return {
      visitId: p.visit_id,
      tenDichVu: x.service_name,
      phong: new Set(g.data.candidates.map((c) => c.room_id).filter((id) => id !== x.room_id)),
      gui: async (roomId) => {
        const kq = await guiThaoTac("xep-phong-v1", x.id, {
          room_id: roomId,
          expected_routing_revision: x.routing_revision,
          reason_code: "LOAD_BALANCE",
          recommendation_ref: g.data.recommendation_ref,
          nguon: "truong_ca",
        });
        return kq.ok ? { ok: true } : { ok: false, loi: kq.loi };
      },
    };
  }

  if (!chuyenDuoc(x)) return { loi: `${x.service_name}: phòng đã gọi hoặc đang làm.` };
  return {
    visitId: p.visit_id,
    tenDichVu: x.service_name,
    phong: new Set(x.phong_lam_duoc.map((c) => c.id).filter((id) => id !== x.room_id)),
    gui: async (roomId) => {
      try {
        const res = await fetch("/api/luot-kham", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Idempotency-Key": khoaGuiLai() },
          body: JSON.stringify({
            thao_tac: "xep-phong",
            id: x.id,
            du_lieu: { room_id: roomId, expected_version: x.version },
          }),
        });
        if (res.ok) return { ok: true };
        const d = (await res.json().catch(() => null)) as { message?: string; error?: string } | null;
        return { ok: false, loi: d?.message ?? d?.error ?? "Không chuyển được." };
      } catch {
        return { ok: false, loi: "Mất kết nối — CHƯA chuyển được." };
      }
    },
  };
}
