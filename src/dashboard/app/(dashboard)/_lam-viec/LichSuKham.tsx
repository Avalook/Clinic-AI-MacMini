"use client";

// "LỊCH SỬ KHÁM" — nút + popup dùng chung (Tuyền chốt 07/10/2026, T7): Bàn khám
// (phía trên bộ 4 khối), `/patient-list`, `/customers`, quầy thuốc `/pharmacy`
// (khung "Lịch sử đơn thuốc", 09/10/2026).
//
// Liệt kê MỌI lượt của khách (cả lượt không phiếu, lượt chuyển từ Notion) —
// `GET /api/ho-so-kham?xem=lich-su` → `services/lich_su_luot.py`. Tìm theo ngày
// (gõ dd/mm hoặc dd/mm/yyyy) / loại dịch vụ; nút lịch cạnh ô tìm chấm xanh những
// ngày khách có khám. Bấm một lượt → mở hồ sơ lượt ấy CHỈ ĐỌC: khung đọc do
// MÁY CHỦ nói (`loai_du_lieu`) — v5 → hồ sơ kiểu Bàn khám; còn lại → khung xem
// lượt (`XemLuot`), hoặc màn gọi tự mở khung của nó (`onChonLuot`).
//
// 29/10/2026 (Tuyền): bấm nút là BUNG DANH SÁCH các lượt ngay dưới nút (thay
// dòng chip "Lượt khám trước" riêng ở Bàn khám); rê chuột vào một lượt hiện tóm
// tắt phiếu bên cạnh; bấm lượt → mở hồ sơ lượt ấy chỉ đọc; "Tìm theo ngày · xem
// mọi lượt" → hộp lớn như cũ.

