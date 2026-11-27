// Ô "Số lượng" của khung chỉnh đơn quầy (`ChinhDonQuay`) TỰ LƯU (27/11/2026).
//
// Prod 27/11: sửa số mà tổng tiền không tính lại. Máy chủ tính đúng mọi số tới nơi —
// gốc là số không được gửi: (1) chỉ gửi khi rời ô, gõ xong vuốt xuống xem Tổng là chưa
// đi đâu; (2) lưu xong một dòng, nạp lại xoá trắng số đang gõ ở dòng khác; (3) số nằm
// trong state, khung gắn lại là mất. Ở đây: ngừng gõ CHO_GO_MS / Enter / rời ô là gửi;
// số đang gõ ở kho theo lượt (`lib/so-dang-go`); mỗi dòng một lệnh một lúc, gõ tiếp
// trong lúc đang lưu thì lưu xong gửi số mới. Luật số hợp lệ ở máy chủ.

import { useCallback, useEffect, useRef, useSyncExternalStore } from "react";

import { khoSoDangGo, SO_RONG, soCanGui } from "@/lib/so-dang-go";

/** Ngừng gõ bấy lâu thì ô Số lượng tự lưu. */
export const CHO_GO_MS = 800;

interface DongSo {
  id: string;
  ten: string;
  so_mua: string | null;
  so_ke: string | null;
  mua: boolean;
  da_chot: boolean;
}

export function useSoLuongTuLuu<D extends DongSo>({
  visitId,
  dong,
  luu,
  baoLoi,
}: {
  visitId: string;
  dong: D[] | null;
  /** Gửi số mới của dòng; xong khi đơn (và hoá đơn của màn cha) đã nạp lại. */
  luu: (d: D, so: number) => Promise<void>;
  baoLoi: (cau: string) => void;
}) {
  const soNhap = useSyncExternalStore(
    khoSoDangGo.nghe,
    () => khoSoDangGo.doc(visitId),
    () => SO_RONG,
  );
  // Hẹn giờ chạy trễ — đọc bản đơn / hàm gửi MỚI NHẤT qua ref, không qua closure cũ.
  const dongMoi = useRef(dong);
  const goi = useRef({ luu, baoLoi });
  useEffect(() => {
    dongMoi.current = dong;
    goi.current = { luu, baoLoi };
  });
  const henGio = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const dangGui = useRef(new Set<string>());
  const guiLai = useRef(new Set<string>());

  const doiSo = useCallback(
    async function chay(id: string): Promise<void> {
      clearTimeout(henGio.current.get(id));
      henGio.current.delete(id);
      if (dangGui.current.has(id)) {
        guiLai.current.add(id);
        return;
      }
      const d = dongMoi.current?.find((x) => x.id === id);
      const v = khoSoDangGo.doc(visitId)[id];
      if (!d || v === undefined) return;
      const kq = soCanGui(v, d.so_mua ?? d.so_ke);
      // Hẹn giờ nổ sau khi dòng vừa bỏ tick / đã chốt: không gửi, bỏ nháp.
      if (kq === null || !d.mua || d.da_chot) {
        // Số không đổi thì không gọi máy chủ (khỏi ghi vết "10 → 10").
        khoSoDangGo.boNeuBang(visitId, id, v);
        return;
      }
      if ("loi" in kq) {
        goi.current.baoLoi(kq.loi);
        return;
      }
      dangGui.current.add(id);
      try {
        await goi.current.luu(d, kq.so);
      } finally {
        // Đơn đã nạp lại: ô hiện số máy chủ. Gõ tiếp trong lúc lưu thì nháp ≠ v, giữ.
        khoSoDangGo.boNeuBang(visitId, id, v);
        dangGui.current.delete(id);
      }
      if (guiLai.current.delete(id)) void chay(id);
    },
    [visitId],
  );

  const go = (id: string, chu: string) => {
    khoSoDangGo.ghi(visitId, id, chu);
    clearTimeout(henGio.current.get(id));
    henGio.current.set(id, setTimeout(() => void doiSo(id), CHO_GO_MS));
  };

  // Gỡ hẹn khi khung rời màn; khung gắn lại mà kho còn số chưa gửi thì hẹn gửi lại.
  useEffect(() => {
    const hen = henGio.current;
    return () => hen.forEach((t) => clearTimeout(t));
  }, []);
  const daHenLai = useRef(false);
  useEffect(() => {
    if (dong === null || daHenLai.current) return;
    daHenLai.current = true;
    for (const id of Object.keys(khoSoDangGo.doc(visitId))) {
      henGio.current.set(id, setTimeout(() => void doiSo(id), CHO_GO_MS));
    }
  }, [dong, visitId, doiSo]);

  return { soNhap, go, doiSo };
}
