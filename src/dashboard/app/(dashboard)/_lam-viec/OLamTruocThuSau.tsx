"use client";

// Ô tick "Làm trước – thu sau" của MỘT lượt (Tuyền 30/09/2026 tối).
//
// Dây nối `thu_truoc_khi_lam` (mặc định BẬT): chưa thu thì chỉ lượt được tick
// mới xếp phòng / bắt đầu làm. Dùng CHUNG ở Bàn khám (khối Chỉ định & kết quả)
// và quầy thu dịch vụ (`thu-ngan/HoaDonMot`) — một bản, không hai bản lệch.
//
// Màn KHÔNG tự quyết: hiện hay không, tick / bỏ tick được hay không, câu vì sao
// không bỏ được, câu "bỏ tick thì chuyện gì xảy ra" — đều là cờ máy chủ trả
// (`GET/POST .../lam-truoc-thu-sau`). Tick lần nữa = HOÀN TÁC (01/10/2026):
// không khoá cứng, kể cả khi đã có dịch vụ bắt đầu làm.
// Bật = máy chủ chốt luôn chỉ định còn chờ khách quyết (quầy gửi kèm lựa chọn
// đang tick trên màn qua `layChon`).

import { useCallback, useEffect, useState } from "react";

import Chip from "@/components/ui/Chip";
import NutInPhieu from "@/components/ui/NutInPhieu";

import { useNgheBang } from "../dung-nghe-bang";

export interface LamTruoc {
  cong_tac_bat: boolean;
  lam_truoc_thu_sau: boolean;
  hien: boolean;
  tick_duoc: boolean;
  bo_tick_duoc: boolean;
  ly_do_khong_bo: string | null;
  /** Bỏ tick thì chuyện gì xảy ra — máy chủ viết, chỉ khi lượt đang tick. */
  luu_y_bo?: string | null;
  chot_thu_sau_duoc: boolean;
  bat_boi: string | null;
  bat_luc: string | null;
}

export interface LuaChonGui {
  order_ids_seen: string[];
  selected_order_ids: string[];
  expected_selection_revision: number;
}

export function gio(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
}

/** Nhãn trạng thái "Làm trước – thu sau · <ai tick> · <giờ>" (quầy giữ khách,
 *  còn nợ, còn thu được). Không tick → null. */
export function nhanLamTruocThuSau(lt: Pick<LamTruoc, "lam_truoc_thu_sau" | "bat_boi" | "bat_luc"> | null | undefined): string | null {
  if (!lt?.lam_truoc_thu_sau) return null;
  return ["Làm trước – thu sau", lt.bat_boi, gio(lt.bat_luc)].filter(Boolean).join(" · ");
}

export default function OLamTruocThuSau({
  visitId,
  trangThai,
  layChon,
  onDoi,
}: {
  visitId: string;
  /** Cờ máy chủ đã trả sẵn (quầy thu). Không có thì ô tự đọc. */
  trangThai?: LamTruoc | null;
  /** Quầy: lựa chọn đang tick trên màn — gửi kèm khi bật để chốt đúng thế. */
  layChon?: () => LuaChonGui | undefined;
  onDoi?: () => void;
}) {
  // Tự đọc khi cha không trả sẵn cờ (Bàn khám); cha trả sẵn thì dùng cờ của
  // cha, riêng kết quả vừa ghi giữ tới khi cha tải lại bảng.
  const [docDuoc, setDocDuoc] = useState<LamTruoc | null>(null);
  const [vuaGhi, setVuaGhi] = useState<{ goc: LamTruoc | null | undefined; tt: LamTruoc } | null>(null);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [ghiChu, setGhiChu] = useState<string | null>(null);
  const tuDoc = trangThai === undefined;

  const doc = useCallback(async (): Promise<LamTruoc | null> => {
    try {
      const r = await fetch(`/api/luot-kham?xem=lam-truoc-thu-sau&luot=${visitId}`, { cache: "no-store" });
      return r.ok ? ((await r.json()) as LamTruoc) : null;
    } catch {
      return null; // mất kết nối: giữ nguyên ô cũ
    }
  }, [visitId]);

  useEffect(() => {
    if (!tuDoc) return;
    let huy = false;
    void doc().then((d) => {
      if (!huy && d) setDocDuoc(d);
    });
    return () => {
      huy = true;
    };
  }, [doc, tuDoc]);
  useNgheBang(["visit"], () => {
    if (tuDoc) void doc().then((d) => d && setDocDuoc(d));
  });

  const tt = tuDoc ? docDuoc : vuaGhi && vuaGhi.goc === trangThai ? vuaGhi.tt : trangThai;

  if (!tt || !tt.hien) return null;

  const bat = !tt.lam_truoc_thu_sau;
  const khoa = dang || (bat ? !tt.tick_duoc : !tt.bo_tick_duoc);

  const doi = async () => {
    setDang(true);
    setLoi(null);
    setGhiChu(null);
    try {
      const chon = bat ? layChon?.() : undefined;
      const r = await fetch("/api/luot-kham", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          thao_tac: "lam-truoc-thu-sau",
          id: visitId,
          du_lieu: chon ? { bat, chon } : { bat },
        }),
      });
      const d = (await r.json().catch(() => null)) as
        | (LamTruoc & { message?: string; error?: string; ghi_chu?: string })
        | null;
      if (!r.ok) {
        setLoi(d?.message ?? d?.error ?? "Không ghi được Làm trước – thu sau.");
      } else if (d) {
        if (tuDoc) setDocDuoc(d);
        else setVuaGhi({ goc: trangThai, tt: d });
        setGhiChu(d.ghi_chu ?? null);
      }
      onDoi?.();
    } catch {
      setLoi("Mất kết nối — CHƯA ghi được Làm trước – thu sau.");
    } finally {
      setDang(false);
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <label className="flex min-h-8 items-center gap-2 text-body font-medium text-ink">
        <input
          type="checkbox"
          checked={tt.lam_truoc_thu_sau}
          disabled={khoa}
          onChange={() => void doi()}
          className="size-4 accent-brand-600"
        />
        Làm trước – thu sau
      </label>
      {!tt.lam_truoc_thu_sau ? (
        <span className="text-meta text-ink-muted">Không tick: thu tiền xong mới xếp phòng, bắt đầu làm.</span>
      ) : tuDoc ? (
        // Quầy thu đã có nhãn này ở đầu khối khách — chỉ Bàn khám cần vẽ ở đây.
        <Chip tone="info">{nhanLamTruocThuSau(tt)}</Chip>
      ) : null}
      {/* Đã tick: in giấy đi phòng cho khách cầm (chưa thu tiền — 30/09/2026).
          Chỉ ở Bàn khám (ô tự đọc) — quầy thu đã có nút này ở khối "Phòng làm
          dịch vụ", không hiện hai nút cùng đích. */}
      {tt.lam_truoc_thu_sau && tuDoc ? (
        <NutInPhieu href={`/print/phieu-thu/${visitId}?loai=huong_dan`} size="sm">
          In phiếu hướng dẫn phòng
        </NutInPhieu>
      ) : null}
      {tt.ly_do_khong_bo ? <span className="w-full text-meta text-ink-muted">{tt.ly_do_khong_bo}</span> : null}
      {tt.lam_truoc_thu_sau && tt.luu_y_bo ? (
        <span className="w-full text-meta text-ink-muted">{tt.luu_y_bo}</span>
      ) : null}
      {ghiChu ? (
        <p role="status" className="w-full text-meta text-ink-soft">
          {ghiChu}
        </p>
      ) : null}
      {loi ? (
        <p role="alert" className="w-full text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
