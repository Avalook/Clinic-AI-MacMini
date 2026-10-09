"use client";

// Hai khối LLM của tab Agent giám sát (09/10/2026):
//   · Tóm tắt của AI — bản mới nhất của hôm nay (tự tạo cuối ngày, hoặc bấm
//     "Tóm tắt ngay" — mỗi lần bấm là một lần gọi tính tiền).
//   · Chi phí AI — đồng hồ tiền do máy chủ ghi từng lần gọi (`llm_lan_goi`):
//     hôm nay so với trần, theo model, theo ngày, 20 lần gần nhất, bảng giá.
//     Số dư tài khoản KHÔNG có ở đây — chỉ Console → Billing mới có.
// Màn chỉ vẽ; tiền, trần, giá đều do máy chủ tính.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { fmtTime } from "@/lib/datetime";
import { nhipKhiHien } from "@/lib/nhip-khi-hien";

interface TomTat {
  ngay: string;
  llm_bat: boolean;
  model: string;
  gio_tu_dong: number;
  tom_tat: {
    id: string;
    noi_dung: string;
    model: string;
    tao_luc: string;
    tu_dong: boolean;
  } | null;
}

interface TheoModel {
  model: string;
  lan_goi: number;
  lan_loi: number;
  vao: number;
  ra: number;
  doc_cache: number;
  ghi_cache: number;
  usd: number;
  thieu_gia: boolean;
}

interface LanGoi {
  luc: string;
  tinh_nang: string;
  model: string;
  vao: number;
  ra: number;
  usd: number | null;
  thanh_cong: boolean;
  loi: string | null;
  thoi_gian_ms: number | null;
}

interface ChiPhi {
  hom_nay_usd: number;
  hom_nay_vnd: number;
  tran_ngay_usd: number;
  con_lai_hom_nay_usd: number;
  so_ngay: number;
  gan_day_bi_cat: boolean;
  theo_model: TheoModel[];
  theo_ngay: { ngay: string; lan_goi: number; usd: number }[];
  gan_day: LanGoi[];
  bang_gia: { model: string; vao: number; ra: number; doc_cache: number; ghi_cache: number }[];
  gia_ngay: string;
}

const so = (n: number) => n.toLocaleString("vi-VN");
const usd = (n: number) => `$${n.toFixed(n < 1 ? 4 : 2)}`;

async function doc<T>(xem: string): Promise<T | null> {
  const r = await fetch(`/api/ops/agent?xem=${xem}`, { cache: "no-store" }).catch(() => null);
  return r && r.ok ? ((await r.json()) as T) : null;
}

