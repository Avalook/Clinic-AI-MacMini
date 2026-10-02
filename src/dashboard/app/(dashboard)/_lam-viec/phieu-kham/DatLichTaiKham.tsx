"use client";

// ĐẶT LỊCH HẸN THẬT ngay dưới ô "Ngày tái khám" (Tuyền 02/10/2026).
//
// Trước đây ô ngày chỉ sinh việc gọi cho CSKH — không có giờ nên không lên lịch
// hẹn. Khung này vẽ bảng còn chỗ của ĐÚNG ngày ấy (cùng `BangBacSiTuan` của màn
// Đặt lịch, chế độ một ngày): bác sĩ có ca thì chọn bác sĩ + giờ; chưa có lịch
// trực thì chọn hàng "Chưa phân bác sĩ" — CSKH phân khi có lịch trực thật.
//
// Việc gọi của CSKH vẫn sinh như cũ. Không có luật nào ở đây: khách, dịch vụ,
// sức chứa, trùng giờ đều do máy chủ (`lich_tai_kham_service`) quyết.

import { CalendarCheck2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import BaoLoiCanhNut from "@/components/ui/BaoLoiCanhNut";
import Button from "@/components/ui/Button";
import XacNhanTaiCho from "@/components/ui/XacNhanTaiCho";
import { vnLocalToUtcISO, vnYmd } from "@/lib/datetime";
import { loiDocDuoc } from "@/lib/loi-doc-duoc";

import BangBacSiTuan from "../../appointments/BangBacSiTuan";
import { phutVn, thuHaiCua, type ThongTinKhung } from "../../appointments/cho-trong";
import { useNgheBang } from "../../dung-nghe-bang";

interface LichDaDat {
  appointment_id: string;
  ngay: string;
  gio: string;
  den: string;
  status: string;
  doctor_id: string | null;
  bac_si: string | null;
  dich_vu: string | null;
  huy_duoc: boolean;
}

const THU = ["Chủ nhật", "Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7"];

function ngayDai(iso: string): string {
  const [y, m, d] = iso.split("-");
  const thu = THU[new Date(`${iso}T12:00:00+07:00`).getUTCDay()] ?? "";
  return `${thu}, ${d}/${m}/${y}`;
}

function cong(gio: string, phut: number): string {
  const [h, m] = gio.split(":").map(Number);
  const t = (h ?? 0) * 60 + (m ?? 0) + phut;
  return `${String(Math.floor(t / 60) % 24).padStart(2, "0")}:${String(t % 60).padStart(2, "0")}`;
}

export default function DatLichTaiKham({ visitId, ngay }: { visitId: string; ngay: string }) {
  const [lich, setLich] = useState<LichDaDat | null | undefined>(undefined);
  const [dichVu, setDichVu] = useState<string | null>(null);
  const [lan, setLan] = useState(0);
  const [chon, setChon] = useState<{
    doctorId: string | null;
    doctorName: string;
    date: string;
    time: string;
    thongTin: ThongTinKhung;
  } | null>(null);
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [hoiHuy, setHoiHuy] = useState(false);
  const [bayGio, setBayGio] = useState(() => Date.now());

  const tai = useCallback(() => setLan((n) => n + 1), []);
  // CSKH đổi giờ / phân bác sĩ ở màn khác → khung này thấy ngay.
  useNgheBang(["appointment"], tai);

  useEffect(() => {
    const t = setInterval(() => setBayGio(Date.now()), 60_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch(`/api/phieu-kham?visit_id=${visitId}&xem=lich-tai-kham`, { signal: ctrl.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { lich: LichDaDat | null; dich_vu: string | null } | null) => {
        if (ctrl.signal.aborted) return;
        setLich(d ? d.lich : null);
        setDichVu(d?.dich_vu ?? null);
      })
      .catch(() => {
        if (!ctrl.signal.aborted) setLich(null);
      });
    return () => ctrl.abort();
  }, [visitId, lan]);

  const homNay = vnYmd();
  const ngayHopLe = /^\d{4}-\d{2}-\d{2}$/.test(ngay) && ngay >= homNay;

  async function gui(than: Record<string, unknown>, loiMacDinh: string): Promise<boolean> {
    setDangGui(true);
    setLoi(null);
    try {
      const r = await fetch("/api/phieu-kham", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visit_id: visitId, ...than }),
      });
      if (!r.ok) {
        setLoi(loiDocDuoc(await r.json().catch(() => ({})), loiMacDinh));
        return false;
      }
      return true;
    } catch {
      setLoi("Mất kết nối tới máy chủ — chưa ghi được.");
      return false;
    } finally {
      setDangGui(false);
      tai();
    }
  }

  async function datLich() {
    if (!chon || dangGui) return;
    const phut = chon.thongTin.khung?.slot_minutes ?? 15;
    const batDau = vnLocalToUtcISO(chon.date, chon.time);
    const ok = await gui(
      {
        thao_tac: "dat-lich-tai-kham",
        slot_start: batDau,
        slot_end: new Date(Date.parse(batDau) + phut * 60_000).toISOString(),
        doctor_id: chon.doctorId,
      },
      "Không đặt được lịch hẹn.",
    );
    if (ok) setChon(null);
  }

  async function huyLich() {
    if (!lich) return;
    const ok = await gui(
      { thao_tac: "huy-lich-tai-kham", appointment_id: lich.appointment_id },
      "Không huỷ được lịch hẹn.",
    );
    if (ok) setHoiHuy(false);
  }

  if (lich === undefined) return null;

  // ── Đã đặt: hiện lịch + huỷ để đặt lại (hoàn tác được) ───────────────────
  if (lich) {
    const lechNgay = ngayHopLe && lich.ngay !== ngay;
    return (
      <div className="space-y-2 rounded-card border border-success/30 bg-success-bg px-3 py-2.5">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-body text-ink">
          <CalendarCheck2 className="size-4 shrink-0 text-success" aria-hidden />
          <span className="font-semibold text-success">Đã đặt lịch hẹn</span>
          <span className="tabular-nums">
            {lich.gio}–{lich.den} · {ngayDai(lich.ngay)}
          </span>
          <span>· {lich.bac_si ?? "Chưa phân bác sĩ"}</span>
          {lich.dich_vu ? <span className="text-ink-muted">· {lich.dich_vu}</span> : null}
        </p>
        <p className="text-meta text-ink-muted">
          Lịch đã hiện ở màn Lịch hẹn
          {lich.bac_si ? "" : " (hàng Chờ xếp bác sĩ — CSKH / quản lý phân bác sĩ khi có lịch trực)"}.
          CSKH vẫn nhận việc gọi chốt giờ trước ngày hẹn 7 ngày.
        </p>
        {lechNgay ? (
          <BaoLoiCanhNut muc="nhac">
            Ngày tái khám trên phiếu ({ngayDai(ngay)}) khác ngày của lịch hẹn. Huỷ lịch này rồi đặt
            lại theo ngày mới.
          </BaoLoiCanhNut>
        ) : null}
        {!lich.huy_duoc ? (
          <p className="text-meta text-ink-muted">Khách đã tới theo lịch này.</p>
        ) : hoiHuy ? (
          <XacNhanTaiCho
            cau="Huỷ lịch hẹn này để đặt lại?"
            nhanDongY="Huỷ lịch hẹn"
            onDongY={() => void huyLich()}
            onThoi={() => setHoiHuy(false)}
            dangGui={dangGui}
          />
        ) : (
          <Button size="sm" variant="secondary" onClick={() => setHoiHuy(true)}>
            Huỷ lịch để đặt lại
          </Button>
        )}
        {loi ? <BaoLoiCanhNut>{loi}</BaoLoiCanhNut> : null}
      </div>
    );
  }

  if (!ngayHopLe) return null;

  // ── Chưa đặt: bảng còn chỗ của đúng ngày tái khám ──────────────────────
  const chonCuaNgay = chon && chon.date === ngay ? chon : null;
  return (
    <div className="space-y-2 rounded-card border border-hairline bg-surface-muted px-3 py-2.5">
      <div>
        <p className="text-emph font-semibold text-ink">Đặt lịch hẹn tái khám — {ngayDai(ngay)}</p>
        <p className="text-meta text-ink-muted">
          Bấm ô của bác sĩ để chọn giờ. Ngày chưa có lịch trực thì chọn hàng “Chưa phân bác sĩ” —
          CSKH phân bác sĩ khi có lịch trực.
          {dichVu ? ` Dịch vụ: ${dichVu}.` : ""}
        </p>
      </div>
      <BangBacSiTuan
        weekStart={thuHaiCua(ngay)}
        chiNgay={ngay}
        lamMoi={lan}
        homNay={homNay}
        bayGioPhut={phutVn(bayGio)}
        chon={chonCuaNgay}
        onChonKhung={(v) => {
          setChon(v);
          setLoi(null);
        }}
      />
      {chonCuaNgay ? (
        <div className="flex flex-wrap items-center gap-2">
          <p className="w-full text-body text-ink sm:w-auto sm:min-w-0 sm:flex-1">
            Đã chọn{" "}
            <span className="font-semibold tabular-nums">
              {chonCuaNgay.time}–{cong(chonCuaNgay.time, chonCuaNgay.thongTin.khung?.slot_minutes ?? 15)}
            </span>{" "}
            · {chonCuaNgay.doctorId ? chonCuaNgay.doctorName : "Chưa phân bác sĩ"}
          </p>
          <Button variant="primary" onClick={() => void datLich()} disabled={dangGui}>
            {dangGui ? "Đang đặt…" : "Đặt lịch hẹn"}
          </Button>
          <Button variant="ghost" onClick={() => setChon(null)} disabled={dangGui}>
            Bỏ chọn
          </Button>
        </div>
      ) : null}
      {loi ? <BaoLoiCanhNut>{loi}</BaoLoiCanhNut> : null}
    </div>
  );
}
