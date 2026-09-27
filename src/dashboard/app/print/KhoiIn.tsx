// HAI KHỐI ĐẦU TRANG dùng chung cho bản in phiếu khám và phiếu kết quả
// (27/09/2026 — Y HỆT bản giao diện mẫu, `in-dau` + `in-bn` của M/style.css).
//
//   DauTrangIn   — đầu trang HAI BÊN: trái tên phòng khám + cơ sở / địa chỉ;
//                  phải tên phiếu + mã, số booking / check-in, ngày. Kẻ đậm dưới.
//   KhoiBenhNhanIn — khối BỆNH NHÂN gọn: nhãn | giá trị, hai cặp một hàng (một
//                  cặp ở màn hẹp); dòng không có giá trị thì BỎ, không in "—".
//
// Chỉ vẽ: mọi giá trị do máy chủ trả (`dau-phieu`, `/api/phieu?in=`).

import type { ReactNode } from "react";

export function DauTrangIn({
  phongKham,
  trai,
  tieuDe,
  phai,
}: {
  phongKham: string | null | undefined;
  /** Dòng phụ bên trái (cơ sở, địa chỉ) — dòng rỗng tự bỏ. */
  trai: (string | null | undefined)[];
  tieuDe: string;
  /** Dòng phụ bên phải (mã, booking / check-in, ngày) — dòng rỗng tự bỏ. */
  phai: (ReactNode | null | undefined)[];
}) {
  const dongTrai = trai.filter((x): x is string => Boolean(x && x.trim()));
  const dongPhai = phai.filter((x) => x !== null && x !== undefined && x !== "");
  return (
    <header className="flex flex-wrap justify-between gap-x-4 gap-y-2 border-b-2 border-ink pb-3">
      <div className="min-w-0">
        <p className="font-semibold uppercase text-ink">{phongKham || "Phòng khám"}</p>
        {dongTrai.map((d) => (
          <p key={d} className="text-meta text-ink-muted">
            {d}
          </p>
        ))}
      </div>
      <div className="min-w-0 text-right">
        <h1 className="font-semibold uppercase text-ink">{tieuDe}</h1>
        {dongPhai.map((d, i) => (
          <p key={i} className="text-meta text-ink-muted">
            {d}
          </p>
        ))}
      </div>
    </header>
  );
}

export interface DongBenhNhan {
  nhan: string;
  gia: ReactNode | null | undefined;
  /** Chiếm trọn một hàng (địa chỉ dài, chẩn đoán…). */
  rong?: boolean;
}

export function KhoiBenhNhanIn({ dong, tieuDe }: { dong: DongBenhNhan[]; tieuDe?: string }) {
  const co = dong.filter((d) => d.gia !== null && d.gia !== undefined && d.gia !== "");
  if (co.length === 0) return null;
  return (
    <section className="in-giu mt-3">
      {tieuDe ? <h2 className="mb-1 font-semibold text-ink">{tieuDe}</h2> : null}
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 sm:grid-cols-[auto_minmax(0,1fr)_auto_minmax(0,1fr)] print:grid-cols-[auto_minmax(0,1fr)_auto_minmax(0,1fr)]">
        {co.map((d) => (
          // Dòng rộng bắt đầu ở cột đầu (col-start-1) để khỏi bị đẩy lệch hàng.
          <div key={d.nhan} className="contents">
            <dt className={`text-ink-muted ${d.rong ? "sm:col-start-1 print:col-start-1" : ""}`}>
              {d.nhan}
            </dt>
            <dd
              className={`whitespace-pre-wrap ${d.rong ? "sm:col-span-3 print:col-span-3" : ""}`}
            >
              {d.gia}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/** "2026-09-25" (hoặc ISO có giờ) → "25/09/2026". Không đọc được thì trả nguyên. */
export function ngayIn(iso: string | number | null | undefined): string | null {
  if (iso === null || iso === undefined || iso === "") return null;
  if (typeof iso === "number") return String(iso);
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (m) return `${m[3]}/${m[2]}/${m[1]}`;
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" });
}

/** ISO → "HH:MM" giờ phòng khám. */
export function gioIn(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? null
    : d.toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
        timeZone: "Asia/Ho_Chi_Minh",
      });
}

/** Số booking / check-in thành một dòng; không có số nào thì null. */
export function dongSoLuot(
  booking: number | null | undefined,
  checkin: number | null | undefined,
): string | null {
  const ds = [
    booking != null ? `Booking #${booking}` : null,
    checkin != null ? `Check-in ${checkin}` : null,
  ].filter(Boolean);
  return ds.length ? ds.join(" · ") : null;
}
