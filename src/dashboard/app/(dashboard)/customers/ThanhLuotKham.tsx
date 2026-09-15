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
  return ["SCHEDULED", "CSKH_CONFIRMED", "CONFIRMED", "CHECKED_IN"].includes(l.status);
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
  if (chuoi.length === 0) {
    return <p className="mt-1 text-label text-ink-muted">Khách chưa có lượt khám nào.</p>;
  }
  return (
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
                    <span className="block tabular-nums">{ngay(l.slot_start)}</span>
                    <span className="block">
                      {j === 0 ? "Lần đầu" : `Tái khám ${j}`} ·{" "}
                      {NHAN_TRANG_THAI[l.status] ?? l.status}
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
  );
}
