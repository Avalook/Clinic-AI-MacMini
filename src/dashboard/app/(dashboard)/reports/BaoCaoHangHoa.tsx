"use client";

// TAB "HÀNG HOÁ" (08/10/2026) — màn hiện Y NHƯ báo cáo KiotViet quầy thuốc đang
// dùng (EndOfDayProduct): Ngày lập · tiêu đề giữa · Ngày bán · Chi nhánh · bảng ·
// địa chỉ chân trang. Tuyền: "hiện giao diện trên hệ thống luôn, in ra là bê ra
// thôi" — nút In in đúng tờ này (thanh chọn ẩn khi in).
//
// Số do máy chủ gom (`GET /api/v1/reports/cuoi-ngay` → `hang_hoa`, `chi_nhanh`),
// cùng luật ngày / ca / cơ sở với tab Cuối ngày. Màn chỉ vẽ.

import { useCallback, useEffect, useRef, useState } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import { ChonCoSoO, type CoSo } from "@/components/ui/ChonCoSo";
import ThanhNgay from "@/components/ui/ThanhNgay";
import { todayVn } from "@/lib/roster";
import { congNgay, type Khoang } from "@/lib/thanh-ngay";

import BangHangHoa, { type HangHoa } from "./BangHangHoa";

interface DuLieu {
  co_so?: string | null;
  ten_co_so?: string | null;
  tu: string;
  den: string;
  ca?: { ma: string; ten: string; tu: string; den: string } | null;
  hang_hoa?: Record<"thuoc" | "dich_vu", HangHoa>;
  chi_nhanh?: { ten: string; dia_chi: string | null }[];
}

function ngayVn(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

// "08/10/2026 15:59" — ngày trước giờ, như KiotViet.
function bayGio(): string {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-GB", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "Asia/Ho_Chi_Minh",
    })
      .formatToParts(new Date())
      .map((x) => [x.type, x.value]),
  );
  return `${p.day}/${p.month}/${p.year} ${p.hour}:${p.minute}`;
}

const NUT = "min-h-10 whitespace-nowrap rounded-control px-3 text-sm font-medium";

