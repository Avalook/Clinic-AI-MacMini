"use client";

// HÀNH TRÌNH HÔM NAY ở đầu phiếu khám (lát 5, 26/09/2026 — bản giao diện mẫu).
//
// Mốc do máy chủ tính (`GET /api/phieu-kham?visit_id&xem=hanh-trinh`, cùng quyền
// đọc phiếu); ở đây chỉ vẽ và đếm giờ. 27/09/2026: tông Y HỆT bản mẫu + bảng
// "Từng dịch vụ" (`tung_dich_vu` — mỗi chỉ định gửi → thu → bắt đầu → xong). Nghe chung dòng tin của RealtimeRefresher
// (không mở kết nối riêng): có tin về hành trình / hàng chờ / chỉ định / thu tiền
// thì nạp lại; mỗi 30 giây vẽ lại để "đang 12 phút" không đứng yên.

import { useEffect, useState } from "react";

import Chip, { type ChipTone } from "@/components/ui/Chip";
import NganGap from "@/components/ui/NganGap";
import Timeline from "@/components/ui/Timeline";
import {
  doanNoi,
  gioMoc,
  khoang,
  phutDichVu,
  type DichVuHanhTrinh,
  type HanhTrinh,
  type TrangThaiDichVu,
} from "@/lib/hanh-trinh";
import { SU_KIEN_BANG } from "@/lib/nhip-lam-moi";

const BANG = new Set([
  "luot_dong_thoi_gian",
  "queue_entry",
  "service_order",
  "payment",
  "visit",
  "consultation",
]);

export default function HanhTrinhLuot({ visitId }: { visitId: string }) {
  const [ht, setHt] = useState<HanhTrinh | null>(null);
  const [bayGio, setBayGio] = useState(() => Date.now());
  const [lanNap, setLanNap] = useState(0);

  useEffect(() => {
    let huy = false;
    void fetch(`/api/phieu-kham?visit_id=${visitId}&xem=hanh-trinh`, { cache: "no-store" })
      .then(async (r) => (r.ok ? ((await r.json().catch(() => null)) as HanhTrinh | null) : null))
      .catch(() => null)
      .then((d) => {
        if (huy || !d) return;
        setHt(d);
        setBayGio(Date.now());
      });
    return () => {
      huy = true;
    };
  }, [visitId, lanNap]);

  useEffect(() => {
    let hen: ReturnType<typeof setTimeout> | undefined;
    const khiBangDoi = (ev: Event) => {
      const bang = (ev as CustomEvent<string | null>).detail;
      if (bang !== null && !BANG.has(bang)) return;
      if (document.visibilityState === "hidden") return;
      clearTimeout(hen);
      hen = setTimeout(() => setLanNap((n) => n + 1), 400);
    };
    window.addEventListener(SU_KIEN_BANG, khiBangDoi);
    const dongHo = setInterval(() => setBayGio(Date.now()), 30_000);
    return () => {
      clearTimeout(hen);
      clearInterval(dongHo);
      window.removeEventListener(SU_KIEN_BANG, khiBangDoi);
    };
  }, []);

  if (!ht) return null;
  const tung = ht.tung_dich_vu ?? [];
  // Bảng mở sẵn khi còn dịch vụ đang chờ / đang làm (bản mẫu) — gập khi xong hết.
  const moSan = tung.some((d) => d.trang_thai === "CHO_LAM" || d.trang_thai === "DANG_LAM");
  return (
    <section
      aria-label="Hành trình hôm nay"
      className="rounded-card border border-hairline bg-surface p-4 print:hidden"
    >
      <Timeline
        nhanAria="Hành trình hôm nay"
        dau={
          <>
            <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
              Hành trình hôm nay
            </p>
            {/* Câu do máy chủ viết sẵn ("Đang ở …", "Chờ …", "Đã về") —
                cùng hàm với Bảng hành trình chung. */}
            <p className="flex flex-wrap items-center gap-2 text-body">
              <Chip tone="brand">Đang ở</Chip>
              <span className="font-semibold text-ink">{ht.dang_o}</span>
              {ht.ngoai_cho > 0 ? (
                <span className="text-meta text-ink-muted">
                  · {ht.ngoai_cho} việc đang ở đối tác
                </span>
              ) : null}
            </p>
          </>
        }
        moc={ht.moc.map((m) => ({
          khoa: m.ma,
          ten: m.ten,
          noi: m.noi || undefined,
          gio: gioMoc(m),
          trangThai: m.trang_thai,
        }))}
        doan={doanNoi(ht.moc, bayGio)}
      />
      {tung.length > 0 ? (
        // `key` theo moSan: có dịch vụ chuyển sang chờ/làm thì bảng tự mở lại,
        // xong hết thì tự thu (giữ đúng hành vi của `<details>` cũ).
        <div className="mt-3">
          <NganGap key={moSan ? "mo" : "gap"} moSan={moSan} tieuDe={`Từng dịch vụ (${tung.length})`}>
            <BangTungDichVu ds={tung} bayGio={bayGio} />
          </NganGap>
        </div>
      ) : null}
    </section>
  );
}

