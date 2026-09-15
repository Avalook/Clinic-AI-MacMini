"use client";

// "3. KHUNG GIỜ KHẢ DỤNG" — lưới thẻ khung giờ của bác sĩ + ngày đang chọn
// (Tuyền duyệt 16/09/2026). Cùng nguồn `quote` với popup của bảng tuần.

import { useEffect, useState } from "react";
import { chuKhung, taiQuote, type KhungQuote, type QuoteNgay } from "./cho-trong";

export interface ThongTinKhung {
  datTuDo: boolean;
  offDuty: boolean;
  khung: KhungQuote | null;
}

function ddmmyyyy(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

export default function KhungGioKhaDung({
  doctorId,
  doctorName,
  date,
  time,
  homNay,
  bayGioPhut,
  lamMoi,
  onChon,
  onThongTin,
}: {
  doctorId: string | null;
  doctorName: string;
  date: string;
  time: string;
  homNay: string;
  bayGioPhut: number;
  lamMoi: number;
  onChon: (time: string) => void;
  /** Báo lên panel phải: sức chứa của khung đang chọn (một nguồn với lưới). */
  onThongTin: (t: ThongTinKhung | null) => void;
}) {
  const [q, setQ] = useState<QuoteNgay | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void taiQuote(date, doctorId, ctrl.signal).then((d) => {
      if (!ctrl.signal.aborted) setQ(d);
    });
    return () => ctrl.abort();
  }, [date, doctorId, lamMoi]);

  useEffect(() => {
    if (!q) {
      onThongTin(null);
      return;
    }
    onThongTin({
      datTuDo: q.dat_tu_do,
      offDuty: q.off_duty,
      khung: q.slots.find((k) => k.time === time) ?? null,
    });
  }, [q, time, onThongTin]);

  const conTrongNgay = q && !q.dat_tu_do ? q.slots.reduce((t, k) => t + k.con_lai, 0) : null;

  return (
    <section className="rounded-card border border-hairline bg-surface p-4 shadow-card">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-emph font-semibold text-ink">3. Khung giờ khả dụng</h3>
          <p className="text-label text-ink-muted">
            {doctorName} · {ddmmyyyy(date)}
          </p>
        </div>
        {q && (
          <span className="rounded-chip bg-brand-50 px-2 py-0.5 text-label font-medium text-brand-700">
            {q.dat_tu_do
              ? "Tuần chưa công bố lịch trực — đặt tự do"
              : `Còn ${conTrongNgay} chỗ trong ngày`}
          </span>
        )}
      </div>
      {!q ? (
        <p className="py-4 text-center text-body text-ink-muted">Đang tải…</p>
      ) : q.slots.length === 0 ? (
        <p className="py-4 text-center text-body text-ink-muted">
          {q.off_duty ? "Bác sĩ nghỉ ngày này." : "Không có khung giờ nào."}
        </p>
      ) : (
        <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 2xl:grid-cols-4">
          {q.slots.map((k) => {
            const daQua = date === homNay && k.minute_of_day + k.slot_minutes <= bayGioPhut;
            const c = chuKhung(k, q.dat_tu_do, daQua);
            const dangChon = k.time === time;
            const cuoi = k.minute_of_day + k.slot_minutes;
            const den = `${String(Math.floor(cuoi / 60)).padStart(2, "0")}:${String(cuoi % 60).padStart(2, "0")}`;
            return (
              <li key={k.time}>
                <button
                  type="button"
                  disabled={c.khoa}
                  onClick={() => onChon(k.time)}
                  aria-pressed={dangChon}
                  className={`w-full rounded-control px-2 py-2 text-center ring-1 ring-inset disabled:cursor-not-allowed disabled:opacity-60 ${
                    dangChon ? "bg-brand-600 text-white ring-brand-600" : `${c.mau} ring-transparent hover:ring-brand-300`
                  }`}
                >
                  <span className="block whitespace-nowrap text-body font-semibold tabular-nums">
                    {k.time}–{den}
                  </span>
                  <span className="block text-label">{c.chu}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
