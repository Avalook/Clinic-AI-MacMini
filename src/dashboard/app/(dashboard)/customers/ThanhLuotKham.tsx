"use client";

// THANH CHỌN LƯỢT KHÁM — đầu cột giữa, gom theo ĐỢT (Tuyền duyệt 16/09/2026).
//
// Thay cho khối "Lịch sử các lần khám" tít dưới đáy vùng làm việc: muốn xem lượt
// khác phải cuộn xuống rồi bấm, còn dòng "Lượt đang xem" chỉ là chữ nhỏ. Nay mỗi
// lượt là một thẻ nằm ngang; thẻ nối nhau theo chuỗi tái khám (`lich_truoc_id`),
// nhìn là biết khách đang ở lần mấy của đợt nào. Chấm đỏ = lượt còn việc CSKH
// đang mở — không phải mở từng lượt mới biết sót.
//
// Chuỗi dựng sẵn ở page.tsx (ChuoiKham); ở đây chỉ vẽ.

import { useState } from "react";
import { FileText } from "lucide-react";
import HoSoKhamModal from "../_lam-viec/HoSoKham";
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
}: {
  chuoi: ChuoiKham[];
  luotDangXem: string | null;
  /** id các lượt còn việc CSKH đang mở. */
  luotConViec: ReadonlySet<string>;
  onChonLuot: (id: string) => void;
}) {
  const [xemHoSo, setXemHoSo] = useState(false);
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
        {chuoi.map((c, i) => {
          const dau = c.luot[0]!;
          const moDot = c.luot.some(dangMo);
          return (
            <div key={dau.id} className="shrink-0">
              <p className="mb-1 text-label font-semibold text-ink-muted">
                {dau.service_name ?? "Chưa chọn dịch vụ"}
                <span className="font-normal text-ink-faint">
                  {moDot ? " · đợt đang mở" : " · đã xong"}
                </span>
              </p>
              <div className="flex gap-1.5">
                {c.luot.map((l, j) => {
                  const chon = l.id === luotDangXem;
                  // Lịch ĐÃ HUỶ vẫn hiện (dấu vết) nhưng không ăn số lần khám:
                  // bác sĩ huỷ để đặt lại trên phiếu (02/10/2026) thì lịch mới
                  // vẫn là "Tái khám 1", không nhảy thành 2, 3.
                  const soLan = c.luot
                    .slice(0, j)
                    .filter((x) => x.status !== "CANCELLED").length;
                  return (
                    <button
                      key={l.id}
                      type="button"
                      role="tab"
                      aria-selected={chon}
                      onClick={() => onChonLuot(l.id)}
                      className={`relative rounded-control px-2.5 py-1.5 text-left text-label ring-1 ring-inset ${
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
                      <span className="block tabular-nums">
                        {ngay(l.slot_start)}
                      </span>
                      <span className="block">
                        {l.status === "CANCELLED"
                          ? "Đã huỷ"
                          : `${soLan === 0 ? "Lần đầu" : `Tái khám ${soLan}`} · ${NHAN_TRANG_THAI[l.status] ?? l.status}`}
                      </span>
                    </button>
                  );
                })}
              </div>
              {i < chuoi.length - 1 && <span className="sr-only">,</span>}
            </div>
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
          Xem hồ sơ khám lượt {ngay(luotChon.slot_start)}
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
      {xemHoSo && luotChon && (
        <HoSoKhamModal
          appointmentId={luotChon.id}
          onDong={() => setXemHoSo(false)}
        />
      )}
    </>
  );
}
