"use client";

// TAB "HÀNG HOÁ" (08/10/2026) — màn hiện Y NHƯ báo cáo KiotViet quầy thuốc đang
// dùng (EndOfDayProduct): Ngày lập · tiêu đề giữa · Ngày bán · Chi nhánh · bảng ·
// địa chỉ chân trang. Tuyền: "hiện giao diện trên hệ thống luôn, in ra là bê ra
// thôi" — nút In in đúng tờ này (thanh chọn ẩn khi in).
//
// Số do máy chủ gom (`GET /api/v1/reports/cuoi-ngay` → `hang_hoa`, `chi_nhanh`),
// cùng luật ngày / ca / cơ sở với tab Cuối ngày. Màn chỉ vẽ.

import { useCallback, useEffect, useState } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import { ChonCoSoO, type CoSo } from "@/components/ui/ChonCoSo";
import ThanhNgay from "@/components/ui/ThanhNgay";
import { todayVn } from "@/lib/roster";
import { congNgay, type Khoang } from "@/lib/thanh-ngay";

import BangHangHoa, { type HangHoa } from "./BangHangHoa";

interface DuLieu {
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

function bayGio(): string {
  return new Date().toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

const NUT = "min-h-10 rounded-control px-3 text-sm font-medium";

export default function BaoCaoHangHoa({ coSo = [] }: { coSo?: CoSo[] }) {
  const [homNay] = useState(todayVn);
  const [khoang, setKhoang] = useState<Khoang>({ tu: homNay, den: homNay });
  const [loai, setLoai] = useState<"thuoc" | "dich_vu">("thuoc");
  const [ca, setCa] = useState<"" | "SANG" | "CHIEU" | "TOI">("");
  const [coSoChon, setCoSoChon] = useState("");
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
    setDangTai(true);
    setLoi(null);
    const r = await fetch(`/api/reports/cuoi-ngay?${chuoi}`, { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as (DuLieu & { message?: string; error?: string }) | null;
    if (!r.ok || !d || !d.hang_hoa) setLoi(d?.message ?? d?.error ?? "Không đọc được báo cáo hàng hoá.");
    else {
      setDl(d);
      setLapLuc(bayGio());
    }
    setDangTai(false);
  }, [chuoi]);

  useEffect(() => {
    const h = setTimeout(() => void tai(), 0);
    return () => clearTimeout(h);
  }, [tai]);

  const hh = dl?.hang_hoa?.[loai];
  const chiNhanh = dl?.chi_nhanh ?? [];

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start gap-2 print:hidden">
        <ThanhNgay
          nhan="Ngày bán"
          khoang={khoang}
          homNay={homNay}
          soNgaySau={0}
          dangTai={dangTai}
          onChon={(k) => setKhoang(k ?? { tu: congNgay(homNay, -92), den: homNay })}
          className="min-w-0 flex-1"
        />
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
            ).map(([ma, nhan]) => (
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
        <ChonCoSoO coSo={coSo} dangChon={coSoChon} onChon={setCoSoChon} />
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
              Chi nhánh: {chiNhanh.length === 1 ? chiNhanh[0].ten : "Tất cả chi nhánh"}
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
