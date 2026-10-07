// Lệnh HOÀN TÁC của máy chủ cho nút `NutHoanTac` / `ThongBaoHoanTac`
// (Tuyền 01/10/2026: "không được để bất kể cái gì khoá hẳn").
//
// Chỉ là ống dẫn: hoàn tác được không, cần hỏi xác nhận không, đưa mọi bảng về
// đâu — máy chủ quyết (`hoan_tac_service.py`). Tệp này không chứa luật nào.

import type { DuLieuHoanTac, KetQuaHoanTac } from "@/components/ui/NutHoanTac";

import { guiThaoTac } from "./api";

/** Lệnh hoàn tác → mã của nó (đúng loại mã mà proxy `/api/luot-kham` đòi). */
export type LenhHoanTac =
  /** id = PHIÊN KHÁM: hoàn tác Khám xong / Hoàn tất / Xong tư vấn. */
  | "mo-lai-kham"
  /** id = CHỈ ĐỊNH: bỏ chỉ định (đã thu → tiền thừa ở quầy). */
  | "huy-chi-dinh"
  /** id = CHỈ ĐỊNH: hoàn tác "Xong" của dịch vụ. */
  | "hoan-tac-xong-v1"
  /** id = LƯỢT: hoàn tác check-out / về giữa chừng. */
  | "mo-lai-luot"
  /** id = CHỈ ĐỊNH: huỷ xếp phòng (chưa bắt đầu) — chỉ định về "chưa xếp phòng". */
  | "huy-xep-phong-v1"
  /** id = CHỈ ĐỊNH: thu hồi kết quả ĐÃ DUYỆT về nháp. */
  | "thu-hoi-ket-qua"
  /** id = LƯỢT (+ room_id, chi_dinh_ids): hoàn tác Nhận — các chỉ định vừa nhận về "Sắp đến". */
  | "hoan-tac-nhan";

export function lenhHoanTac(
  lenh: LenhHoanTac,
  id: string,
  /** Trường riêng của lệnh gốc (vd `expected_routing_revision` khi huỷ xếp phòng). */
  them: Record<string, unknown> = {},
): (duLieu: DuLieuHoanTac) => Promise<KetQuaHoanTac> {
  return async (duLieu) => {
    const kq = await guiThaoTac(lenh, id, { ...them, ...duLieu });
    if (kq.ok) return { ok: true };
    return { ok: false, loi: kq.loi, ...(kq.chiTiet ? { chiTiet: kq.chiTiet } : {}) };
  };
}
