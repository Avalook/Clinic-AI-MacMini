"use client";

// PHIẾU THU kiểu HOÁ ĐƠN — khổ giấy máy in nhiệt 80mm (Tuyền 28/09/2026: "chỉ
// có phiếu thuốc và phiếu dịch vụ là kiểu hoá đơn thôi, còn kết quả các thứ
// phải là cỡ A4"). Một trang cho cả thu tiền DỊCH VỤ lẫn tiền THUỐC (`kind`),
// và phiếu hoàn. Phiếu khám, kết quả dùng `KieuInA4`.
//
// PHIẾU HƯỚNG DẪN (`loai=huong_dan`, Tuyền 30/09/2026): khách làm trước, thu
// sau — chưa có tiền nhưng vẫn cần tờ giấy ghi đi phòng nào. Cùng khổ, cùng
// trang; `id` là mã LƯỢT, không có dòng tiền.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { tenHinhThuc, type PhanThu } from "@/lib/hinh-thuc-thu";

import DoiPhong from "../../../(dashboard)/_lam-viec/DoiPhong";

export interface Phieu {
  /** Mã gốc của lần thu / lần hoàn. */
  id: string;
  loai: LoaiPhieu;
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
  dong: {
    ten: string;
    so_luong: number;
    thanh_tien: number | null;
    /** Lần chỉ định (06/10/2026) — "Lần k"; null = tiền khám / mang sang. */
    lan?: number | null;
    /** Chỉ định đã bỏ sau khi thu — in lại ghi "đã bỏ", không in phòng. */
    da_bo?: boolean;
    /** Phòng làm dịch vụ — in cho khách đi theo (30/09/2026). Chỉ dòng dịch vụ.
     *  Chỉ in TÊN PHÒNG, không in tầng (Tuyền 30/09/2026). */
    phong?: {
      ten: string;
      tang: string | number | null;
      du_kien: boolean;
      /** Bác sĩ quầy chọn trong phòng nhiều bác sĩ ("BS X") — 30/09/2026. */
      bac_si?: string | null;
    } | null;
    /** Vừa thu, máy chủ chưa xếp xong phòng (chạy nền) — bản in hỏi lại sau giây lát. */
    cho_xep?: boolean;
    /** Xếp / đổi phòng ngay trên trang phiếu (quên chọn phòng lúc thu). */
    order_id?: string;
    room_id?: string | null;
    routing_revision?: number | null;
    doi_phong_duoc?: boolean;
  }[];
  tong: number;
  hinh_thuc: string | null;
  /** Từng phần theo hình thức (01/10/2026: một lần thu = Tiền mặt + Chuyển khoản).
   *  Phiếu in mỗi phần một dòng. Máy chủ cũ không gửi → rơi về `hinh_thuc`. */
  phan?: PhanThu[];
  /** Tiền thừa trả khách (khách đưa − phần tiền mặt) — chỉ in, không vào sổ. */
  tra_lai?: number | null;
  nguoi_thu: string | null;
  ly_do: string | null;
  doi_tac: { ten: string; gia: number | null }[];
}

export type LoaiPhieu = "thu" | "hoan" | "huong_dan";


// Khổ hoá đơn 80mm, dài theo nội dung. `@page` chỉ áp cho trang in này.
export const KIEU_HOA_DON = `
@page { size: 80mm auto; margin: 4mm 3mm; }
@media print {
  html, body { background: white; }
}
`;

function tien(n: number): string {
  return n.toLocaleString("vi-VN") + "đ";
}

