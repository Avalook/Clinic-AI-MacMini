"use client";

// Tab "Nhật ký vận hành" (Tuyền 27/09/2026): "khách A check-in lúc này do lễ tân
// này; đo sinh hiệu lúc này do tài khoản này làm trong bao nhiêu phút; thời gian
// check-in đến khi bắt đầu đo…".
//
// Máy chủ (`services/nhat_ky_van_hanh.py`) đọc dòng thời gian của mọi lượt trong
// ngày và TÍNH SẴN số phút từng khâu + trung vị cả ngày. Màn chỉ vẽ: bảng chỉ số
// theo lượt (khâu nào chậm tô cam) và dòng sự kiện ai-làm-gì-lúc-nào.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import SoLuot from "@/components/ui/SoLuot";
import { fmtTime } from "@/lib/datetime";

interface ChiSo {
  ma: string;
  ten: string;
}
type SoPhut = Record<string, number | null>;
interface DuLieu {
  ngay: string;
  chi_so: ChiSo[];
  trung_vi: SoPhut;
  theo_luot: (Record<string, unknown> & {
    visit_id: string;
    khach: string;
    ma_khach: string | null;
    so_booking: number | null;
    so_tiep_don: number | null;
    check_in: string | null;
  })[];
  dong: {
    luc: string;
    visit_id: string;
    khach: string;
    ma_khach: string | null;
    viec: string;
    nguoi_lam: string | null;
    cach_buoc_truoc_phut: number | null;
  }[];
  bi_cat: boolean;
  tong_dong: number;
}

const O = "min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink";

