"use client";

// "LỊCH SỬ KHÁM" — nút + popup dùng chung (Tuyền chốt 07/10/2026, T7): Bàn khám
// (phía trên bộ 4 khối), `/patient-list`, `/customers`.
//
// Liệt kê MỌI lượt của khách (cả lượt không phiếu, lượt chuyển từ Notion) —
// `GET /api/ho-so-kham?xem=lich-su` → `services/lich_su_luot.py`. Tìm theo ngày
// (gõ dd/mm hoặc dd/mm/yyyy) / loại dịch vụ; nút lịch cạnh ô tìm chấm xanh những
// ngày khách có khám. Bấm một lượt → mở hồ sơ lượt ấy CHỈ ĐỌC: khung đọc do
// MÁY CHỦ nói (`loai_du_lieu`) — v5 → hồ sơ kiểu Bàn khám; còn lại → khung xem
// lượt (`XemLuot`), hoặc màn gọi tự mở khung của nó (`onChonLuot`).

import { History, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import LichKhoangNgay from "@/components/ui/LichKhoangNgay";
import { chuNhanLuot, type NhanLuot } from "@/lib/nhan-luot";
import { todayVn } from "@/lib/roster";
import type { Khoang } from "@/lib/thanh-ngay";

import { INPUT } from "../form-ui";
import PhieuKhamLuot from "./phieu-kham/PhieuKhamLuot";
import XemLuot from "./XemLuot";

export interface LuotLichSu {
  visit_id: string;
  appointment_id: string | null;
  ngay: string;
  trang_thai: string;
  dich_vu_id: string | null;
  dich_vu: string | null;
  bac_si: string | null;
  /** v5 | notion | cu | trong — máy chủ quyết khung đọc. */
  loai_du_lieu: string;
  nhan_loai: string;
  service_code_cu: string | null;
  /** Nhãn đếm lượt máy chủ tính (08/10/2026): "Lượt khám n" / "Buổi k/N"… */
  nhan_luot?: NhanLuot | null;
}

interface GoiLichSu {
  luot: LuotLichSu[];
  ngay_co_kham: string[];
  dich_vu: { id: string; ten: string | null }[];
  tong: number;
}

/** "07/10" | "7/10/2026" | "2026-10-07" → yyyy-mm-dd (năm thiếu = năm nay). */
function ngayGo(chu: string, homNay: string): string | null {
  const s = chu.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const m = s.match(/^(\d{1,2})[/.-](\d{1,2})(?:[/.-](\d{4}))?$/);
  if (!m) return null;
  const nam = m[3] ?? homNay.slice(0, 4);
  return `${nam}-${m[2].padStart(2, "0")}-${m[1].padStart(2, "0")}`;
}

function ngayVN(iso: string): string {
  const [y, mo, d] = iso.split("-");
  return `${d}/${mo}/${y}`;
}

export default function LichSuKham({
  clinicPatientId,
  visitIdHienTai,
  onChonLuot,
  nhanNut = "Lịch sử khám",
}: {
  clinicPatientId: string;
  /** Lượt đang mở (đánh dấu "đang khám", vẫn xem được). */
  visitIdHienTai?: string | null;
  /** Màn gọi tự mở khung đọc của nó (vd `/patient-list` giữ khung cũ cho lượt
   *  không phiếu v5, `/customers` mở hồ sơ CSKH). Trả true = đã mở → đóng popup;
   *  false = dùng khung mặc định trong popup. */
  onChonLuot?: (l: LuotLichSu) => boolean;
  nhanNut?: string;
}) {
  const homNay = todayVn();
  const [mo, setMo] = useState(false);
  const [goi, setGoi] = useState<GoiLichSu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [khoang, setKhoang] = useState<Khoang | null>(null);
  const [dichVu, setDichVu] = useState("");
  const [tim, setTim] = useState("");
  const [xem, setXem] = useState<LuotLichSu | null>(null);

  const ngayTim = tim ? ngayGo(tim, homNay) : null;
  const q = new URLSearchParams({ clinic_patient_id: clinicPatientId, xem: "lich-su" });
  const tu = ngayTim ?? khoang?.tu;
  const den = ngayTim ?? khoang?.den;
  if (tu) q.set("tu", tu);
  if (den) q.set("den", den);
  if (dichVu) q.set("dich_vu_id", dichVu);
  const url = `/api/ho-so-kham?${q.toString()}`;

  useEffect(() => {
    if (!mo) return;
    let huy = false;
    void fetch(url, { cache: "no-store" })
      .then(async (r) => ({ ok: r.ok, d: (await r.json().catch(() => null)) as GoiLichSu | null }))
      .then(({ ok, d }) => {
        if (huy) return;
        setGoi(ok ? d : null);
        setLoi(ok ? null : "Không đọc được lịch sử khám.");
      })
      .catch(() => {
        if (!huy) setLoi("Mất kết nối — thử lại.");
      });
    return () => {
      huy = true;
    };
  }, [mo, url]);

  const ngayCham = useMemo(() => new Set(goi?.ngay_co_kham ?? []), [goi]);
  const dong = () => {
    setMo(false);
    setXem(null);
  };

  return (
    <>
      <Button size="sm" variant="secondary" onClick={() => setMo(true)}>
        <History className="size-4" aria-hidden="true" />
        {nhanNut}
      </Button>
      {mo ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-4" role="presentation" onClick={dong}>
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Lịch sử khám"
            className="my-6 w-full max-w-5xl space-y-3 rounded-card bg-surface p-4 shadow-panel"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-title font-semibold text-ink">
                Lịch sử khám{goi ? ` (${goi.tong} lượt)` : ""}
              </h2>
              <button type="button" aria-label="Đóng" onClick={dong} className="rounded-control p-1 text-ink-muted hover:bg-surface-sunken">
                <X className="size-5" />
              </button>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={tim}
                onChange={(e) => setTim(e.target.value)}
                placeholder="Tìm ngày (dd/mm/yyyy)"
                aria-label="Tìm theo ngày khám"
                className={`${INPUT} max-w-48`}
              />
              <LichKhoangNgay khoang={khoang} homNay={homNay} onChon={setKhoang} nhan="Chọn ngày khám" ngayCham={ngayCham} />
              <select value={dichVu} onChange={(e) => setDichVu(e.target.value)} aria-label="Loại dịch vụ" className={`${INPUT} max-w-60`}>
                <option value="">Mọi dịch vụ</option>
                {(goi?.dich_vu ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.ten ?? "—"}
                  </option>
                ))}
              </select>
              {tim && !ngayTim ? <span className="text-meta text-warning">Ngày chưa đúng dạng dd/mm/yyyy.</span> : null}
            </div>
            {loi ? (
              <p role="alert" className="text-body text-danger">
                {loi}
              </p>
            ) : null}
            <ul className="divide-y divide-line rounded-control border border-line">
              {(goi?.luot ?? []).map((l) => (
                <li key={l.visit_id}>
                  <button
                    type="button"
                    aria-pressed={xem?.visit_id === l.visit_id}
                    onClick={() => {
                      if (onChonLuot?.(l)) dong();
                      else setXem(l);
                    }}
                    className={`flex w-full flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 text-left text-body hover:bg-surface-muted ${
                      xem?.visit_id === l.visit_id ? "bg-surface-selected" : ""
                    }`}
                  >
                    <b className="tabular-nums text-ink">{ngayVN(l.ngay)}</b>
                    <Chip tone="info">{chuNhanLuot(l.nhan_luot)}</Chip>
                    <span className="text-ink">{l.dich_vu ?? "—"}</span>
                    <span className="text-meta text-ink-muted">{l.bac_si ?? ""}</span>
                    <Chip tone="neutral">{l.nhan_loai}</Chip>
                    {l.visit_id === visitIdHienTai ? <Chip tone="info">đang khám</Chip> : null}
                  </button>
                </li>
              ))}
              {goi && goi.luot.length === 0 ? (
                <li className="px-3 py-6 text-center text-body text-ink-muted">Không có lượt khám nào khớp.</li>
              ) : null}
            </ul>
            {xem && xem.loai_du_lieu === "v5" ? (
              <PhieuKhamLuot
                key={`ls-${xem.visit_id}`}
                visitId={xem.visit_id}
                clinicPatientId={clinicPatientId}
                choGhi={false}
                xemLai
                datChiDinh={async () => ({ ok: false, loi: "Đang xem lại lượt cũ — không chỉ định được." })}
                onDaDat={() => undefined}
              />
            ) : xem ? (
              <XemLuot visitId={xem.visit_id} onDong={() => setXem(null)} />
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