export default function AgentAiChiPhi() {
  const [tomTat, setTomTat] = useState<TomTat | null>(null);
  const [chiPhi, setChiPhi] = useState<ChiPhi | null>(null);
  const [dangTao, setDangTao] = useState(false);
  const [baoLoi, setBaoLoi] = useState<string | null>(null);

  const nap = useCallback(async () => {
    const [t, c] = await Promise.all([doc<TomTat>("tom-tat"), doc<ChiPhi>("chi-phi")]);
    setTomTat(t);
    setChiPhi(c);
  }, []);

  useEffect(() => {
    let huy = false;
    const chay = () => {
      if (!huy) void nap();
    };
    chay();
    const goNhip = nhipKhiHien(chay, 30000);
    return () => {
      huy = true;
      goNhip();
    };
  }, [nap]);

  const taoNgay = async () => {
    setDangTao(true);
    setBaoLoi(null);
    const r = await fetch("/api/ops/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hanh_dong: "tom-tat" }),
    }).catch(() => null);
    setDangTao(false);
    if (!r || !r.ok) {
      const loi = r ? ((await r.json().catch(() => null)) as { detail?: string; message?: string } | null) : null;
      setBaoLoi(loi?.message ?? loi?.detail ?? "Không tạo được bản tóm tắt.");
    }
    await nap();
  };

  const phanTram =
    chiPhi && chiPhi.tran_ngay_usd > 0
      ? Math.min(100, Math.round((chiPhi.hom_nay_usd / chiPhi.tran_ngay_usd) * 100))
      : 0;

  return (
    <>
      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-emph font-semibold text-ink">
            Tóm tắt của AI{" "}
            <Chip tone={tomTat?.llm_bat ? "info" : "neutral"}>
              {tomTat === null ? "…" : tomTat.llm_bat ? tomTat.model : "Chưa bật (chưa có khoá)"}
            </Chip>
          </h2>
          <Button
            type="button"
            size="sm"
            variant="soft"
            disabled={!tomTat?.llm_bat || dangTao}
            onClick={() => void taoNgay()}
          >
            {dangTao ? "Đang viết…" : "Tóm tắt ngay"}
          </Button>
        </div>
        {baoLoi ? (
          <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
            {baoLoi}
          </p>
        ) : null}
        {tomTat?.tom_tat ? (
          <div className="rounded-card border border-hairline bg-surface p-3">
            <p className="text-meta text-ink-muted">
              {tomTat.tom_tat.tu_dong ? "Tự tạo" : "Bấm tay"} lúc {fmtTime(tomTat.tom_tat.tao_luc)} ·{" "}
              {tomTat.tom_tat.model} · chỉ đọc nhận định đã không tên khách
            </p>
            <div className="mt-2 whitespace-pre-wrap break-words text-body text-ink">{tomTat.tom_tat.noi_dung}</div>
          </div>
        ) : (
          <p className="text-meta text-ink-muted">
            {tomTat?.llm_bat
              ? `Hôm nay chưa có bản tóm tắt — tự tạo sau ${tomTat.gio_tu_dong}:00, hoặc bấm "Tóm tắt ngay".`
              : "LLM chưa bật: cần tệp khoá agent_llm_api_key trên máy chủ."}
          </p>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-emph font-semibold text-ink">Chi phí AI · {chiPhi?.so_ngay ?? 7} ngày</h2>
        {chiPhi === null ? (
          <p className="text-body text-ink-muted">Đang tải…</p>
        ) : (
          <>
            <div className="rounded-card border border-hairline bg-surface p-3">
              <p className="text-body text-ink">
                Hôm nay <b>{usd(chiPhi.hom_nay_usd)}</b> (≈ {so(chiPhi.hom_nay_vnd)} đ) / trần{" "}
                {usd(chiPhi.tran_ngay_usd)} · còn {usd(chiPhi.con_lai_hom_nay_usd)}
              </p>
              {/* <meter> gốc: trình duyệt tự tô xanh / vàng / đỏ theo low-high,
                  không cần style riêng. */}
              <meter
                className="mt-2 h-2 w-full"
                min={0}
                max={100}
                low={60}
                high={90}
                optimum={0}
                value={phanTram}
                aria-label="Tiền hôm nay so với trần"
              >
                {phanTram}%
              </meter>
              <p className="mt-1 text-meta text-ink-muted">
                Chạm trần thì máy chủ tự ngừng gọi tới hết ngày. Số dư tài khoản chỉ xem được ở Console → Billing.
              </p>
            </div>

            {chiPhi.theo_model.length === 0 ? (
              <p className="text-meta text-ink-muted">Chưa có lần gọi nào trong {chiPhi.so_ngay} ngày.</p>
            ) : (
              <ul className="grid gap-2 lg:grid-cols-2">
                {chiPhi.theo_model.map((m) => (
                  <li key={m.model} className="rounded-card border border-hairline bg-surface p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="min-w-0 break-all text-body font-semibold text-ink">{m.model}</span>
                      <b className="text-body text-ink">{m.thieu_gia ? "chưa có giá" : usd(m.usd)}</b>
                    </div>
                    <p className="mt-1 text-meta text-ink-muted">
                      {so(m.lan_goi)} lần gọi{m.lan_loi ? ` (${m.lan_loi} lỗi)` : ""} · vào {so(m.vao)} · ra {so(m.ra)}{" "}
                      · cache đọc {so(m.doc_cache)} · cache ghi {so(m.ghi_cache)} token
                    </p>
                  </li>
                ))}
              </ul>
            )}

            {chiPhi.gan_day.length > 0 ? (
              <details className="rounded-card border border-hairline bg-surface">
                <summary className="cursor-pointer px-3 py-2 text-meta text-ink-muted">
                  {chiPhi.gan_day_bi_cat ? "20 lần gọi gần nhất" : `Các lần gọi (${chiPhi.gan_day.length})`} · theo
                  ngày: {chiPhi.theo_ngay.map((d) => `${d.ngay.slice(8)}/${d.ngay.slice(5, 7)} ${usd(d.usd)}`).join(" · ")}
                </summary>
                <ul className="divide-y divide-hairline border-t border-hairline">
                  {chiPhi.gan_day.map((g) => (
                    <li key={g.luc} className="px-3 py-2 text-meta text-ink-muted">
                      {fmtTime(g.luc)} · {g.tinh_nang} · {g.model} · vào {so(g.vao)} / ra {so(g.ra)} ·{" "}
                      {g.usd === null ? "chưa có giá" : usd(g.usd)}
                      {g.thoi_gian_ms ? ` · ${(g.thoi_gian_ms / 1000).toFixed(1)}s` : ""}
                      {g.thanh_cong ? "" : ` · lỗi: ${g.loi ?? ""}`}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}

            <details className="rounded-card border border-hairline bg-surface">
              <summary className="cursor-pointer px-3 py-2 text-meta text-ink-muted">
                Bảng giá đang áp (USD / 1 triệu token, chép ngày {chiPhi.gia_ngay})
              </summary>
              <ul className="divide-y divide-hairline border-t border-hairline">
                {chiPhi.bang_gia.map((g) => (
                  <li key={g.model} className="px-3 py-2 text-meta text-ink-muted">
                    {g.model}: vào {g.vao} · ra {g.ra} · cache đọc {g.doc_cache} · cache ghi {g.ghi_cache}
                  </li>
                ))}
              </ul>
            </details>
          </>
        )}
      </section>
    </>
  );
}
