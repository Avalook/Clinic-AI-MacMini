"use client";

// Ô chữ TỰ DO của bác sĩ tư vấn (Tuyền 24/09/2026).
//
// "Chỗ bác sĩ tư vấn chỉ cần 1 ô vuông to để điền tự do — không phải dùng form
// của bác sĩ chính, để còn đồng bộ sang 'Dữ liệu mang sang từ phần khám/tư vấn
// ban đầu' của bác sĩ chính." Trước đó bàn tư vấn ghi vào chính phiếu khám v5.
//
// Tự lưu (dừng gõ ~1 giây, hoặc rời ô) → lệnh `noi-dung-tu-van`. Máy chủ giữ
// mọi bản đã lưu; phiếu bác sĩ chính đọc bản mới nhất. Nút "Xong tư vấn" đợi ô
// này lưu xong — báo qua `onTrangThai` giống phiếu khám.

import { useCallback, useEffect, useRef, useState } from "react";

import type { ClinicalCompletionGate } from "@/lib/clinical-completion";
import type { DauPhieu } from "@/lib/phieu-kham";

import { guiThaoTac } from "../_lam-viec/api";

type TrangThai = "dang-tai" | "da-luu" | "chua-luu" | "dang-luu" | "loi";

export default function ONhapTuVan({
  visitId,
  consultationId,
  choGhi,
  onTrangThai,
}: {
  visitId: string;
  /** Phiên TƯ VẤN (ref_id của dòng hàng chờ tư vấn). */
  consultationId: string;
  choGhi: boolean;
  onTrangThai: (g: ClinicalCompletionGate) => void;
}) {
  const [chu, setChu] = useState("");
  const [tt, setTt] = useState<TrangThai>("dang-tai");
  const [loi, setLoi] = useState<string | null>(null);
  const daLuu = useRef("");
  const hen = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Bản đang có trên máy chủ (bản mới nhất của đúng phiên tư vấn này).
  useEffect(() => {
    let bo = false;
    fetch(`/api/phieu-kham?visit_id=${visitId}&xem=dau-phieu`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: DauPhieu | null) => {
        if (bo) return;
        const cua = (d?.tu_van ?? []).filter((g) => g.consultation_id === consultationId);
        const hien = cua.length ? cua[cua.length - 1]!.noi_dung : "";
        daLuu.current = hien;
        setChu(hien);
        setTt(d ? "da-luu" : "loi");
        if (!d) setLoi("Không đọc được nội dung đã ghi — tải lại trang.");
      })
      .catch(() => {
        if (!bo) {
          setTt("loi");
          setLoi("Mất kết nối — không đọc được nội dung đã ghi.");
        }
      });
    return () => {
      bo = true;
    };
  }, [visitId, consultationId]);

  useEffect(() => {
    const ok = tt === "da-luu";
    onTrangThai({
      ok,
      code: ok ? null : tt === "dang-tai" ? "FORM_NOT_READY" : "UNSAVED_CHANGES",
      message: ok
        ? null
        : tt === "dang-tai"
          ? "Đang tải nội dung tư vấn…"
          : "Nội dung tư vấn chưa lưu xong — đợi chữ “Đã lưu” rồi bấm lại.",
    });
  }, [tt, onTrangThai]);

  const luu = useCallback(
    async (noiDung: string) => {
      if (noiDung === daLuu.current) {
        setTt("da-luu");
        return;
      }
      setTt("dang-luu");
      setLoi(null);
      const kq = await guiThaoTac("noi-dung-tu-van", consultationId, {
        noi_dung: noiDung,
      });
      if (!kq.ok) {
        setTt("loi");
        setLoi(kq.loi);
        return;
      }
      daLuu.current = noiDung;
      setTt("da-luu");
    },
    [consultationId],
  );

  useEffect(
    () => () => {
      if (hen.current) clearTimeout(hen.current);
    },
    [],
  );

  return (
    <div className="space-y-2">
      <label className="block">
        <span className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
          Nội dung tư vấn — bác sĩ chính thấy ở mục “Dữ liệu mang sang”
        </span>
        <textarea
          value={chu}
          disabled={!choGhi || tt === "dang-tai"}
          onChange={(e) => {
            const v = e.target.value;
            setChu(v);
            setTt("chua-luu");
            if (hen.current) clearTimeout(hen.current);
            hen.current = setTimeout(() => void luu(v), 1000);
          }}
          onBlur={() => {
            if (hen.current) clearTimeout(hen.current);
            void luu(chu);
          }}
          rows={14}
          placeholder="Lý do đến khám, tiền sử, triệu chứng, đã tư vấn gì…"
          className="mt-1 block w-full rounded-control border border-line bg-surface p-3 text-body text-ink focus:border-brand-500 focus:outline-none disabled:bg-surface-sunken"
        />
      </label>
      <p className="text-meta text-ink-muted" aria-live="polite">
        {tt === "dang-tai"
          ? "Đang tải…"
          : tt === "dang-luu"
            ? "Đang lưu…"
            : tt === "chua-luu"
              ? "Chưa lưu"
              : tt === "da-luu"
                ? "Đã lưu"
                : null}
      </p>
      {loi ? (
        <p className="rounded-control bg-danger-bg px-3 py-2 text-meta text-danger">{loi}</p>
      ) : null}
    </div>
  );
}