const TRANG_THAI: Record<TrangThaiDichVu, { nhan: string; tone: ChipTone }> = {
  CHO_THU: { nhan: "Chờ thu tiền", tone: "warning" },
  CHO_LAM: { nhan: "Đã thu — chờ làm", tone: "info" },
  DANG_LAM: { nhan: "Đang làm", tone: "run" },
  XONG: { nhan: "Xong", tone: "success" },
  BO: { nhan: "Khách không làm", tone: "neutral" },
};

/** Bảng "Từng dịch vụ": mỗi chỉ định chờ → bắt đầu → xong, số phút. Chỉ kẻ
 *  ngang; cuộn ngang TRONG thẻ ở màn hẹp (DESIGN.md §6, §7). */
function BangTungDichVu({ ds, bayGio }: { ds: DichVuHanhTrinh[]; bayGio: number }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-160 text-body">
        <thead>
          <tr className="border-b border-hairline bg-surface-muted text-left text-label font-semibold uppercase tracking-wide text-ink-muted">
            <th scope="col" className="px-2 py-2">Dịch vụ</th>
            <th scope="col" className="px-2 py-2">Làm ở</th>
            <th scope="col" className="px-2 py-2">Trạng thái</th>
            <th scope="col" className="px-2 py-2">Mốc</th>
            <th scope="col" className="px-2 py-2 text-right">Tổng</th>
          </tr>
        </thead>
        <tbody>
          {ds.map((d, i) => {
            const p = phutDichVu(d, bayGio);
            const tt = TRANG_THAI[d.trang_thai];
            const chi = [
              p.cho != null ? `chờ ${khoang(p.cho)}` : null,
              p.lam != null ? `${p.dangChay ? "đang làm" : "làm"} ${khoang(p.lam)}` : null,
            ].filter(Boolean);
            return (
              <tr key={d.id ?? i} className="border-b border-hairline align-top last:border-b-0">
                <td className="px-2 py-2 text-ink">
                  {d.ten}
                  {d.lan != null ? <span className="ml-1 text-meta text-ink-muted">· lần {d.lan}</span> : null}
                </td>
                <td className="px-2 py-2 text-meta text-ink-muted">{d.noi}</td>
                <td className="px-2 py-2">
                  <Chip tone={tt.tone}>{tt.nhan}</Chip>
                </td>
                <td className="px-2 py-2 text-meta tabular-nums text-ink-muted">
                  <p>{p.moc}</p>
                  {chi.length > 0 ? <p className="text-ink-soft">{chi.join(" · ")}</p> : null}
                </td>
                <td className="whitespace-nowrap px-2 py-2 text-right tabular-nums text-ink">
                  {p.tong != null ? khoang(p.tong) : <span className="text-ink-faint">—</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
