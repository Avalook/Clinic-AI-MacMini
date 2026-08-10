"use client";

// "Khách này đang có mấy lịch" — và bỏ bớt cho còn một.
//
// QUANG 09/08/2026, sau khi đặt thử ba lần cho Nguyễn Thị Lan: *"nó hiện ra đây
// 3 cái như này, mà không có thao tác gì xử lý rồi… nên chuyển cái 3 việc thành
// cảnh báo, click vào để hiện ra 3 cái lịch đặt, xoá đi các lịch thừa để chỉ
// giữ 1 lịch thôi, chứ không cứ viết đè như này là hỏng hệ thống"*.
//
// CHIP CŨ ĐẾM NHẦM THỨ. Nó đọc `so_viec_mo` của `v_trang_thai_cskh` — số VIỆC
// CSKH đang mở, không phải số LỊCH. Lan đặt 3 lần thì chip hiện "+3 việc", mà
// thật ra là 4 việc trên 3 lịch: hai con số khác nhau tình cờ gần nhau, và
// người đọc kết luận sai. Bảng này đếm đúng cái nó nói: lịch còn sống, còn sắp
// tới, của đúng khách này.
//
// KHÔNG TỰ CHỌN HỘ LỊCH NÀO ĐƯỢC GIỮ. Ba lịch của Lan cách nhau 45 phút và
// không có gì trong dữ liệu nói cái nào là "cái thật" — chỉ người vừa nói
// chuyện với khách mới biết. Máy chọn hộ ở đây là lặng lẽ huỷ đúng cái lịch
// khách muốn giữ.

import { useState } from "react";
import { nhanLoi } from "@/lib/loi-api";
import { X, CalendarX2, AlertTriangle } from "lucide-react";
import { fmtDayTime } from "@/lib/datetime";
import type { LichSapToi } from "./CustomersView";

const NHAN_TRANG_THAI: Record<string, string> = {
  SCHEDULED: "Mới đặt",
  CSKH_CONFIRMED: "CSKH đã xác nhận",
  CONFIRMED: "Đã đặt lịch",
  CHECKED_IN: "Đã check-in",
};

export default function LichTrungCuaKhach({
  tenKhach,
  lich,
  onDong,
  onDaHuy,
}: {
  tenKhach: string;
  lich: LichSapToi[];
  onDong: () => void;
  /** Huỷ xong một lịch — để màn cha tải lại. */
  onDaHuy: () => void;
}) {
  const [dangHuy, setDangHuy] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [daHuy, setDaHuy] = useState<Set<string>>(new Set());

  const conLai = lich.filter((l) => !daHuy.has(l.id));

  async function huy(l: LichSapToi) {
    setDangHuy(l.id);
    setLoi(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: l.id,
        action: "cancel",
        // Mã riêng chứ không mượn ba mã "khách báo không đến": khách không huỷ
        // gì cả. Xem ghi chú ở lib/ly-do-huy.ts.
        ly_do_huy_ma: "DAT_TRUNG",
        cancellation_reason: `Đặt trùng — bỏ lịch ${fmtDayTime(l.slot_start)}, giữ lại lịch khác của khách.`,
      }),
    });
    setDangHuy(null);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as {
        error?: string;
        message?: string;
      } | null;
      setLoi(nhanLoi(d, `Không huỷ được (lỗi ${res.status}).`));
      return;
    }
    setDaHuy((truoc) => new Set(truoc).add(l.id));
    onDaHuy();
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Lịch sắp tới của ${tenKhach}`}
      className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4"
      onClick={onDong}
    >
      <div
        className="w-full max-w-lg space-y-3 rounded-2xl border border-line bg-surface p-4 shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3 border-b border-line pb-3">
          <div>
            <h2 className="text-sm font-semibold text-ink">
              {tenKhach} đang có {conLai.length} lịch sắp tới
            </h2>
            <p className="mt-0.5 text-[11px] text-ink-muted">
              Giữ lại lịch khách thật sự muốn đến, bỏ những lịch còn lại.
            </p>
          </div>
          <button
            type="button"
            onClick={onDong}
            aria-label="Đóng"
            className="shrink-0 rounded-lg p-1 text-ink-muted hover:bg-surface-muted"
          >
            <X className="size-4" />
          </button>
        </div>

        {conLai.length === 1 && (
          <p className="rounded-xl bg-success-bg px-3 py-2 text-xs text-success">
            Còn đúng một lịch — không còn trùng nữa.
          </p>
        )}

        <ul className="space-y-2">
          {conLai.map((l) => (
            <li
              key={l.id}
              className="flex items-center justify-between gap-3 rounded-xl border border-line p-3"
            >
              <div className="min-w-0">
                <div className="text-xs font-bold text-ink">
                  {fmtDayTime(l.slot_start)}
                </div>
                <div className="truncate text-[11px] text-ink-soft">
                  {l.service_name || "Chưa chọn dịch vụ"}
                  {" · "}
                  {l.doctor_name || "Chưa phân bác sĩ"}
                  {" · "}
                  {NHAN_TRANG_THAI[l.status] ?? l.status}
                </div>
              </div>
              {/* Lịch cuối cùng KHÔNG huỷ được ở đây. Bảng này để bỏ lịch THỪA;
                  huỷ nốt cái cuối là huỷ hẳn cuộc hẹn của khách, và việc đó
                  phải đi qua ô "Đổi / huỷ lịch hẹn" — nơi có ô chọn lý do thật
                  thay vì gán cứng "đặt trùng". */}
              <button
                type="button"
                onClick={() => void huy(l)}
                disabled={dangHuy !== null || conLai.length === 1}
                title={
                  conLai.length === 1
                    ? "Đây là lịch duy nhất — huỷ hẳn thì dùng “Đổi / huỷ lịch hẹn”"
                    : undefined
                }
                className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-danger/40 px-2.5 py-1.5 text-[11px] font-semibold text-danger hover:bg-danger-bg disabled:opacity-40"
              >
                <CalendarX2 className="size-3.5" />
                {dangHuy === l.id ? "Đang bỏ…" : "Bỏ lịch này"}
              </button>
            </li>
          ))}
        </ul>

        {loi && (
          <p
            role="alert"
            className="flex items-start gap-1.5 rounded-xl border border-danger/30 bg-danger-bg px-3 py-2 text-xs text-danger"
          >
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />
            {loi}
          </p>
        )}
      </div>
    </div>
  );
}
