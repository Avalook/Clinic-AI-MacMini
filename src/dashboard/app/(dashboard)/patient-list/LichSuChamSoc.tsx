"use client";

// LỊCH SỬ CHĂM SÓC KHÁCH TRƯỚC 10/2026 (Tuyền 06/10/2026) — chỉ đọc, trong hồ sơ khách,
// đặt cạnh khối "Hồ sơ khám trước 10/2026" ở Danh sách bệnh nhân và Quản lý khách hàng.
//
// Nguồn: bảng chăm sóc khách của hệ thống cũ, nạp vào `lich_su_notion.cham_soc`
// (KHÔNG phải việc CSKH — không sinh việc, không ai phải "làm" gì ở đây). Đọc
// `GET /api/lich-su-notion?cham_soc=<khách>`; ai xem được do FastAPI quyết (cửa của
// một trong hai màn). Mặc định THU GỌN; khách không có lịch sử thì khối không vẽ.

import { useEffect, useState } from "react";
import { PhoneCall } from "lucide-react";

import Chip from "@/components/ui/Chip";
import NganGap from "@/components/ui/NganGap";
import { fmtDate, fmtDateTime } from "../../../lib/datetime";

type DongChamSoc = {
  id: string;
  ma: string | null;
  luc: string;
  buoc: string;
  buoc_nhan: string;
  phan_loai: string | null;
  kich_ban: string | null;
  tinh_trang: string | null;
  noi_dung: string | null;
  doi_tuong: string | null;
  nguoi_lam: string | null;
  ngay_hen: string | null;
  gio_hen: string | null;
  hen_loai_kham: string | null;
};

type ChamSoc = { tong: number; dong: DongChamSoc[] };

/** Đối tượng của dòng: lịch hẹn nối được thì in đủ ngày (có năm), còn lại in như cũ. */
function doiTuong(d: DongChamSoc): string | null {
  if (d.ngay_hen) {
    return [
      `Lịch hẹn ${fmtDate(d.ngay_hen)}${d.gio_hen && d.gio_hen !== "00:00" ? ` ${d.gio_hen}` : ""}`,
      d.hen_loai_kham,
    ]
      .filter(Boolean)
      .join(" · ");
  }
  return d.doi_tuong;
}

export default function LichSuChamSoc({ clinicPatientId }: { clinicPatientId: string }) {
  const [cs, setCs] = useState<ChamSoc | null>(null);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    // Đổi khách = component mới (cha đặt `key` theo khách) → state tự sạch.
    let huy = false;
    fetch(`/api/lich-su-notion?cham_soc=${encodeURIComponent(clinicPatientId)}`, { cache: "no-store" })
      .then(async (r) => {
        const j = await r.json().catch(() => null);
        if (huy) return;
        // Không vào được màn nào có khối này → khối tự ẩn, không báo lỗi.
        if (r.status === 403) setCs({ tong: 0, dong: [] });
        else if (!r.ok) setLoi((j && (j.message || j.detail)) || "Không đọc được lịch sử chăm sóc cũ.");
        else setCs(j as ChamSoc);
      })
      .catch(() => !huy && setLoi("Không đọc được lịch sử chăm sóc cũ."));
    return () => {
      huy = true;
    };
  }, [clinicPatientId]);

  if (loi) {
    return (
      <section className="border-t border-line px-5 py-4">
        <p className="text-meta text-danger">{loi}</p>
      </section>
    );
  }
  if (!cs || cs.tong === 0) return null;

  return (
    // `w-0 min-w-full`: như khối hồ sơ khám cũ — chữ dài không kéo khung rộng quá màn 375.
    <section className="w-0 min-w-full border-t border-line px-5 py-4" aria-label="Lịch sử chăm sóc trước 10/2026">
      <NganGap
        co="the"
        tieuDe={
          <span className="flex items-center gap-1.5">
            <PhoneCall size={15} className="text-brand-600" /> Lịch sử chăm sóc trước 10/2026 ({cs.tong})
          </span>
        }
        chip={<Chip tone="info">Hồ sơ cũ</Chip>}
      >
        <p className="text-meta text-ink-muted">
          Nhật ký gọi, nhắn, nhắc lịch, trả kết quả ở hệ thống cũ — chỉ để tra, không phải việc cần làm.
          {cs.tong > cs.dong.length ? ` Hiện ${cs.dong.length} dòng mới nhất.` : ""}
        </p>
        <ul className="divide-y divide-hairline">
          {cs.dong.map((d) => {
            const dt = doiTuong(d);
            return (
              <li key={d.id} className="py-2">
                <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                  <span className="tabular-nums text-meta font-semibold text-ink">{fmtDateTime(d.luc)}</span>
                  <Chip tone="neutral">{d.buoc_nhan}</Chip>
                  {d.phan_loai ? <span className="text-meta text-ink-soft">{d.phan_loai}</span> : null}
                  {d.nguoi_lam ? <span className="text-meta text-ink-muted">· {d.nguoi_lam}</span> : null}
                </div>
                {d.kich_ban ? <p className="mt-1 break-words text-body text-ink">{d.kich_ban}</p> : null}
                {d.tinh_trang ? (
                  <p className="mt-1 break-words text-meta text-ink-soft">Tình trạng: {d.tinh_trang}</p>
                ) : null}
                {d.noi_dung ? (
                  <p className="mt-1 whitespace-pre-wrap break-words text-body text-ink">{d.noi_dung}</p>
                ) : null}
                {dt ? <p className="mt-1 break-words text-meta text-ink-muted">{dt}</p> : null}
              </li>
            );
          })}
        </ul>
      </NganGap>
    </section>
  );
}
