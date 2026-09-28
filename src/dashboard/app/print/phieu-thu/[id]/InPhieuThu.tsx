"use client";

// PHIẾU THU kiểu HOÁ ĐƠN — khổ giấy máy in nhiệt 80mm (Tuyền 28/09/2026: "chỉ
// có phiếu thuốc và phiếu dịch vụ là kiểu hoá đơn thôi, còn kết quả các thứ
// phải là cỡ A4"). Một trang cho cả thu tiền DỊCH VỤ lẫn tiền THUỐC (`kind`),
// và phiếu hoàn. Phiếu khám, kết quả dùng `KieuInA4`.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";

interface Phieu {
  loai: "thu" | "hoan";
  /** Lần thu tiền dịch vụ hay tiền thuốc. */
  kind: string | null;
  ma: string;
  ma_phieu_goc: string | null;
  luc: string | null;
  trang_thai: string | null;
  phong_kham: string | null;
  co_so: string | null;
  dia_chi: string | null;
  khach: string | null;
  ma_bn: string | null;
  so_booking: number | null;
  so_tiep_don: number | null;
  bac_si: string | null;
  dong: { ten: string; so_luong: number; thanh_tien: number | null }[];
  tong: number;
  hinh_thuc: string | null;
  nguoi_thu: string | null;
  ly_do: string | null;
  doi_tac: { ten: string; gia: number | null }[];
}

const TEN_PT: Record<string, string> = { CASH: "Tiền mặt", TRANSFER: "Chuyển khoản", QR: "QR" };

// Khổ hoá đơn 80mm, dài theo nội dung. `@page` chỉ áp cho trang in này.
const KIEU_HOA_DON = `
@page { size: 80mm auto; margin: 4mm 3mm; }
@media print {
  html, body { background: white; }
}
`;

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

export default function InPhieuThu({ id, loai }: { id: string; loai: "thu" | "hoan" }) {
  const [p, setP] = useState<Phieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    void (async () => {
      const r = await fetch(`/api/cashier?xem=phieu&id=${encodeURIComponent(id)}&loai=${loai}`, {
        cache: "no-store",
      });
      const d = (await r.json().catch(() => null)) as (Phieu & { message?: string; error?: string }) | null;
      if (huy) return;
      if (!r.ok || !d) setLoi(d?.message ?? d?.error ?? "Không đọc được phiếu.");
      else setP(d);
    })();
    return () => {
      huy = true;
    };
  }, [id, loai]);

  if (loi) return <p className="p-8 text-body text-danger">{loi}</p>;
  if (!p) return <p className="p-8 text-body text-ink-muted">Đang tải phiếu…</p>;

  const luc = p.luc
    ? new Date(p.luc).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })
    : "";
  const soLuot = [p.so_booking != null ? `#${p.so_booking}` : null, p.so_tiep_don != null ? String(p.so_tiep_don) : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <main className="mx-auto max-w-xs bg-surface p-4 text-body text-ink print:max-w-none print:p-0">
      <style>{KIEU_HOA_DON}</style>
      <div className="mb-4 flex gap-2 print:hidden">
        <Button variant="primary" onClick={() => window.print()}>
          In
        </Button>
        <Button variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      <header className="text-center">
        <p className="font-semibold uppercase">{p.phong_kham ?? "Phòng khám"}</p>
        <p className="text-meta text-ink-muted">
          {[p.co_so, p.dia_chi].filter(Boolean).join(" · ")}
        </p>
        <h1 className="mt-3 text-emph font-semibold">
          {p.loai === "hoan"
            ? "PHIẾU HOÀN TIỀN"
            : p.kind === "thuoc"
              ? "PHIẾU THU TIỀN THUỐC"
              : "PHIẾU THU TIỀN DỊCH VỤ"}
        </h1>
        <p className="text-meta text-ink-muted">
          {p.ma} · {luc}
          {p.ma_phieu_goc ? ` · theo phiếu ${p.ma_phieu_goc}` : ""}
        </p>
      </header>
      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-meta">
        <dt className="text-ink-muted">Khách</dt>
        <dd>{p.khach ?? "—"}</dd>
        <dt className="text-ink-muted">Mã khách</dt>
        <dd>{p.ma_bn ?? "—"}</dd>
        {soLuot ? (
          <>
            <dt className="text-ink-muted">Booking · Check-in</dt>
            <dd>{soLuot}</dd>
          </>
        ) : null}
        {p.bac_si ? (
          <>
            <dt className="text-ink-muted">Bác sĩ</dt>
            <dd>{p.bac_si}</dd>
          </>
        ) : null}
      </dl>
      <table className="mt-4 w-full text-meta">
        <tbody>
          {p.dong.map((d, i) => (
            <tr key={i} className="border-b border-line">
              <td className="py-1">
                {d.ten}
                {d.so_luong !== 1 ? ` × ${d.so_luong}` : ""}
              </td>
              <td className="py-1 text-right tabular-nums">
                {d.thanh_tien != null ? d.thanh_tien.toLocaleString("vi-VN") : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-3 flex justify-between font-semibold">
        <span>{p.loai === "hoan" ? "TỔNG HOÀN" : "TỔNG THU"}</span>
        <span className="tabular-nums">{tien(Math.abs(p.tong))}</span>
      </p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-meta">
        <dt className="text-ink-muted">Hình thức</dt>
        <dd>{p.hinh_thuc ? (TEN_PT[p.hinh_thuc] ?? p.hinh_thuc) : "—"}</dd>
        <dt className="text-ink-muted">Người thu</dt>
        <dd>{p.nguoi_thu ?? "—"}</dd>
        {p.ly_do ? (
          <>
            <dt className="text-ink-muted">Lý do</dt>
            <dd>{p.ly_do}</dd>
          </>
        ) : null}
      </dl>
      {p.doi_tac.length > 0 ? (
        <p className="mt-3 text-meta text-ink-muted">
          Dịch vụ khách trả trực tiếp đối tác (không thu tại đây):{" "}
          {p.doi_tac
            .map((d) => `${d.ten}${d.gia != null ? ` — tham khảo ${tien(d.gia)}` : ""}`)
            .join("; ")}
        </p>
      ) : null}
      <p className="mt-6 text-center text-meta text-ink-muted">Cảm ơn quý khách</p>
    </main>
  );
}