function homNay(): string {
  const d = new Date();
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function doiNgay(ngay: string, buoc: number): string {
  const [y, m, d] = ngay.split("-").map(Number);
  const t = new Date(y, m - 1, d + buoc);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${t.getFullYear()}-${p(t.getMonth() + 1)}-${p(t.getDate())}`;
}

function phut(v: unknown): string {
  return typeof v === "number" ? `${v.toLocaleString("vi-VN")}′` : "—";
}

export default function NhatKyVanHanh() {
  const [ngay, setNgay] = useState(homNay());
  const [tim, setTim] = useState("");
  const [timGui, setTimGui] = useState("");
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [chonLuot, setChonLuot] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    const q = new URLSearchParams({ xem: "nhat-ky", ngay });
    if (timGui) q.set("tim", timGui);
    void fetch(`/api/ops/theo-doi?${q.toString()}`, { cache: "no-store" })
      .then(async (r) => {
        if (huy) return;
        if (!r.ok) {
          setLoi("Không đọc được nhật ký.");
          return;
        }
        setLoi(null);
        setDl((await r.json()) as DuLieu);
      })
      .catch(() => !huy && setLoi("Mất kết nối."));
    return () => {
      huy = true;
    };
  }, [ngay, timGui]);

  const dong = (dl?.dong ?? []).filter((d) => !chonLuot || d.visit_id === chonLuot);

  return (
    <div className="space-y-4 p-4 lg:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="ghost" onClick={() => setNgay(doiNgay(ngay, -1))}>
          ← Hôm trước
        </Button>
        <input
          type="date"
          value={ngay}
          onChange={(e) => e.target.value && setNgay(e.target.value)}
          aria-label="Ngày"
          className={O}
        />
        <Button type="button" size="sm" variant="ghost" onClick={() => setNgay(doiNgay(ngay, 1))}>
          Hôm sau →
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setNgay(homNay())}>
          Hôm nay
        </Button>
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setTimGui(tim.trim());
            setChonLuot(null);
          }}
        >
          <input
            type="search"
            value={tim}
            onChange={(e) => setTim(e.target.value)}
            placeholder="Tên hoặc mã khách"
            aria-label="Tìm khách"
            className={O}
          />
          <Button type="submit" size="sm" variant="secondary">
            Tìm
          </Button>
        </form>
      </div>

      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {!dl ? <p className="text-body text-ink-muted">Đang tải…</p> : null}

      {dl ? (
        <>
          <section className="space-y-2">
            <h2 className="text-emph font-semibold text-ink">
              Thời gian từng khâu · {dl.theo_luot.length} lượt
            </h2>
            <p className="text-meta text-ink-muted">
              Số phút tính từ mốc máy chủ ghi (lần đầu mỗi bước). Ô tô cam: chậm hơn gấp đôi trung vị
              cả ngày. Bấm một khách để lọc dòng sự kiện bên dưới.
            </p>
            <div className="overflow-x-auto rounded-card border border-hairline bg-surface">
              <table className="w-full text-body">
                <thead className="bg-surface-muted text-meta text-ink-muted">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left">Khách</th>
                    <th scope="col" className="px-3 py-2 text-left">Check-in</th>
                    {dl.chi_so.map((c) => (
                      <th key={c.ma} scope="col" className="px-3 py-2 text-right">
                        {c.ten}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-hairline">
                  <tr className="bg-brand-50 font-semibold">
                    <td className="px-3 py-1.5" colSpan={2}>
                      Trung vị cả ngày
                    </td>
                    {dl.chi_so.map((c) => (
                      <td key={c.ma} className="px-3 py-1.5 text-right tabular-nums">
                        {phut(dl.trung_vi[c.ma])}
                      </td>
                    ))}
                  </tr>
                  {dl.theo_luot.map((l) => (
                    <tr
                      key={l.visit_id}
                      className={chonLuot === l.visit_id ? "bg-surface-selected" : undefined}
                    >
                      <td className="px-3 py-1.5">
                        <button
                          type="button"
                          onClick={() => setChonLuot(chonLuot === l.visit_id ? null : l.visit_id)}
                          className="text-left font-medium text-brand-700 hover:underline"
                        >
                          {l.khach}
                        </button>
                        <SoLuot booking={l.so_booking} checkin={l.so_tiep_don} className="ml-1" />
                      </td>
                      <td className="px-3 py-1.5 tabular-nums">{l.check_in ? fmtTime(l.check_in) : "—"}</td>
                      {dl.chi_so.map((c) => {
                        const v = l[c.ma];
                        const tv = dl.trung_vi[c.ma];
                        const cham = typeof v === "number" && typeof tv === "number" && tv > 0 && v > 2 * tv;
                        return (
                          <td
                            key={c.ma}
                            className={`px-3 py-1.5 text-right tabular-nums ${cham ? "bg-warning-bg font-semibold text-warning" : ""}`}
                          >
                            {phut(v)}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="space-y-2">
            <h2 className="flex flex-wrap items-center gap-2 text-emph font-semibold text-ink">
              Ai làm gì, lúc nào
              {chonLuot ? (
                <Button type="button" size="sm" variant="ghost" onClick={() => setChonLuot(null)}>
                  Bỏ lọc khách
                </Button>
              ) : null}
              {dl.bi_cat ? <Chip tone="warning">chỉ hiện {dl.tong_dong} dòng đầu — tìm theo khách để xem đủ</Chip> : null}
            </h2>
            <ul className="divide-y divide-hairline rounded-card border border-hairline bg-surface">
              {dong.length === 0 ? (
                <li className="px-3 py-3 text-body text-ink-muted">Không có sự kiện nào.</li>
              ) : (
                dong.map((d, i) => (
                  <li key={`${d.visit_id}-${d.luc}-${i}`} className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 px-3 py-2 text-body">
                    <span className="w-12 shrink-0 tabular-nums text-ink-muted">{fmtTime(d.luc)}</span>
                    <span className="min-w-0 flex-1">
                      <b className="font-semibold text-ink">{d.khach}</b>
                      <span className="text-ink"> · {d.viec}</span>
                    </span>
                    <span className="text-meta text-ink-muted">
                      {d.nguoi_lam ?? "—"}
                      {d.cach_buoc_truoc_phut !== null ? ` · sau bước trước ${phut(d.cach_buoc_truoc_phut)}` : ""}
                    </span>
                  </li>
                ))
              )}
            </ul>
          </section>
        </>
      ) : null}
    </div>
  );
}
