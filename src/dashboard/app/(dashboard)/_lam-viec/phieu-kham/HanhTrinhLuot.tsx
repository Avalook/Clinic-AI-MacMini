"use client";

// HÀNH TRÌNH HÔM NAY ở đầu phiếu khám (lát 5, 26/09/2026 — bản giao diện mẫu).
//
// Mốc do máy chủ tính (`GET /api/phieu-kham?visit_id&xem=hanh-trinh`, cùng quyền
// đọc phiếu); ở đây chỉ vẽ và đếm giờ. Nghe chung dòng tin của RealtimeRefresher
// (không mở kết nối riêng): có tin về hành trình / hàng chờ / chỉ định / thu tiền
// thì nạp lại; mỗi 30 giây vẽ lại để "đang 12 phút" không đứng yên.

import { useEffect, useState } from "react";

import Chip from "@/components/ui/Chip";
import Timeline from "@/components/ui/Timeline";
import { doanNoi, gioMoc, type HanhTrinh } from "@/lib/hanh-trinh";
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
  return (
    <section
      aria-label="Hành trình hôm nay"
      className="rounded-card border border-hairline bg-surface px-3 py-2 print:hidden"
    >
      <Timeline
        nhanAria="Hành trình hôm nay"
        dau={
          <p className="flex flex-wrap items-center gap-2 text-body">
            <span className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
              Hành trình hôm nay
            </span>
            {/* Câu do máy chủ viết sẵn ("Đang ở …", "Chờ …", "Đã về") —
                cùng hàm với Bảng hành trình chung. */}
            <Chip tone="brand">{ht.dang_o}</Chip>
            {ht.ngoai_cho > 0 ? (
              <span className="text-meta text-ink-muted">
                · {ht.ngoai_cho} việc đang ở đối tác
              </span>
            ) : null}
          </p>
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
    </section>
  );
}
