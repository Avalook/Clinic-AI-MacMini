"use client";

// BẢNG BÁC SĨ × TUẦN + POPUP KHUNG GIỜ (Tuyền duyệt 16/09/2026).
//
// Thay hàng nút ngày + danh sách khung dọc: nhìn một lần thấy cả tuần của mọi
// bác sĩ (còn chỗ / ít chỗ / đầy / nghỉ / đặt tự do), bấm một ô là popup liệt
// kê khung giờ của bác sĩ đó ngày đó, bấm khung là chọn luôn.
//
// Số chỗ đọc từ backend (cho-trong.ts). Không tính gì ở đây.

import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import {
  MAU_NGAY,
  NHAN_NGAY,
  chuKhung,
  chuONgay,
  moDuoc,
  taiBangTuan,
  taiQuote,
  type BangTuan,
  type QuoteNgay,
  type TrangThaiNgay,
} from "./cho-trong";

const THU = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"];
const CHU_THICH: TrangThaiNgay[] = ["CON_CHO", "IT_CHO", "DAY", "NGHI", "TU_DO"];

function ddmm(iso: string): string {
  const [, m, d] = iso.split("-");
  return `${d}/${m}`;
}

function vietTat(ten: string): string {
  return ten
    .split(/\s+/)
    .filter(Boolean)
    .slice(-2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

export default function BangBacSiTuan({
  weekStart,
  lamMoi,
  homNay,
  bayGioPhut,
  chon,
  locBacSi,
  onChonKhung,
}: {
  /** Thứ Hai của tuần, yyyy-mm-dd. */
  weekStart: string;
  /** Đổi số này để tải lại (vd sau khi đặt xong). */
  lamMoi: number;
  homNay: string;
  /** Phút trong ngày hiện tại (giờ VN) — khoá khung đã qua của hôm nay. */
  bayGioPhut: number;
  chon: { doctorId: string | null; date: string; time: string } | null;
  /** "all" = mọi bác sĩ; hoặc id bác sĩ; "none" = chỉ hàng chưa phân. */
  locBacSi: string;
  onChonKhung: (v: {
    doctorId: string | null;
    doctorName: string;
    date: string;
    time: string;
  }) => void;
}) {
  const [bang, setBang] = useState<BangTuan | null>(null);
  const [loi, setLoi] = useState(false);
  const [popup, setPopup] = useState<{
    doctorId: string | null;
    doctorName: string;
    date: string;
    x: number;
    y: number;
  } | null>(null);
  const [quote, setQuote] = useState<QuoteNgay | null>(null);
  const khung = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    void taiBangTuan(weekStart, ctrl.signal).then((b) => {
      if (ctrl.signal.aborted) return;
      setBang(b);
      setLoi(b === null);
    });
    return () => ctrl.abort();
  }, [weekStart, lamMoi]);

  useEffect(() => {
    if (!popup) return;
    const ctrl = new AbortController();
    void taiQuote(popup.date, popup.doctorId, ctrl.signal).then((q) => {
      if (!ctrl.signal.aborted) setQuote(q);
    });
    return () => ctrl.abort();
  }, [popup, lamMoi]);

  const hang = (bang?.bac_si ?? []).filter((b) =>
    locBacSi === "all" ? true : locBacSi === "none" ? b.id === null : b.id === locBacSi,
  );

  function moPopup(
    e: React.MouseEvent<HTMLButtonElement>,
    doctorId: string | null,
    doctorName: string,
    date: string,
  ) {
    const goc = khung.current?.getBoundingClientRect();
    const o = e.currentTarget.getBoundingClientRect();
    setQuote(null);
    setPopup({
      doctorId,
      doctorName,
      date,
      x: Math.max(0, Math.min(o.left - (goc?.left ?? 0), (goc?.width ?? 600) - 260)),
      y: o.bottom - (goc?.top ?? 0) + 4,
    });
  }

  return (
    <div ref={khung} className="relative">
      <div className="flex flex-wrap items-center justify-end gap-3 px-1 pb-2 text-label text-ink-muted">
        {CHU_THICH.map((t) => (
          <span key={t} className="inline-flex items-center gap-1.5">
            <span className={`size-2.5 rounded-full ${MAU_NGAY[t].split(" ")[0]}`} />
            {NHAN_NGAY[t]}
          </span>
        ))}
      </div>

      {loi ? (
        <p className="rounded-card bg-danger-bg px-3 py-2 text-body text-danger">
          Không đọc được lịch còn chỗ của tuần này. Thử tải lại.
        </p>
      ) : !bang ? (
        <p className="px-3 py-6 text-center text-body text-ink-muted">Đang tải lịch tuần…</p>
      ) : (
        <div className="overflow-x-auto rounded-card border border-hairline">
          <table className="w-full min-w-130 border-collapse text-body">
            <thead>
              <tr className="bg-surface-muted">
                <th className="sticky left-0 z-10 bg-surface-muted px-3 py-2 text-left text-label font-semibold uppercase tracking-wide text-ink-muted">
                  Bác sĩ
                </th>
                {bang.ngay.map((d, i) => (
                  <th
                    key={d}
                    className={`px-1 py-2 text-center text-label font-semibold ${
                      d === homNay ? "text-brand-700" : "text-ink-muted"
                    }`}
                  >
                    <span className="block">{THU[i]}</span>
                    <span className="block tabular-nums">{ddmm(d)}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {hang.map((b) => (
                <tr key={b.id ?? "chua-phan"} className="border-t border-hairline">
                  <th
                    scope="row"
                    className="sticky left-0 z-10 bg-surface px-3 py-2 text-left font-normal"
                  >
                    <span className="flex items-center gap-2">
                      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-brand-50 text-label font-semibold text-brand-700">
                        {b.id ? vietTat(b.full_name) : "?"}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate font-medium text-ink">{b.full_name}</span>
                        <span className="block text-label text-ink-muted">
                          {b.id === null
                            ? "Quản lý phân sau"
                            : b.role === "ULTRASOUND_DOCTOR"
                              ? "Bác sĩ siêu âm"
                              : "Bác sĩ"}
                        </span>
                      </span>
                    </span>
                  </th>
                  {b.o.map((o) => {
                    const dangChon =
                      chon && chon.date === o.date && (chon.doctorId ?? null) === b.id;
                    return (
                      <td key={o.date} className="px-1 py-1.5 text-center">
                        {moDuoc(o) ? (
                          <button
                            type="button"
                            onClick={(e) => moPopup(e, b.id, b.full_name, o.date)}
                            aria-label={`${b.full_name} ${ddmm(o.date)}: ${chuONgay(o)}`}
                            className={`h-9 w-full whitespace-nowrap rounded-control px-1 text-label font-medium hover:brightness-95 ${
                              MAU_NGAY[o.trang_thai]
                            } ${dangChon ? "ring-2 ring-brand-600" : ""}`}
                          >
                            {chuONgay(o)}
                          </button>
                        ) : (
                          <span
                            className={`flex h-9 w-full items-center justify-center rounded-control px-1 text-label ${
                              MAU_NGAY[o.trang_thai]
                            }`}
                          >
                            {chuONgay(o)}
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {popup && (
        <>
          <button
            type="button"
            aria-label="Đóng chọn khung giờ"
            className="fixed inset-0 z-20 cursor-default"
            onClick={() => setPopup(null)}
          />
          <div
            role="dialog"
            aria-label={`Khung giờ ${popup.doctorName} ${ddmm(popup.date)}`}
            className="absolute z-30 w-64 rounded-modal border border-hairline bg-surface p-3 shadow-panel"
            style={{ left: popup.x, top: popup.y }}
          >
            <div className="mb-2 flex items-start justify-between gap-2">
              <div>
                <p className="text-emph font-semibold text-ink">{popup.doctorName}</p>
                <p className="text-label text-ink-muted">
                  {THU[(bang?.ngay ?? []).indexOf(popup.date)] ?? ""}, {ddmm(popup.date)}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setPopup(null)}
                aria-label="Đóng"
                className="rounded-control p-1 text-ink-muted hover:bg-surface-sunken"
              >
                <X className="size-4" />
              </button>
            </div>
            {!quote ? (
              <p className="py-3 text-center text-label text-ink-muted">Đang tải khung giờ…</p>
            ) : quote.slots.length === 0 ? (
              <p className="py-3 text-center text-label text-ink-muted">
                {quote.off_duty ? "Bác sĩ nghỉ ngày này." : "Không có khung giờ nào."}
              </p>
            ) : (
              <ul className="max-h-72 space-y-1 overflow-y-auto pr-1">
                {quote.slots.map((k) => {
                  const daQua = popup.date === homNay && k.minute_of_day + k.slot_minutes <= bayGioPhut;
                  const c = chuKhung(k, quote.dat_tu_do, daQua);
                  const dangChon =
                    chon?.date === popup.date &&
                    (chon.doctorId ?? null) === popup.doctorId &&
                    chon.time === k.time;
                  const den = `${String(Math.floor((k.minute_of_day + k.slot_minutes) / 60)).padStart(2, "0")}:${String((k.minute_of_day + k.slot_minutes) % 60).padStart(2, "0")}`;
                  return (
                    <li key={k.time}>
                      <button
                        type="button"
                        disabled={c.khoa}
                        onClick={() => {
                          onChonKhung({
                            doctorId: popup.doctorId,
                            doctorName: popup.doctorName,
                            date: popup.date,
                            time: k.time,
                          });
                          setPopup(null);
                        }}
                        className={`flex w-full items-center justify-between rounded-control px-2 py-1.5 text-body hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60 ${
                          dangChon ? "bg-surface-selected font-semibold" : ""
                        }`}
                      >
                        <span className="tabular-nums text-ink">
                          {k.time} – {den}
                        </span>
                        <span className={`rounded-chip px-1.5 py-0.5 text-label font-medium ${c.mau}`}>
                          {c.chu}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