export default function InPhieuThu({ id, loai }: { id: string; loai: LoaiPhieu }) {
  const [p, setP] = useState<Phieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  // Tăng lên sau mỗi lần đổi phòng → nạp lại phiếu để in bản mới.
  const [lanNap, setLanNap] = useState(0);

  useEffect(() => {
    let huy = false;
    void (async () => {
      // Thu xong máy chủ mới xếp phòng (vài giây, chạy nền). Bill mở ngay lúc ấy
      // có thể chưa có phòng → hỏi lại tối đa 4 lần, cách 1,5 giây.
      for (let lan = 0; lan < 5; lan++) {
        const r = await fetch(`/api/cashier?xem=phieu&id=${encodeURIComponent(id)}&loai=${loai}`, {
          cache: "no-store",
        });
        const d = (await r.json().catch(() => null)) as (Phieu & { message?: string; error?: string }) | null;
        if (huy) return;
        if (!r.ok || !d) {
          setLoi(d?.message ?? d?.error ?? "Không đọc được phiếu.");
          return;
        }
        setP(d);
        if (!d.dong.some((x) => x.cho_xep) || lan === 4) return;
        await new Promise((ok) => setTimeout(ok, 1500));
        if (huy) return;
      }
    })();
    return () => {
      huy = true;
    };
  }, [id, loai, lanNap]);

  if (loi) return <p className="p-8 text-body text-danger">{loi}</p>;
  if (!p) return <p className="p-8 text-body text-ink-muted">Đang tải phiếu…</p>;

  return (
    <main className="mx-auto w-full max-w-xs bg-surface p-4 text-body text-ink print:max-w-none print:p-0">
      <style>{KIEU_HOA_DON}</style>
      <div className="mb-4 flex gap-2 print:hidden">
        <Button variant="primary" onClick={() => window.print()}>
          In
        </Button>
        <Button variant="ghost" onClick={() => window.close()}>
          Đóng
        </Button>
      </div>
      <XepPhongTrenPhieu p={p} onDaDoi={() => setLanNap((n) => n + 1)} />
      <PhieuThuGiay p={p} />
    </main>
  );
}

/** XẾP / ĐỔI PHÒNG ngay trên trang phiếu (Tuyền 30/09/2026: "in ra mà quên
 *  chưa chọn phòng thì cho họ đổi phòng rồi in lại"). Chỉ hiện trên màn hình,
 *  không in. Dùng lại khối `DoiPhong` của Bàn khám / quầy thu — máy chủ quyết
 *  phòng nào làm được và gác lệnh xếp. */
