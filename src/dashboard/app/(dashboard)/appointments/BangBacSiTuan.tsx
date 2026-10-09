"use client";

// BẢNG BÁC SĨ × TUẦN + POPUP KHUNG GIỜ (Tuyền duyệt 16/09/2026).
//
// Thay hàng nút ngày + danh sách khung dọc: nhìn một lần thấy cả tuần của mọi
// bác sĩ (còn chỗ / ít chỗ / đầy / nghỉ / đặt tự do), bấm một ô là popup liệt
// kê khung giờ của bác sĩ đó ngày đó, bấm khung là chọn luôn.
//
// Số chỗ đọc từ backend (cho-trong.ts). Không tính gì ở đây.

import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, X } from "lucide-react";
import {
  MAU_NGAY,
  NHAN_NGAY,
  chuKhung,
  chuONgay,
  moDuoc,
  taiBangTuan,
  taiQuote,
  type BangTuan,
  type HangBacSi,
  type QuoteNgay,
  type ThongTinKhung,
  type TrangThaiNgay,
} from "./cho-trong";
import { khoaGiuCho, useGiuCho } from "./dung-giu-cho";
import { khungDaQuaTheoPhut } from "@/lib/khung-da-qua";
import { unaccentVi } from "@/lib/validation";

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
  onChonKhung,
  doiTuan,
  chiNgay,
}: {
  /** Thứ Hai của tuần, yyyy-mm-dd. */
  weekStart: string;
  /** Đổi số này để tải lại (vd sau khi đặt xong). */
  lamMoi: number;
  homNay: string;
  /** Phút trong ngày hiện tại (giờ VN) — khoá khung đã qua của hôm nay. */
  bayGioPhut: number;
  chon: { doctorId: string | null; date: string; time: string } | null;
  onChonKhung: (v: {
    doctorId: string | null;
    doctorName: string;
    date: string;
    time: string;
    /** Sức chứa của đúng khung vừa bấm — panel phải đọc từ đây (16/09/2026,
     *  thay ô "3. Khung giờ khả dụng" đã bỏ). */
    thongTin: ThongTinKhung;
  }) => void;
  /** Có = vẽ nút tuần trước / sau / tuần này ngay trên bảng (form khách mới). */
  doiTuan?: { truoc: () => void; sau: () => void; homNay: () => void };
  /** Có = chỉ vẽ cột của NGÀY này, và chỉ các bác sĩ có ca hôm ấy (hàng
   *  "Chưa phân bác sĩ" luôn còn) — ô Ngày tái khám của phiếu (02/10/2026). */
  chiNgay?: string;
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
  // Chỗ CSKH khác đang giữ, THEO NGÀY CỦA POPUP — không theo ngày đang xem:
  // popup mở được một ngày khác, và trước 16/09/2026 nó mù hẳn chuyện này.
  // Popup đóng ⇒ `null` ⇒ hook không hỏi gì.
  const giuCho = useGiuCho(popup?.date ?? null);

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

  // BỘ LỌC BÁC SĨ — state nằm TRONG bảng, không ở màn gọi (16/09/2026).
  //
  // Nó chỉ đổi cách NHÌN cái bảng này, nên để màn ngoài giữ hộ là mời chúng
  // hiểu khác nhau: BookingHub từng giữ `selectedDoctorId` trong khi form khách
  // mới truyền cứng "all". Lọc rồi đổi khách thì lọc VẪN NGUYÊN — đó là cả
  // dụng ý: chốt một bác sĩ, đặt cùng một khung cho nhiều khách liên tiếp.
  const [loc, setLoc] = useState<string>("all");
  const [moLoc, setMoLoc] = useState(false);
  const [timLoc, setTimLoc] = useState("");
  const oTim = useRef<HTMLInputElement>(null);

  // GÕ ĐƯỢC NGAY, KHÔNG PHẢI BẤM THÊM MỘT NHÁT (Tuyền 16/09/2026: *"người dùng
  // có thể gõ luôn mà không cần click vào ô này"*). `autoFocus` của React không
  // đủ: cú bấm mở bảng giữ con trỏ ở chính nút tiêu đề cột — đo trên local, gõ
  // xong danh sách không lọc gì. Tự gọi focus sau khi bảng hiện ra.
  useEffect(() => {
    if (moLoc) oTim.current?.focus();
  }, [moLoc]);

  // Chế độ một ngày: cột chỉ còn ngày ấy; bác sĩ nghỉ hôm ấy không chiếm hàng.
  const cot = (bang?.ngay ?? []).filter((d) => !chiNgay || d === chiNgay);
  const oCua = (b: HangBacSi) =>
    b.o.filter((o) => !chiNgay || o.date === chiNgay);
  const hang = (bang?.bac_si ?? [])
    .filter((b) => (loc === "all" ? true : loc === "none" ? b.id === null : b.id === loc))
    .filter(
      (b) =>
        !chiNgay ||
        b.id === null ||
        b.o.some((o) => o.date === chiNgay && moDuoc(o)),
    );
  const tenLoc = (bang?.bac_si ?? []).find((b) => (b.id ?? "none") === loc)?.full_name;
  const timThay = (bang?.bac_si ?? []).filter((b) =>
    unaccentVi(b.full_name).includes(unaccentVi(timLoc.trim())),
  );

  function chonLoc(id: string) {
    setLoc(id);
    setMoLoc(false);
    setTimLoc("");
  }

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
        {doiTuan && (
          <span className="mr-auto inline-flex items-center gap-1">
            <button
              type="button"
              onClick={doiTuan.truoc}
              aria-label="Tuần trước"
              className="rounded-control p-1 text-ink-soft ring-1 ring-inset ring-line-strong hover:bg-surface-muted"
            >
              <ChevronLeft className="size-4" />
            </button>
            <span className="px-1 font-semibold tabular-nums text-ink">
              Tuần {ddmm(weekStart)}
            </span>
            <button
              type="button"
              onClick={doiTuan.sau}
              aria-label="Tuần sau"
              className="rounded-control p-1 text-ink-soft ring-1 ring-inset ring-line-strong hover:bg-surface-muted"
            >
              <ChevronRight className="size-4" />
            </button>
            <button
              type="button"
              onClick={doiTuan.homNay}
              className="ml-1 rounded-control px-2 py-1 text-ink ring-1 ring-inset ring-line-strong hover:bg-surface-muted"
            >
              Tuần này
            </button>
          </span>
        )}
        {CHU_THICH.map((t) => (
          <span key={t} className="inline-flex items-center gap-1.5">
            <span className={`size-2.5 rounded-full ${MAU_NGAY[t].split(" ")[0]}`} />
            {NHAN_NGAY[t]}
          </span>
        ))}
      </div>

      {/* BẢNG CHỌN BÁC SĨ — ô tìm ở trên nhận sẵn con trỏ, gõ thẳng là lọc,
          Enter lấy tên đầu tiên khớp. "Tất cả bác sĩ" luôn đứng đầu: mở ra là
          thấy ngay đường quay về, không phải nhớ cách bỏ lọc. */}
      {moLoc && (
        <>
          <button
            type="button"
            aria-label="Đóng chọn bác sĩ"
            className="fixed inset-0 z-20 cursor-default"
            onClick={() => setMoLoc(false)}
          />
          <div
            role="dialog"
            aria-label="Chọn bác sĩ"
            className="absolute left-0 top-8 z-30 w-64 rounded-modal border border-hairline bg-surface p-2 shadow-panel"
          >
            <input
              ref={oTim}
              value={timLoc}
              onChange={(e) => setTimLoc(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && timThay[0]) chonLoc(timThay[0].id ?? "none");
                if (e.key === "Escape") setMoLoc(false);
              }}
              placeholder="Gõ tên bác sĩ…"
              className="mb-1 w-full rounded-control border border-line px-2 py-1.5 text-body text-ink outline-none focus:border-brand-600"
            />
            <ul className="max-h-64 space-y-0.5 overflow-y-auto">
              <li>
                <button
                  type="button"
                  onClick={() => chonLoc("all")}
                  className={`w-full rounded-control px-2 py-1.5 text-left text-body hover:bg-surface-muted ${
                    loc === "all" ? "bg-surface-selected font-semibold" : ""
                  }`}
                >
                  Tất cả bác sĩ
                </button>
              </li>
              {timThay.map((b) => (
                <li key={b.id ?? "chua-phan"}>
                  <button
                    type="button"
                    onClick={() => chonLoc(b.id ?? "none")}
                    className={`w-full truncate rounded-control px-2 py-1.5 text-left text-body hover:bg-surface-muted ${
                      (b.id ?? "none") === loc ? "bg-surface-selected font-semibold" : ""
                    }`}
                  >
                    {b.full_name}
                  </button>
                </li>
              ))}
              {timThay.length === 0 && (
                <li className="px-2 py-2 text-label text-ink-muted">Không có tên nào khớp.</li>
              )}
            </ul>
          </div>
        </>
      )}

      {loi ? (
        <p className="rounded-card bg-danger-bg px-3 py-2 text-body text-danger">
          Không đọc được lịch còn chỗ của tuần này. Thử tải lại.
        </p>
      ) : !bang ? (
        <p className="px-3 py-6 text-center text-body text-ink-muted">Đang tải lịch tuần…</p>
      ) : (
        <div className="overflow-x-auto rounded-card border border-hairline">
          {/* Bảy cột cần bề rộng tối thiểu (cuộn ngang); một ngày thì vừa 375. */}
          <table
            className={`w-full border-collapse text-body ${chiNgay ? "" : "min-w-130"}`}
          >
            <thead>
              <tr className="bg-surface-muted">
                {/* CỘT "BÁC SĨ" LÀ BỘ LỌC (Tuyền 16/09/2026).

                    Dụng ý: chốt một bác sĩ rồi đặt CÙNG một khung giờ cho nhiều
                    khách liên tiếp — đổi khách không đụng tới bộ lọc. Ô lọc
                    từng nằm ở hàng lọc phía trên và đã bỏ sáng nay vì nó đứng
                    xa bảng; đặt ngay trên cột nó lọc thì không phải giải thích
                    nó lọc cái gì. */}
                <th className="sticky left-0 z-10 bg-surface-muted p-0 text-left">
                  <button
                    type="button"
                    onClick={() => {
                      setMoLoc((v) => !v);
                      setTimLoc("");
                    }}
                    aria-expanded={moLoc}
                    className="flex w-full items-center gap-1 px-3 py-2 text-label font-semibold uppercase tracking-wide text-ink-muted hover:text-brand-700"
                  >
                    <span className="truncate">
                      {loc === "all" ? "Bác sĩ" : (tenLoc ?? "Bác sĩ")}
                    </span>
                    <ChevronDown className="size-3.5 shrink-0" />
                  </button>
                </th>
                {cot.map((d) => (
                  <th
                    key={d}
                    className={`px-1 py-2 text-center text-label font-semibold ${
                      d === homNay ? "text-brand-700" : "text-ink-muted"
                    }`}
                  >
                    <span className="block">{THU[bang.ngay.indexOf(d)]}</span>
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
                  {oCua(b).map((o) => {
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
                  // Đã qua = khung đã KẾT THÚC (khung đang chạy vẫn đặt được).
                  const daQua =
                    popup.date === homNay &&
                    khungDaQuaTheoPhut(k.minute_of_day, k.slot_minutes, bayGioPhut);
                  const c = chuKhung(
                    k,
                    quote.dat_tu_do,
                    daQua,
                    giuCho.has(khoaGiuCho(popup.doctorId, popup.date, k.time)),
                  );
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
                            thongTin: {
                              datTuDo: quote.dat_tu_do,
                              offDuty: quote.off_duty,
                              khung: k,
                            },
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
