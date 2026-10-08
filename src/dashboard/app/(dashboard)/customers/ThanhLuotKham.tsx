"use client";

// THANH CHỌN LƯỢT KHÁM — đầu cột giữa (Tuyền duyệt 16/09/2026).
//
// Mỗi lượt là một ô nằm ngang trên MỘT DẢI THEO THỜI GIAN (Tuyền chốt 08/10/2026
// — trước đó gom chuỗi theo dịch vụ / `lich_truoc_id`, nên hai lượt cùng ngày
// của hai dịch vụ đều là "Lần đầu"). Ô: ngày · nhãn máy chủ đếm ("Lượt khám 2",
// "Buổi 3/10", "Điều trị · buổi lẻ", "Lịch hẹn", "Đã huỷ") · tên dịch vụ ·
// trạng thái. Chấm đỏ = lượt còn việc CSKH đang mở.
//
// Dải dựng sẵn ở page.tsx; số do máy chủ (`nhan_luot`) — ở đây chỉ vẽ.

import { useState } from "react";
import { FileText } from "lucide-react";
import HoSoKhamModal from "../_lam-viec/HoSoKham";
import LichSuKham from "../_lam-viec/LichSuKham";
import { chipBuoiPhu, chuNhanLuot } from "@/lib/nhan-luot";

import type { ChuoiKham, LuotKham } from "./CustomersView";

const NHAN_TRANG_THAI: Record<string, string> = {
  SCHEDULED: "sắp tới",
  CSKH_CONFIRMED: "sắp tới",
  CONFIRMED: "sắp tới",
  CHECKED_IN: "đang khám",
  COMPLETED: "khám xong",
  CANCELLED: "đã huỷ",
  NO_SHOW: "không đến",
  DOCTOR_DECLINED: "chưa phân bác sĩ",
};

function ngay(iso: string): string {
  return new Date(iso).toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

function dangMo(l: LuotKham): boolean {
  return ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"].includes(
    l.status,
  );
}

