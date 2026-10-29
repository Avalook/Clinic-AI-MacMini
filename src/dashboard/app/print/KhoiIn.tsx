// HAI KHỐI ĐẦU TRANG dùng chung cho bản in phiếu khám và phiếu kết quả
// (27/09/2026 — Y HỆT bản giao diện mẫu, `in-dau` + `in-bn` của M/style.css).
//
//   DauTrangIn   — đầu trang: tên phòng khám, cơ sở, địa chỉ (nghiêng) và tên
//                  phiếu căn giữa; mã, số booking / check-in, ngày bên trái
//                  dưới đó (29/10/2026). Kẻ đậm dưới.
//   KhoiBenhNhanIn — khối BỆNH NHÂN gọn: nhãn | giá trị, hai cặp một hàng (một
//                  cặp ở màn hẹp); dòng không có giá trị thì BỎ, không in "—".
//
// Chỉ vẽ: mọi giá trị do máy chủ trả (`dau-phieu`, `/api/phieu?in=`).

import type { ReactNode } from "react";

export function DauTrangIn({
  phongKham,
  coSo,
  diaChi,
  tieuDe,
  phai,
}: {
  phongKham: string | null | undefined;
  coSo?: string | null;
  diaChi?: string | null;
  tieuDe: string;
  /** Mã, booking / check-in, ngày — dòng rỗng tự bỏ. */
  phai: (ReactNode | null | undefined)[];
}) {
  const dongPhai = phai.filter((x) => x !== null && x !== undefined && x !== "");
  // Tuyền 29/10/2026: tên phòng khám + tên phiếu CĂN GIỮA; địa chỉ in nghiêng,
  // ghi rõ "Địa chỉ:"; mã khách / booking / ngày khám dồn bên trái cho gọn.
  return (
    <header className="border-b-2 border-ink pb-3">
      <div className="text-center">
        <p className="font-semibold uppercase text-ink">{phongKham || "Phòng khám"}</p>
        {coSo?.trim() ? <p className="text-meta text-ink-muted">{coSo}</p> : null}
        {diaChi?.trim() ? <p className="text-meta italic text-ink-muted">Địa chỉ: {diaChi}</p> : null}
        <h1 className="mt-3 font-semibold uppercase text-ink">{tieuDe}</h1>
      </div>
      {dongPhai.length > 0 ? (
        <div className="mt-2 space-y-0.5">
          {dongPhai.map((d, i) => (
            <p key={i} className="text-meta text-ink-muted">
              {d}
            </p>
          ))}
        </div>
      ) : null}
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