function XepPhongTrenPhieu({ p, onDaDoi }: { p: Phieu; onDaDoi: () => void }) {
  const ds = p.dong.filter((d) => d.order_id && d.doi_phong_duoc);
  if (p.loai === "hoan" || ds.length === 0) return null;
  return (
    <section className="mb-4 space-y-2 rounded-card border border-line p-3 print:hidden">
      <p className="text-meta font-semibold text-ink">Phòng làm dịch vụ — chọn / đổi rồi bấm In</p>
      <ul className="space-y-2">
        {ds.map((d) => (
          <li key={d.order_id}>
            <p className="text-meta text-ink">
              {d.ten}
              <span className={d.phong ? "text-ink-muted" : "text-warning"}>
                {" "}
                · {d.phong ? `${d.phong.ten}${d.phong.bac_si ? ` · ${d.phong.bac_si}` : ""}` : "vui lòng chọn phòng"}
              </span>
            </p>
            <DoiPhong
              orderId={d.order_id as string}
              phongHienTaiId={d.room_id ?? null}
              routingRevision={d.routing_revision ?? null}
              choDoi
              onDaDoi={onDaDoi}
              nguon="quay_thu"
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Thân MỘT phiếu thu khổ hoá đơn — dùng chung cho in một phiếu và in mọi
 *  hoá đơn thuốc của một lượt (CSKH, 28/09/2026). */
export function PhieuThuGiay({ p }: { p: Phieu }) {
  if (p.loai === "huong_dan") return <PhieuHuongDanGiay p={p} />;
  const phanCo = (p.phan ?? []).filter((ph) => ph.hinh_thuc);
  const khachDua = phanCo.find((ph) => ph.hinh_thuc === "CASH")?.khach_dua ?? null;
  const luc = p.luc
    ? new Date(p.luc).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })
    : "";
  const soLuot = [p.so_booking != null ? `#${p.so_booking}` : null, p.so_tiep_don != null ? String(p.so_tiep_don) : null]
    .filter(Boolean)
    .join(" · ");

  return (
    <>
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
                {d.lan ? ` · Lần ${d.lan}` : ""}
                {d.da_bo ? " · đã bỏ" : ""}
                {d.phong ? (
                  <span className="block font-semibold">
                    → {d.phong.ten}
                    {d.phong.bac_si ? ` · ${d.phong.bac_si}` : ""}
                    {d.phong.du_kien ? " (dự kiến)" : ""}
                  </span>
                ) : d.cho_xep ? (
                  <span className="block text-ink-muted">→ Chờ xếp phòng — xem màn hình gọi số</span>
                ) : null}
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
        {phanCo.length > 1 ? (
          phanCo.map((ph, i) => (
            <div key={i} className="contents">
              <dt className="text-ink-muted">{tenHinhThuc(ph.hinh_thuc)}</dt>
              <dd className="text-right tabular-nums">{tien(ph.so_tien)}</dd>
            </div>
          ))
        ) : (
          <>
            <dt className="text-ink-muted">Hình thức</dt>
            <dd>{tenHinhThuc(phanCo[0]?.hinh_thuc ?? p.hinh_thuc) || "—"}</dd>
          </>
        )}
        {khachDua != null && p.tra_lai ? (
          <>
            <dt className="text-ink-muted">Khách đưa</dt>
            <dd className="text-right tabular-nums">{tien(khachDua)}</dd>
            <dt className="text-ink-muted">Trả lại khách</dt>
            <dd className="text-right tabular-nums">{tien(p.tra_lai)}</dd>
          </>
        ) : null}
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
          Dịch vụ thu hộ đối tác (không cộng vào phiếu thu này):{" "}
          {p.doi_tac
            .map((d) => `${d.ten}${d.gia != null ? ` — tham khảo ${tien(d.gia)}` : ""}`)
            .join("; ")}
        </p>
      ) : null}
      <p className="mt-6 text-center text-meta text-ink-muted">Cảm ơn quý khách</p>
    </>
  );
}

/** PHIẾU HƯỚNG DẪN — dịch vụ khách đã chốt + phòng đi làm, KHÔNG tiền. Khách
 *  làm trước, thu sau: cuối buổi quay lại quầy thanh toán (Tuyền 30/09/2026). */
function PhieuHuongDanGiay({ p }: { p: Phieu }) {
  const luc = p.luc
    ? new Date(p.luc).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" })
    : "";
  const soLuot = [p.so_booking != null ? `#${p.so_booking}` : null, p.so_tiep_don != null ? String(p.so_tiep_don) : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <>
      <header className="text-center">
        <p className="font-semibold uppercase">{p.phong_kham ?? "Phòng khám"}</p>
        <p className="text-meta text-ink-muted">
          {[p.co_so, p.dia_chi].filter(Boolean).join(" · ")}
        </p>
        <h1 className="mt-3 text-emph font-semibold">PHIẾU HƯỚNG DẪN LÀM DỊCH VỤ</h1>
        <p className="text-meta text-ink-muted">{luc}</p>
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
      {p.dong.length === 0 ? (
        <p className="mt-4 text-meta text-ink-muted">Không còn dịch vụ nào chờ làm.</p>
      ) : (
        <ol className="mt-4 space-y-1 text-meta">
          {p.dong.map((d, i) => (
            <li key={d.order_id ?? i} className="border-b border-line py-1">
              {i + 1}. {d.ten}
              {d.phong ? (
                <span className="block font-semibold">
                  → {d.phong.ten}
                  {d.phong.bac_si ? ` · ${d.phong.bac_si}` : ""}
                  {d.phong.du_kien ? " (dự kiến)" : ""}
                </span>
              ) : (
                <span className="block text-ink-muted">→ Chờ xếp phòng — xem màn hình gọi số</span>
              )}
            </li>
          ))}
        </ol>
      )}
      <p className="mt-4 text-center font-semibold">CHƯA THANH TOÁN</p>
      <p className="text-center text-meta">Làm xong, mời quý khách quay lại quầy lễ tân để thanh toán.</p>
    </>
  );
}
