"use client";

// Ô CHỮ TƯ VẤN TỰ LƯU — nội dung tư vấn của MỘT phiên tư vấn.
//
// Một ô, hai chỗ dùng (bản giao diện mẫu, Tuyền duyệt 27/09/2026):
//   · Bàn tư vấn — ô to "✎ Bác sĩ tư vấn · tự lưu" (`ban-kham/ONhapTuVan`).
//   · Khối 1 phiếu bác sĩ chính — "Bác sĩ tư vấn ghi … bác sĩ chính sửa tiếp
//     được" (`KhoiDauPhieu.KhoiTuVan`, mục 12).
// Cùng lệnh `noi-dung-tu-van` → máy chủ quyết AI ghi được (khối Tư vấn hoặc quyền
// ghi phiếu khám) và giữ mọi bản đã lưu (lịch sử). Màn không if theo vai.
//
// Tự lưu: dừng gõ ~1 giây hoặc rời ô. Trạng thái lưu báo lên qua `onTrangThai`
// để nút "Xong tư vấn" đợi chữ lưu xong.

import { useCallback, useEffect, useRef, useState } from "react";

import type { ClinicalCompletionGate } from "@/lib/clinical-completion";
import { INPUT } from "../../form-ui";
import { guiThaoTac } from "../api";

type TrangThai = "da-luu" | "chua-luu" | "dang-luu" | "loi";

const CHO_LUU_MS = 1000;

function gio(d: Date): string {
  return d.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function OTuVanTuLuu({
  consultationId,
  banDau,
  choGhi,
  onTrangThai,
  to = false,
  nhan,
  placeholder = "Lý do đến khám, tiền sử, triệu chứng, đã tư vấn gì…",
}: {
  /** Phiên TƯ VẤN (consultation kind TU_VAN). */
  consultationId: string;
  /** Bản mới nhất máy chủ đang giữ. */
  banDau: string;
  /** Người đang mở có chỗ ghi — máy chủ vẫn kiểm lại quyền. */
  choGhi: boolean;
  onTrangThai?: (g: ClinicalCompletionGate) => void;
  /** Ô to của bàn tư vấn (bản mẫu `.ta.big` 240px); nhỏ = 160px. */
  to?: boolean;
  /** aria-label của ô. */
  nhan: string;
  placeholder?: string;
}) {
  const [chu, setChu] = useState(banDau);
  const [tt, setTt] = useState<TrangThai>("da-luu");
  const [luuLuc, setLuuLuc] = useState<Date | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const daLuu = useRef(banDau);
  const hen = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!onTrangThai) return;
    const ok = tt === "da-luu";
    onTrangThai({
      ok,
      code: ok ? null : "UNSAVED_CHANGES",
      message: ok ? null : "Nội dung tư vấn chưa lưu xong — đợi chữ “Đã lưu” rồi bấm lại.",
    });
  }, [tt, onTrangThai]);

  useEffect(
    () => () => {
      if (hen.current) clearTimeout(hen.current);
    },
    [],
  );

  const luu = useCallback(
    async (noiDung: string) => {
      if (noiDung === daLuu.current) {
        setTt("da-luu");
        return;
      }
      setTt("dang-luu");
      setLoi(null);
      const kq = await guiThaoTac("noi-dung-tu-van", consultationId, { noi_dung: noiDung });
      if (!kq.ok) {
        setTt("loi");
        setLoi(kq.loi);
        return;
      }
      daLuu.current = noiDung;
      setLuuLuc(new Date());
      setTt("da-luu");
    },
    [consultationId],
  );

  const chuTrangThai =
    tt === "dang-luu"
      ? "Đang lưu…"
      : tt === "chua-luu"
        ? "Chưa lưu"
        : tt === "da-luu"
          ? luuLuc
            ? `Đã lưu ${gio(luuLuc)}`
            : "Tự lưu khi gõ"
          : null;

  return (
    <div className="space-y-2">
      <textarea
        value={chu}
        aria-label={nhan}
        disabled={!choGhi}
        onChange={(e) => {
          const v = e.target.value;
          setChu(v);
          setTt("chua-luu");
          if (hen.current) clearTimeout(hen.current);
          hen.current = setTimeout(() => void luu(v), CHO_LUU_MS);
        }}
        onBlur={() => {
          if (hen.current) clearTimeout(hen.current);
          void luu(chu);
        }}
        placeholder={placeholder}
        className={`${INPUT} resize-y leading-relaxed ${to ? "min-h-60 sm:min-h-60" : "min-h-40 sm:min-h-40"}`}
      />
      {chuTrangThai ? (
        <p className="text-meta text-ink-muted" aria-live="polite">
          {chuTrangThai}
        </p>
      ) : null}
      {loi ? (
        <p role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}
