"use client";

// ĐỔI LỊCH TẠI CHỖ — MỘT popover cho mọi lối (Tuyền chốt 29/09/2026, bản demo
// doi-lich/index.html): Tiếp đón khách (bấm dòng ngày khác / ⋯ "Đổi sang hôm
// nay"), Trang chủ (⋯ "Đổi lịch"), Đặt lịch (khung vàng "đã có lịch sắp tới").
//
//   · Chọn ngày: Hôm nay · Mai · Chọn ngày…
//   · Mỗi bác sĩ có ca ngày ấy một hàng ô giờ (xanh = trống ngay bây giờ, vàng =
//     còn ít, gạch = đầy); bác sĩ cũ gắn "BS cũ"; hôm nay có ô "Ngay bây giờ".
//   · Chân dính đáy: "➜ Lịch mới" + lý do + [Thôi] [Chỉ đổi lịch] [Đổi & Check-in].
//
// CHỈ VẼ. Máy chủ quyết trạng thái ô, ai được check-in, ô nào chỉ đi kèm
// check-in (`GET /api/v1/appointments/{id}/doi-lich-nhanh`); lệnh ghi là MỘT
// giao dịch (`POST …/doi-lich-nhanh`: đổi lịch + check-in luôn).

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import Button from "@/components/ui/Button";
import { chipClass } from "@/components/ui/Chip";
import PopoverNeo from "@/components/ui/PopoverNeo";
import { fmtTime, ngayVN } from "@/lib/datetime";
import { doctorName } from "@/lib/doctor-name";
import { dayShort, fmtDayMonth } from "@/lib/roster";

type TrangThaiO = "TRONG" | "IT" | "DAY";

interface OGio {
  gio: string;
  slot_start: string;
  slot_end: string;
  trang_thai: TrangThaiO;
  con_lai: number | null;
  dang_chay: boolean;
  la_lich_hien_tai: boolean;
}

interface OBayGio {
  gio: string;
  slot_start: string;
  slot_end: string;
  trang_thai: TrangThaiO;
  ngoai_ca: boolean;
  chi_kem_check_in: boolean;
}

interface HangBacSi {
  id: string;
  ten: string;
  bs_cu: boolean;
  ca: string | null;
  o: OGio[];
  ngay_bay_gio: OBayGio | null;
}

interface GoiDoiLich {
  ngay: string;
  hom_nay: string;
  ngay_mai: string;
  la_hom_nay: boolean;
  da_qua: boolean;
  lich: {
    id: string;
    ten_khach: string | null;
    slot_start: string;
    bac_si_ten: string | null;
    dich_vu: string | null;
  };
  cho_check_in: boolean;
  ly_do: string[];
  ly_do_mac_dinh: string;
  bac_si: HangBacSi[];
}

interface Chon {
  bacSiId: string;
  bacSiTen: string;
  gio: string;
  slot_start: string;
  slot_end: string;
  bayGio: boolean;
  chiKemCheckIn: boolean;
}

const LY_DO_KHAC = "Khác…";

/** Lớp của một ô giờ — chỉ tô theo `trang_thai` máy chủ trả. */
function lopO(tt: TrangThaiO, dangChay: boolean, chon: boolean, tat: boolean): string {
  const goc =
    "inline-flex min-w-16 flex-col items-center rounded-control px-2 py-1 text-meta " +
    "tabular-nums ring-1 ring-inset transition-colors max-md:min-h-10 ";
  if (chon) return goc + "bg-brand-600 font-semibold text-white ring-brand-600";
  if (tat) return goc + "cursor-not-allowed bg-surface-sunken text-ink-faint ring-transparent";
  if (tt === "IT") return goc + "bg-warning-bg text-warning ring-warning/40 hover:ring-warning";
  if (dangChay) return goc + "bg-success-bg font-semibold text-success ring-success/40 hover:ring-success";
  return goc + "bg-surface text-ink ring-line hover:bg-surface-muted";
}

function nhanNgay(ngay: string, goi: GoiDoiLich | null): string {
  if (goi && ngay === goi.hom_nay) return "hôm nay";
  if (goi && ngay === goi.ngay_mai) return "ngày mai";
  return `${dayShort(ngay)} ${fmtDayMonth(ngay)}`;
}

