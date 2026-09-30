"use client";

// Ô tick "Làm trước – thu sau" của MỘT lượt (Tuyền 30/09/2026 tối).
//
// Dây nối `thu_truoc_khi_lam` (mặc định BẬT): chưa thu thì chỉ lượt được tick
// mới xếp phòng / bắt đầu làm. Dùng CHUNG ở Bàn khám (khối Chỉ định & kết quả)
// và quầy thu dịch vụ (`thu-ngan/HoaDonMot`) — một bản, không hai bản lệch.
//
// Màn KHÔNG tự quyết: hiện hay không, tick / bỏ tick được hay không, câu vì sao
// không bỏ được — đều là cờ máy chủ trả (`GET/POST .../lam-truoc-thu-sau`).
// Bật = máy chủ chốt luôn chỉ định còn chờ khách quyết (quầy gửi kèm lựa chọn
// đang tick trên màn qua `layChon`).

import { useCallback, useEffect, useState } from "react";

import NutInPhieu from "@/components/ui/NutInPhieu";

import { useNgheBang } from "../dung-nghe-bang";

export interface LamTruoc {
  cong_tac_bat: boolean;
  lam_truoc_thu_sau: boolean;
  hien: boolean;
  tick_duoc: boolean;
  bo_tick_duoc: boolean;
  ly_do_khong_bo: string | null;
  chot_thu_sau_duoc: boolean;
  bat_boi: string | null;
  bat_luc: string | null;
}

export interface LuaChonGui {
  order_ids_seen: string[];
  selected_order_ids: string[];
  expected_selection_revision: number;
}

function gio(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ""
    : d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh" });
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
      const d = (await r.json().catch(() => null)) as (LamTruoc & { message?: string; error?: string }) | null;
      if (!r.ok) {
        setLoi(d?.message ?? d?.error ?? "Không ghi được Làm trước – thu sau.");
      } else if (d) {
        if (tuDoc) setDocDuoc(d);
        else setVuaGhi({ goc: trangThai, tt: d });
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
      {tt.lam_truoc_thu_sau && tt.bat_boi ? (
        <span className="text-meta text-ink-muted">
          Bật bởi {tt.bat_boi}
          {tt.bat_luc ? ` lúc ${gio(tt.bat_luc)}` : ""}
        </span>
      ) : !tt.lam_truoc_thu_sau ? (
        <span className="text-meta text-ink-muted">Không tick: thu tiền xong mới xếp phòng, bắt đầu làm.</span>
      ) : null}
      {/* Đã tick: in giấy đi phòng cho khách cầm (chưa thu tiền — 30/09/2026). */}
      {tt.lam_truoc_thu_sau ? (
        <NutInPhieu href={`/print/phieu-thu/${visitId}?loai=huong_dan`} size="sm">
          In phiếu hướng dẫn phòng
        </NutInPhieu>
      ) : null}
      {tt.ly_do_khong_bo ? <span className="w-full text-meta text-ink-muted">{tt.ly_do_khong_bo}</span> : null}
      {loi ? (
        <p role="alert" className="w-full text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