import { History, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import LichKhoangNgay from "@/components/ui/LichKhoangNgay";
import { chuNhanLuot, type NhanLuot } from "@/lib/nhan-luot";
import { todayVn } from "@/lib/roster";
import type { Khoang } from "@/lib/thanh-ngay";

import { INPUT } from "../form-ui";
import { DongPhanHoiThuoc, type PhanHoiThuoc } from "./PhanHoiThuocKhach";
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
  /** Phản hồi sau dùng thuốc CSKH ghi cho lượt này (10/10/2026, chỉ đọc). */
  phan_hoi_thuoc?: PhanHoiThuoc[];
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

/** Tóm tắt phiếu của một lượt — cùng nguồn dòng chip "Lượt khám trước" cũ
 *  (`/api/clinical-forms/history`). */
interface TomTatLuot {
  visit_id: string;
  form_data: Record<string, unknown>;
}

/** Vài dòng đầu của phiếu, đủ để nhớ ra hôm đó khám gì. */
function tomTat(form: Record<string, unknown> | undefined): string[] {
  const ra: string[] = [];
  for (const [, v] of Object.entries(form ?? {})) {
    if (ra.length >= 4) break;
    if (typeof v === "string" && v.trim().length > 2) ra.push(v.trim());
    else if (Array.isArray(v) && v.length) ra.push(v.join(", "));
  }
  return ra;
}

/** Số lượt hiện trong danh sách bung — còn lại tìm ở hộp lớn. */
const SO_NHANH = 8;

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
  const [menu, setMenu] = useState(false);
  const [hien, setHien] = useState<string | null>(null);
  const [tomTatTheoLuot, setTomTatTheoLuot] = useState<Map<string, string[]> | null>(null);
  const vungRef = useRef<HTMLDivElement>(null);

  const ngayTim = tim ? ngayGo(tim, homNay) : null;
  const q = new URLSearchParams({ clinic_patient_id: clinicPatientId, xem: "lich-su" });
  const tu = ngayTim ?? khoang?.tu;
  const den = ngayTim ?? khoang?.den;
  if (tu) q.set("tu", tu);
  if (den) q.set("den", den);
  if (dichVu) q.set("dich_vu_id", dichVu);
  const url = `/api/ho-so-kham?${q.toString()}`;

  useEffect(() => {
    if (!mo && !menu) return;
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
  }, [mo, menu, url]);

  // Tóm tắt phiếu cho ô rê chuột — nạp một lần khi bung danh sách. Không đọc
  // được (quyền / mất mạng) thì ô vẫn hiện ngày · dịch vụ · bác sĩ.
  useEffect(() => {
    if (!menu || tomTatTheoLuot) return;
    let huy = false;
    void fetch(`/api/clinical-forms/history?clinic_patient_id=${clinicPatientId}`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { items?: TomTatLuot[] } | null) => {
        if (huy) return;
        setTomTatTheoLuot(new Map((d?.items ?? []).map((x) => [x.visit_id, tomTat(x.form_data)])));
      })
      .catch(() => {
        if (!huy) setTomTatTheoLuot(new Map());
      });
    return () => {
      huy = true;
    };
  }, [menu, tomTatTheoLuot, clinicPatientId]);

  // Bấm ra ngoài / Esc → gập danh sách.
  useEffect(() => {
    if (!menu) return;
    const ngoai = (e: MouseEvent) => {
      if (vungRef.current && !vungRef.current.contains(e.target as Node)) setMenu(false);
    };
    const esc = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenu(false);
    };
    document.addEventListener("mousedown", ngoai);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", ngoai);
      document.removeEventListener("keydown", esc);
    };
  }, [menu]);

  const ngayCham = useMemo(() => new Set(goi?.ngay_co_kham ?? []), [goi]);
  const dong = () => {
    setMo(false);
    setXem(null);
  };
  const chon = (l: LuotLichSu) => {
    setMenu(false);
    setHien(null);
    if (onChonLuot?.(l)) return;
    setXem(l);
    setMo(true);
  };
  const nhanh = (goi?.luot ?? []).filter((l) => l.visit_id !== visitIdHienTai).slice(0, SO_NHANH);
  const luotHien = hien ? nhanh.find((l) => l.visit_id === hien) : null;
  const dongHien = luotHien ? tomTatTheoLuot?.get(luotHien.visit_id) : undefined;

  return (
    <>
      <div ref={vungRef} className="relative inline-block">
        <Button size="sm" variant="secondary" aria-expanded={menu} onClick={() => setMenu((x) => !x)}>
          <History className="size-4" aria-hidden="true" />
          {nhanNut}
        </Button>
        {menu ? (
          <div className="absolute right-0 top-full z-30 mt-1 w-72 rounded-card border border-hairline bg-surface p-1.5 shadow-panel">
            {!goi && !loi ? <p className="px-2 py-2 text-meta text-ink-muted">Đang tải…</p> : null}
            {loi ? <p className="px-2 py-2 text-meta text-danger">{loi}</p> : null}
            {goi && nhanh.length === 0 ? (
              <p className="px-2 py-2 text-meta text-ink-muted">Chưa có lượt khám trước.</p>
            ) : null}
            <ul>
              {nhanh.map((l) => (
                <li key={l.visit_id}>
                  <button
                    type="button"
                    onMouseEnter={() => setHien(l.visit_id)}
                    onMouseLeave={() => setHien(null)}
                    onFocus={() => setHien(l.visit_id)}
                    onBlur={() => setHien(null)}
                    onClick={() => chon(l)}
                    className="flex w-full flex-wrap items-baseline gap-x-2 rounded-control px-2 py-1.5 text-left text-meta hover:bg-brand-50"
                  >
                    <b className="tabular-nums text-ink">{ngayVN(l.ngay)}</b>
                    <span className="text-brand-700">{chuNhanLuot(l.nhan_luot)}</span>
                    <span className="min-w-0 truncate text-ink-muted">{l.dich_vu ?? ""}</span>
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={() => {
                setMenu(false);
                setMo(true);
              }}
              className="mt-1 w-full rounded-control border-t border-hairline px-2 pt-2 pb-1 text-left text-meta font-medium text-brand-700 hover:bg-surface-muted"
            >
              Tìm theo ngày · xem mọi lượt{goi ? ` (${goi.tong})` : ""}
            </button>
            {/* Tóm tắt BÊN CẠNH khi rê chuột — liếc rồi đi tiếp, không phải hộp
                thoại phải đóng. Màn hẹp không có rê chuột → không vẽ. */}
            {luotHien ? (
              <div className="absolute right-full top-0 mr-2 hidden w-72 rounded-card bg-surface p-3 text-xs shadow-panel sm:block">
                <p className="font-semibold text-ink">
                  {ngayVN(luotHien.ngay)}
                  {luotHien.dich_vu ? ` · ${luotHien.dich_vu}` : ""}
                </p>
                {luotHien.bac_si ? <p className="mt-0.5 text-ink-muted">{luotHien.bac_si}</p> : null}
                {dongHien?.length ? (
                  <ul className="mt-1.5 grid gap-1 text-ink-soft">
                    {dongHien.map((d, i) => (
                      <li key={i} className="line-clamp-2">
                        {d}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1.5 text-ink-muted">
                    {tomTatTheoLuot ? "Phiếu hôm đó chưa ghi nội dung nào." : "Đang tải tóm tắt…"}
                  </p>
                )}
                <p className="mt-2 text-brand-600">Bấm để xem lại nguyên phiếu</p>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
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
                  {l.phan_hoi_thuoc?.length ? (
                    <ul aria-label="Phản hồi sau dùng thuốc" className="space-y-1 px-3 pb-2">
                      {l.phan_hoi_thuoc.map((p) => (
                        <li key={p.id} className="rounded-control bg-surface-muted px-3 py-2">
                          <DongPhanHoiThuoc p={p} />
                        </li>
                      ))}
                    </ul>
                  ) : null}
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