export default function DoiLichTaiCho({
  lichId,
  neo,
  onDong,
  ngayDau,
  onXong,
}: {
  lichId: string;
  /** Phần tử neo popover (dòng khách / khung vàng). */
  neo: HTMLElement | null;
  onDong: () => void;
  /** Ngày chọn sẵn (YYYY-MM-DD). Không truyền = hôm nay (máy chủ quyết). */
  ngayDau?: string;
  /** Đổi xong — nhận câu báo. Không truyền → tải lại trang. */
  onXong?: (cau: string) => void;
}) {
  const router = useRouter();
  const [ngay, setNgay] = useState<string | null>(ngayDau ?? null);
  const [chonNgayTay, setChonNgayTay] = useState(false);
  const [goi, setGoi] = useState<{ ngay: string | null; data: GoiDoiLich | null; loi: string | null } | null>(
    null,
  );
  const [chon, setChon] = useState<Chon | null>(null);
  const [lyDo, setLyDo] = useState<string | null>(null);
  const [lyDoKhac, setLyDoKhac] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loiGui, setLoiGui] = useState<string | null>(null);
  // Khoá chống bấm đúp: cùng popover + cùng lựa chọn = cùng khoá.
  const [phien] = useState(() => crypto.randomUUID());

  useEffect(() => {
    let huy = false;
    const q = new URLSearchParams({ id: lichId });
    if (ngay) q.set("ngay", ngay);
    void fetch(`/api/appointments/doi-lich-nhanh?${q.toString()}`, { cache: "no-store" })
      .then(async (res) => {
        const body = await res.json().catch(() => ({}));
        if (huy) return;
        setGoi(
          res.ok
            ? { ngay, data: body as GoiDoiLich, loi: null }
            : { ngay, data: null, loi: body?.error ?? "Không đọc được lịch trống." },
        );
      })
      .catch(() => {
        if (!huy) setGoi({ ngay, data: null, loi: "Mất kết nối — thử lại." });
      });
    return () => {
      huy = true;
    };
  }, [lichId, ngay]);

  const dung = goi && goi.ngay === ngay ? goi : null;
  const data = dung?.data ?? null;
  const lyDoChon = lyDo ?? data?.ly_do_mac_dinh ?? "";
  const lyDoCuoi = lyDoChon === LY_DO_KHAC ? lyDoKhac.trim() : lyDoChon;

  function doiNgay(n: string) {
    setChon(null);
    setLoiGui(null);
    setNgay(n);
  }

  async function gui(checkIn: boolean) {
    if (!chon || dangGui) return;
    if (!lyDoCuoi) {
      setLoiGui("Ghi lý do đổi lịch.");
      return;
    }
    setDangGui(true);
    setLoiGui(null);
    const res = await fetch("/api/appointments/doi-lich-nhanh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: lichId,
        slot_start: chon.slot_start,
        slot_end: chon.slot_end,
        doctor_id: chon.bacSiId,
        ly_do: lyDoCuoi,
        check_in: checkIn,
        idempotency_key: `${phien}:${chon.bacSiId}:${chon.slot_start}:${checkIn ? 1 : 0}`,
      }),
    }).catch(() => null);
    setDangGui(false);
    if (!res) {
      setLoiGui("Mất kết nối — lịch chưa đổi. Thử lại.");
      return;
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      setLoiGui(body?.error ?? "Không đổi được lịch.");
      return;
    }
    const khi = `${doctorName(chon.bacSiTen)} · ${chon.gio} ${nhanNgay(data?.ngay ?? "", data)}`;
    const cau = checkIn
      ? `Đã đổi lịch sang ${khi} và check-in${body?.queue_number ? ` — số ${body.queue_number}` : ""}.`
      : `Đã đổi lịch sang ${khi}.`;
    onDong();
    if (onXong) onXong(cau);
    else router.refresh();
  }

  const lich = data?.lich;
  const dau = (
    <div className="flex min-w-0 items-center gap-3">
      <span
        aria-hidden
        className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-50 text-emph font-semibold text-brand-700"
      >
        {(lich?.ten_khach ?? "?").trim().split(/\s+/).pop()?.charAt(0).toUpperCase() ?? "?"}
      </span>
      <div className="min-w-0">
        <p className="truncate text-emph font-semibold text-ink">
          Đổi lịch · {lich?.ten_khach ?? "…"}
        </p>
        {lich ? (
          <p className="truncate text-meta text-ink-muted">
            Lịch hiện tại:{" "}
            <s>
              {dayShort(ngayVN(lich.slot_start))} {fmtDayMonth(ngayVN(lich.slot_start))} ·{" "}
              {fmtTime(lich.slot_start)}
            </s>
            {lich.bac_si_ten ? ` · ${doctorName(lich.bac_si_ten)}` : ""}
            {lich.dich_vu ? ` · ${lich.dich_vu}` : ""}
          </p>
        ) : null}
      </div>
    </div>
  );

  const nutNgay = (ma: string | undefined, nhan: string, dangChon: boolean) => (
    <button
      key={nhan}
      type="button"
      aria-pressed={dangChon}
      disabled={ma === ""}
      onClick={() => {
        if (ma === undefined) {
          setChonNgayTay(true);
          return;
        }
        setChonNgayTay(false);
        doiNgay(ma);
      }}
      className={`h-8 rounded-control px-3 text-body transition-colors max-md:h-10 ${
        dangChon ? "bg-surface font-semibold text-ink shadow-card" : "text-ink-muted hover:text-ink"
      }`}
    >
      {nhan}
    </button>
  );

  const ngayHien = data?.ngay ?? ngay;
  const laHomNay = !chonNgayTay && data !== null && ngayHien === data.hom_nay;
  const laMai = !chonNgayTay && data !== null && ngayHien === data.ngay_mai;

  const chan = (
    <div className="flex flex-col gap-2">
      <p className="text-body text-ink">
        {chon ? (
          <>
            ➜ Lịch mới: <b>{doctorName(chon.bacSiTen)}</b> · <b>{chon.bayGio ? `ngay bây giờ (${chon.gio})` : chon.gio}</b>{" "}
            · {nhanNgay(data?.ngay ?? "", data)}
          </>
        ) : (
          <span className="text-ink-muted">Chọn một ô giờ.</span>
        )}
      </p>
      {loiGui ? (
        <p role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-meta text-danger">
          {loiGui}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor={`ly-do-${lichId}`}>
          Lý do đổi lịch
        </label>
        <select
          id={`ly-do-${lichId}`}
          value={lyDoChon}
          onChange={(e) => setLyDo(e.target.value)}
          className="h-8 rounded-control border border-line bg-surface px-2 text-body text-ink max-md:h-10"
        >
          {(data?.ly_do ?? []).map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
        {lyDoChon === LY_DO_KHAC ? (
          <input
            type="text"
            value={lyDoKhac}
            maxLength={300}
            onChange={(e) => setLyDoKhac(e.target.value)}
            placeholder="Ghi lý do…"
            aria-label="Lý do khác"
            className="h-8 min-w-0 flex-1 rounded-control border border-line bg-surface px-2 text-body text-ink max-md:h-10"
          />
        ) : null}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="md" onClick={onDong}>
            Thôi
          </Button>
          <Button
            variant="secondary"
            size="md"
            disabled={!chon || dangGui || chon.chiKemCheckIn}
            title={chon?.chiKemCheckIn ? "Ngoài giờ ca — chỉ đổi kèm check-in (khách đang ở quầy)." : undefined}
            onClick={() => void gui(false)}
          >
            Chỉ đổi lịch
          </Button>
          {data?.cho_check_in ? (
            <Button variant="primary" size="md" disabled={!chon || dangGui} onClick={() => void gui(true)}>
              {dangGui ? "Đang đổi…" : "Đổi & Check-in luôn"}
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );

  return (
    <PopoverNeo neo={neo} onDong={onDong} dau={dau} chan={chan}>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div role="group" aria-label="Chọn ngày" className="inline-flex rounded-control bg-surface-sunken p-0.5">
          {nutNgay(data?.hom_nay ?? "", "Hôm nay", laHomNay)}
          {nutNgay(data?.ngay_mai ?? "", "Mai", laMai)}
          {nutNgay(undefined, "Chọn ngày…", chonNgayTay || (!laHomNay && !laMai && data !== null))}
        </div>
        {chonNgayTay || (data !== null && !laHomNay && !laMai) ? (
          <input
            type="date"
            aria-label="Ngày đổi sang"
            min={data?.hom_nay}
            value={ngayHien ?? ""}
            onChange={(e) => {
              if (/^\d{4}-\d{2}-\d{2}$/.test(e.target.value)) doiNgay(e.target.value);
            }}
            className="h-8 rounded-control border border-line bg-surface px-2 text-body text-ink max-md:h-10"
          />
        ) : null}
      </div>

      {/* Chú giải màu. */}
      <div className="mb-3 flex flex-wrap gap-1.5" aria-hidden>
        <span className={chipClass("success")}>Trống ngay bây giờ</span>
        <span className={chipClass("warning")}>Còn ít</span>
        <span className={`${chipClass("neutral")} line-through`}>Đầy</span>
      </div>

      {dung === null ? (
        <p className="py-6 text-center text-body text-ink-muted">Đang xem giờ trống…</p>
      ) : dung.loi ? (
        <p role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-body text-danger">
          {dung.loi}
        </p>
      ) : data && data.da_qua ? (
        <p className="py-6 text-center text-body text-ink-muted">Ngày đã qua — chọn hôm nay hoặc ngày sau.</p>
      ) : data && data.bac_si.length === 0 ? (
        <p className="py-6 text-center text-body text-ink-muted">
          Ngày này chưa có bác sĩ nào có ca — chọn ngày khác.
        </p>
      ) : data ? (
        <ul className="flex flex-col gap-3">
          {data.bac_si.map((b) => {
            const trong = b.o.length === 0 && !b.ngay_bay_gio;
            return (
              <li key={b.id} className="grid gap-2 md:grid-cols-[9rem_minmax(0,1fr)] md:items-start">
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-1.5 text-body font-semibold text-ink">
                    {doctorName(b.ten)}
                    {b.bs_cu ? <span className={chipClass("success")}>BS cũ</span> : null}
                  </p>
                  {b.ca ? <p className="text-meta text-ink-muted">Ca {b.ca}</p> : null}
                </div>
                {trong ? (
                  <p className="text-meta text-ink-faint">Không còn khung giờ nào trong ngày.</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {b.ngay_bay_gio ? (
                      (() => {
                        const n = b.ngay_bay_gio;
                        const tat = n.trang_thai === "DAY";
                        const dangChon =
                          chon?.bacSiId === b.id && chon.bayGio && chon.slot_start === n.slot_start;
                        return (
                          <button
                            type="button"
                            disabled={tat}
                            aria-pressed={dangChon}
                            onClick={() =>
                              setChon({
                                bacSiId: b.id,
                                bacSiTen: b.ten,
                                gio: n.gio,
                                slot_start: n.slot_start,
                                slot_end: n.slot_end,
                                bayGio: true,
                                chiKemCheckIn: n.chi_kem_check_in,
                              })
                            }
                            className={lopO(n.trang_thai, !tat, dangChon, tat)}
                          >
                            Ngay bây giờ
                            <span className="text-label font-normal">
                              {tat ? "đầy" : n.ngoai_ca ? "ngoài ca · kèm check-in" : "đang trống"}
                            </span>
                          </button>
                        );
                      })()
                    ) : null}
                    {b.o.map((o) => {
                      const tat = o.trang_thai === "DAY" || o.la_lich_hien_tai;
                      const dangChon =
                        chon?.bacSiId === b.id && !chon.bayGio && chon.slot_start === o.slot_start;
                      return (
                        <button
                          key={o.slot_start}
                          type="button"
                          disabled={tat}
                          aria-pressed={dangChon}
                          onClick={() =>
                            setChon({
                              bacSiId: b.id,
                              bacSiTen: b.ten,
                              gio: o.gio,
                              slot_start: o.slot_start,
                              slot_end: o.slot_end,
                              bayGio: false,
                              chiKemCheckIn: false,
                            })
                          }
                          className={`${lopO(o.trang_thai, o.dang_chay, dangChon, tat)} ${
                            o.trang_thai === "DAY" ? "line-through" : ""
                          }`}
                        >
                          {o.gio}
                          {o.la_lich_hien_tai ? (
                            <span className="text-label font-normal">đang hẹn</span>
                          ) : o.trang_thai === "DAY" ? (
                            <span className="text-label font-normal">đầy</span>
                          ) : o.trang_thai === "IT" && o.con_lai != null ? (
                            <span className="text-label font-normal">còn {o.con_lai}</span>
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      ) : null}
    </PopoverNeo>
  );
}