export default function BaoCaoHangHoa({ coSo = [], access }: { coSo?: CoSo[]; access?: import("./access").ReportAccess }) {
  const lanTai = useRef(0);
  const lanNgay = useRef(0);
  const [chuoiDaTai, setChuoiDaTai] = useState("");
  const [phamVi, setPhamVi] = useState(access);
  const restricted = !!phamVi && !phamVi.legacy && !phamVi.quan_ly;
  const doiNgay = async (k: Khoang) => {
    if (!restricted) { setKhoang(k); return; }
    const lan = ++lanNgay.current;
    ++lanTai.current; setDl(null);
    try {
      const res = await fetch(`/api/reports/access?ngay=${encodeURIComponent(k.tu)}`);
      if (!res.ok) throw new Error("Không kiểm được quyền xem ngày này.");
      const next: import("./access").ReportAccess = await res.json();
      if (lan !== lanNgay.current) return;
      setPhamVi(next); setDl(null);
      setKhoang({ tu: k.tu, den: k.tu });
      if (!next.ban_hang) { setLoi("Bạn không có ca được duyệt trong ngày này."); return; }
      setCa(next.cac_ca.includes("FULL") ? "" : next.cac_ca[0] as "SANG" | "CHIEU" | "TOI");
      setCoSoChon(next.co_so_ids[0] ?? "");
      setKhoang({ tu: k.tu, den: k.tu });
    } catch { setLoi("Không kiểm được quyền xem ngày này."); setDl(null); }
  };
  const [homNay] = useState(todayVn);
  const [khoang, setKhoang] = useState<Khoang>({ tu: homNay, den: homNay });
  const [loai, setLoai] = useState<"thuoc" | "dich_vu">("thuoc");
  const [ca, setCa] = useState<"" | "SANG" | "CHIEU" | "TOI">(() => access && !access.legacy && !access.quan_ly && !access.cac_ca.includes("FULL") ? (access.cac_ca[0] as "SANG" | "CHIEU" | "TOI") ?? "" : "");
  const [coSoChon, setCoSoChon] = useState(() => access && !access.legacy && !access.quan_ly ? access.co_so_ids[0] ?? "" : "");
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangTai, setDangTai] = useState(true);
  const [lapLuc, setLapLuc] = useState("");
  const motNgay = khoang.tu === khoang.den;

  const chuoi = new URLSearchParams({
    tu: khoang.tu,
    den: khoang.den,
    loai,
    ...(coSoChon ? { co_so: coSoChon } : {}),
    ...(ca && motNgay ? { ca } : {}),
  }).toString();

  const tai = useCallback(async () => {
    const lan = ++lanTai.current;
    setDangTai(true); setLoi(null); setDl(null);
    try {
      const r = await fetch(`/api/reports/cuoi-ngay?${chuoi}`, { cache: "no-store", signal: AbortSignal.timeout(15000) });
      const d = await r.json().catch(() => null) as (DuLieu & { message?: string; error?: string }) | null;
      if (lan !== lanTai.current) return;
      if (!r.ok || !d?.hang_hoa) throw new Error(d?.message ?? d?.error ?? "Không đọc được báo cáo hàng hoá.");
      setDl(d); setChuoiDaTai(chuoi); setLapLuc(bayGio());
    } catch (e) {
      if (lan === lanTai.current) setLoi(e instanceof Error ? e.message : "Không đọc được báo cáo.");
    } finally { if (lan === lanTai.current) setDangTai(false); }
  }, [chuoi]);

  useEffect(() => {
    const h = setTimeout(() => void tai(), 0);
    return () => clearTimeout(h);
  }, [tai]);

  const hh = !dangTai && !loi && chuoiDaTai === chuoi ? dl?.hang_hoa?.[loai] : undefined;
  const chiNhanh = dl?.chi_nhanh ?? [];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start gap-2 print:hidden">
        {restricted ? <label className="text-body">
          Ngày bán
          <input type="date" value={khoang.tu} max={homNay}
            className="min-h-10 rounded-control bg-surface px-3 ring-1 ring-line-strong"
            onChange={e => { if (e.target.value) void doiNgay({ tu: e.target.value, den: e.target.value }); }} />
        </label> : <ThanhNgay
          nhan="Ngày bán"
          khoang={khoang}
          homNay={homNay}
          soNgaySau={0}
          dangTai={dangTai}
          onChon={(k) => setKhoang(k ?? { tu: congNgay(homNay, -92), den: homNay })}
          className="min-w-0 basis-full lg:basis-0 lg:flex-1"
        />}
        <div role="tablist" aria-label="Loại hàng" className="flex gap-1">
          {(
            [
              ["thuoc", "Thuốc"],
              ["dich_vu", "Dịch vụ"],
            ] as const
          ).map(([ma, nhan]) => (
            <button
              key={ma}
              type="button"
              role="tab"
              aria-selected={loai === ma}
              onClick={() => setLoai(ma)}
              className={`${NUT} ${loai === ma ? "bg-brand-600 text-white" : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"}`}
            >
              {nhan}
            </button>
          ))}
        </div>
        {motNgay ? (
          <div role="tablist" aria-label="Ca" className="flex gap-1">
            {(
              [
                ["", "Cả ngày"],
                ["SANG", "Ca sáng"],
                ["CHIEU", "Ca chiều"],
                ["TOI", "Ca tối"],
              ] as const
            ).filter(([ma]) => !phamVi || phamVi.quan_ly || phamVi.legacy || phamVi.cac_ca.includes(ma || "FULL")).map(([ma, nhan]) => (
              <button
                key={ma}
                type="button"
                role="tab"
                aria-selected={ca === ma}
                onClick={() => setCa(ma)}
                className={`${NUT} ${ca === ma ? "bg-brand-600 text-white" : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"}`}
              >
                {nhan}
              </button>
            ))}
          </div>
        ) : null}
        <ChonCoSoO coSo={restricted && phamVi ? coSo.filter(c => phamVi.co_so_ids.includes(c.id)) : coSo} dangChon={coSoChon} onChon={setCoSoChon} />
        <div className="flex gap-2">
          <Button type="button" size="sm" onClick={() => window.print()} disabled={!hh}>
            In
          </Button>
          <a
            href={`/api/reports/cuoi-ngay?xuat=csv&mau=hang_hoa&${chuoi}`}
            className={buttonClass("secondary", "sm")}
          >
            Xuất Excel
          </a>
        </div>
      </div>

      {loi ? (
        <p role="alert" className="text-meta text-danger print:hidden">
          {loi}
        </p>
      ) : null}

      {dl && hh ? (
        <article className="mx-auto max-w-5xl space-y-4 rounded-card border border-line bg-surface px-4 py-6 shadow-card sm:px-8 print:max-w-none print:border-0 print:p-0 print:shadow-none">
          <p className="text-meta text-ink-soft">Ngày lập:{lapLuc}</p>
          <header className="space-y-1 text-center">
            <h2 className="text-title font-semibold text-ink">Báo cáo cuối ngày về hàng hóa</h2>
            <p className="text-body text-ink-soft">
              Ngày bán: {dl.tu === dl.den ? ngayVn(dl.tu) : `${ngayVn(dl.tu)} - ${ngayVn(dl.den)}`}
              {dl.ca ? ` · ${dl.ca.ten} ${dl.ca.tu}–${dl.ca.den}` : ""}
            </p>
            <p className="text-body text-ink-soft">
              Chi nhánh: {dl?.ten_co_so ?? (chiNhanh.length === 1 ? chiNhanh[0].ten : "Tất cả cơ sở")}
              {loai === "dich_vu" ? " · Dịch vụ" : " · Thuốc"}
            </p>
          </header>
          <BangHangHoa hh={hh} />
          <footer className="space-y-0.5 pt-6 text-center text-meta text-ink-soft">
            {chiNhanh
              .filter((c) => c.dia_chi)
              .map((c) => (
                <p key={c.ten}>
                  {c.ten}: {c.dia_chi}
                </p>
              ))}
          </footer>
        </article>
      ) : null}
      <p className="text-meta text-ink-muted print:hidden">
        Thuốc: mã hàng là mã KiotViet; dịch vụ: mã của hệ thống. Chưa có cột Tồn đầu / Tồn cuối — quầy bán
        chưa trừ kho nên số tồn máy chưa đúng.
      </p>
    </section>
  );
}