export default function ThanhLuotKham({
  chuoi,
  luotDangXem,
  luotConViec,
  onChonLuot,
  clinicPatientId,
}: {
  chuoi: ChuoiKham[];
  luotDangXem: string | null;
  /** id các lượt còn việc CSKH đang mở. */
  luotConViec: ReadonlySet<string>;
  onChonLuot: (id: string) => void;
  /** Có thì hiện nút "Lịch sử khám" (mọi lượt, cả không phiếu / Notion). */
  clinicPatientId?: string;
}) {
  const [xemHoSo, setXemHoSo] = useState(false);
  /** Lịch hẹn của lượt bấm trong popup Lịch sử khám → mở hồ sơ CSKH. */
  const [hoSoId, setHoSoId] = useState<string | null>(null);
  const [loiIn, setLoiIn] = useState<string | null>(null);
  const luotChon = chuoi
    .flatMap((c) => c.luot)
    .find((l) => l.id === luotDangXem);
  // Hồ sơ khám chỉ có từ lúc khách đã vào khám (check-in trở đi).
  const coHoSo =
    luotChon?.status === "CHECKED_IN" || luotChon?.status === "COMPLETED";
  // IN PDF TRẢ KHÁCH theo từng ngày khám (Tuyền 28/09/2026 — "in ra toàn bộ
  // thông tin cho khách"): PHIẾU KHÁM ĐẦY ĐỦ (cả quá trình khám như màn bác sĩ,
  // `/print/phieu-kham`) · MỌI PHIẾU KẾT QUẢ siêu âm / thủ thuật / xét nghiệm
  // kèm ảnh (`/print/ket-qua-luot`) · HOÁ ĐƠN THUỐC (`/print/hoa-don-thuoc`, khổ
  // 80mm). Mở tab NGAY lúc bấm (trình duyệt chặn cửa sổ mở sau một vòng mạng),
  // rồi mới hỏi máy chủ mã lượt khám.
  async function moIn(appointmentId: string, trang: "phieu-kham" | "ket-qua-luot" | "hoa-don-thuoc") {
    setLoiIn(null);
    const tab = window.open("", "_blank");
    const r = await fetch(`/api/cskh/ho-so-kham/${appointmentId}`, { cache: "no-store" })
      .then(async (x) => (x.ok ? ((await x.json()) as { luot?: { visit_id?: string } }) : null))
      .catch(() => null);
    const vid = r?.luot?.visit_id;
    if (!vid) {
      tab?.close();
      setLoiIn("Lượt này chưa có hồ sơ khám để in.");
      return;
    }
    const duong = `/print/${trang}/${vid}`;
    // Trình duyệt chặn mở tab → mở ở đây (bấm Quay lại để về màn CSKH).
    if (tab) tab.location.href = duong;
    else window.location.assign(duong);
  }
  if (chuoi.length === 0) {
    return (
      <p className="mt-1 text-label text-ink-muted">
        Khách chưa có lượt khám nào.
      </p>
    );
  }
  return (
    <>
      <div
        role="tablist"
        aria-label="Các lượt khám của khách"
        className="mt-2 flex gap-3 overflow-x-auto pb-1"
      >
        {chuoi.flatMap((c) => c.luot).map((l) => {
          const chon = l.id === luotDangXem;
          const buoiPhu = chipBuoiPhu(l.nhan_luot);
          return (
            <button
              key={l.id}
              type="button"
              role="tab"
              aria-selected={chon}
              onClick={() => onChonLuot(l.id)}
              className={`relative max-w-48 shrink-0 rounded-control px-2.5 py-1.5 text-left text-label ring-1 ring-inset ${
                chon
                  ? "bg-brand-600 font-semibold text-white ring-brand-600"
                  : dangMo(l)
                    ? "bg-surface text-ink ring-brand-300 hover:bg-brand-50"
                    : "bg-surface-muted text-ink-soft ring-line hover:bg-surface-sunken"
              }`}
            >
              {luotConViec.has(l.id) && (
                <span
                  aria-label="còn việc chưa xong"
                  className="absolute -right-1 -top-1 size-2.5 rounded-full bg-danger ring-2 ring-surface"
                />
              )}
              <span className="block tabular-nums">{ngay(l.bat_dau ?? l.slot_start)}</span>
              <span className="block font-semibold">
                {chuNhanLuot(l.nhan_luot, l.status === "CANCELLED" ? "Đã huỷ" : "Lượt")}
                {buoiPhu ? ` · ${buoiPhu}` : ""}
              </span>
              <span className="block truncate">{l.service_name ?? "Chưa chọn dịch vụ"}</span>
              {l.status !== "CANCELLED" ? (
                <span className="block">{NHAN_TRANG_THAI[l.status] ?? l.status}</span>
              ) : null}
            </button>
          );
        })}
      </div>
      {luotChon && coHoSo && (
        <button
          type="button"
          onClick={() => setXemHoSo(true)}
          className="mt-2 inline-flex items-center gap-1.5 rounded-control bg-brand-50 px-3 py-1.5 text-sm font-semibold text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-100"
        >
          <FileText className="size-4" aria-hidden="true" />
          Xem hồ sơ khám lượt {ngay(luotChon.bat_dau ?? luotChon.slot_start)}
        </button>
      )}
      {luotChon && coHoSo && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-label text-ink-muted">In PDF trả khách:</span>
          {(
            [
              ["phieu-kham", "Phiếu khám đầy đủ"],
              ["ket-qua-luot", "Kết quả + ảnh"],
              ["hoa-don-thuoc", "Hoá đơn thuốc"],
            ] as const
          ).map(([trang, nhan]) => (
            <button
              key={trang}
              type="button"
              onClick={() => void moIn(luotChon.id, trang)}
              className="inline-flex min-h-10 items-center gap-1.5 rounded-control bg-surface px-3 py-1.5 text-sm font-semibold text-brand-700 ring-1 ring-inset ring-brand-300 hover:bg-brand-50"
            >
              <FileText className="size-4" aria-hidden="true" />
              {nhan}
            </button>
          ))}
          {loiIn ? <span className="text-label text-danger">{loiIn}</span> : null}
        </div>
      )}
      {clinicPatientId ? (
        <div className="mt-2">
          <LichSuKham
            clinicPatientId={clinicPatientId}
            onChonLuot={(l) => {
              if (!l.appointment_id) return false;
              setHoSoId(l.appointment_id);
              return true;
            }}
          />
        </div>
      ) : null}
      {hoSoId ? <HoSoKhamModal appointmentId={hoSoId} onDong={() => setHoSoId(null)} /> : null}
      {xemHoSo && luotChon && (
        <HoSoKhamModal
          appointmentId={luotChon.id}
          onDong={() => setXemHoSo(false)}
        />
      )}
    </>
  );
}
