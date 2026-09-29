"use client";

// Tab "Lỗi & cảnh báo" (27/09/2026 — theo dõi lỗi Pha 1).
//
// Hai khối, cả hai do MÁY CHỦ gom:
//   · Cảnh báo — bộ canh gác trong vòng su-kien mở / tự đóng mỗi phút
//     (services/canh_gac.py): tin sự kiện kẹt, lỗi mới, hàng chờ ma, lượt treo;
//     cộng tốc độ kho tệp Viettel CFS do API tự đo mỗi phút
//     (services/canh_gac_kho_tep.py, 29/09).
//   · Lỗi theo kiểu — mỗi kiểu lỗi (API 500, bên nhận sự kiện hỏng, trang lỗi
//     giao diện) MỘT dòng, đếm số lần; người trực đánh dấu Đã biết / Đã sửa /
//     Bỏ qua. Đã sửa mà tái diễn thì máy chủ tự mở lại.
// Màn chỉ vẽ + gửi lệnh đổi trạng thái; không tự suy luận gì.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip, { type ChipTone } from "@/components/ui/Chip";
import { fmtTime } from "@/lib/datetime";

interface CanhBao {
  id: string;
  ma: string;
  muc: "warning" | "critical";
  noi_dung: string;
  so_lan: number;
  mo_luc: string;
  lan_cuoi: string;
  dong_luc: string | null;
  bao_luc: string | null;
}

// Số đo kho tệp mới nhất — null khi API chưa đo (vừa khởi động / tắt đo).
interface KhoTep {
  luc: string;
  doc_kb_s: number | null;
  ghi_kb_s: number | null;
  loi: string | null;
  cham: boolean;
}

function kbS(v: number | null): string {
  if (v === null) return "—";
  return v >= 1024 ? `${(v / 1024).toFixed(1)} MB/s` : `${Math.round(v)} KB/s`;
}

interface Loi {
  id: string;
  nguon: "api" | "worker" | "web";
  vi_tri: string;
  kieu: string;
  thong_diep: string;
  so_lan: number;
  lan_dau: string;
  lan_cuoi: string;
  ma_yeu_cau: string | null;
  trang_thai: "MOI" | "DA_BIET" | "DA_SUA" | "BO_QUA";
  doi_boi: string | null;
}

const NHAN_TT: Record<Loi["trang_thai"], { nhan: string; tone: ChipTone }> = {
  MOI: { nhan: "Mới", tone: "danger" },
  DA_BIET: { nhan: "Đã biết", tone: "warning" },
  DA_SUA: { nhan: "Đã sửa", tone: "success" },
  BO_QUA: { nhan: "Bỏ qua", tone: "neutral" },
};
const NHAN_NGUON: Record<Loi["nguon"], string> = {
  api: "API",
  worker: "Người đưa tin",
  web: "Giao diện",
};

function ngayGio(iso: string): string {
  const d = new Date(iso);
  const hom = new Date().toDateString() === d.toDateString();
  return hom ? fmtTime(iso) : `${d.getDate()}/${d.getMonth() + 1} ${fmtTime(iso)}`;
}

async function doc<T>(xem: string): Promise<T | null> {
  const r = await fetch(`/api/ops/theo-doi?xem=${xem}`, { cache: "no-store" }).catch(() => null);
  return r && r.ok ? ((await r.json()) as T) : null;
}

export default function LoiCanhBao() {
  const [canh, setCanh] = useState<CanhBao[] | null>(null);
  const [khoTep, setKhoTep] = useState<KhoTep | null>(null);
  const [loi, setLoi] = useState<Loi[] | null>(null);
  const [chiMo, setChiMo] = useState(true);
  const [dang, setDang] = useState<string | null>(null);
  const [baoLoi, setBaoLoi] = useState<string | null>(null);

  const nap = useCallback(async () => {
    const [c, l] = await Promise.all([
      doc<{ canh_bao: CanhBao[]; kho_tep?: KhoTep | null }>("canh-bao"),
      doc<{ loi: Loi[] }>(`loi${chiMo ? "&chi_mo=1" : ""}`),
    ]);
    if (!c || !l) setBaoLoi("Không đọc được — thử tải lại.");
    else setBaoLoi(null);
    setCanh(c?.canh_bao ?? []);
    setKhoTep(c?.kho_tep ?? null);
    setLoi(l?.loi ?? []);
  }, [chiMo]);

  useEffect(() => {
    let huy = false;
    const chay = () => {
      if (!huy) void nap();
    };
    chay();
    const t = setInterval(chay, 30000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [nap]);

  const doi = async (id: string, trangThai: Loi["trang_thai"]) => {
    setDang(id);
    const r = await fetch("/api/ops/theo-doi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ loi_id: id, trang_thai: trangThai }),
    }).catch(() => null);
    setDang(null);
    if (!r || !r.ok) setBaoLoi("Không đổi được trạng thái lỗi.");
    await nap();
  };

  const dangMo = (canh ?? []).filter((c) => !c.dong_luc);
  const daDong = (canh ?? []).filter((c) => c.dong_luc).slice(0, 10);

  return (
    <div className="space-y-5 p-4 lg:p-5">
      {baoLoi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {baoLoi}
        </p>
      ) : null}

      <section className="space-y-2">
        <h2 className="text-emph font-semibold text-ink">
          Cảnh báo đang mở{" "}
          <Chip tone={dangMo.length ? "danger" : "success"}>{dangMo.length}</Chip>
        </h2>
        <p className="text-meta text-ink-muted">
          Bộ canh gác chạy mỗi phút trong người đưa tin sự kiện; hết chuyện thì tự đóng. Có kênh
          Telegram ops (<code>TELEGRAM_OPS_CHAT_ID</code>) thì báo ngay lúc mở.
        </p>
        {khoTep ? (
          <p className="text-meta text-ink-muted">
            Kho tệp Viettel CFS:{" "}
            <Chip tone={khoTep.cham ? "danger" : "success"}>
              {khoTep.loi ? "không đo được" : khoTep.cham ? "chậm" : "ổn"}
            </Chip>{" "}
            {khoTep.loi ?? `đọc ${kbS(khoTep.doc_kb_s)} · ghi ${kbS(khoTep.ghi_kb_s)}`} · đo lúc{" "}
            {fmtTime(khoTep.luc)}
          </p>
        ) : null}
        {canh === null ? (
          <p className="text-body text-ink-muted">Đang tải…</p>
        ) : dangMo.length === 0 ? (
          <p className="rounded-control bg-success-bg px-3 py-2 text-body text-success">Không có cảnh báo nào — hệ thống ổn.</p>
        ) : (
          <ul className="space-y-2">
            {dangMo.map((c) => (
              <li key={c.id} className="rounded-card border border-hairline bg-surface p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone={c.muc === "critical" ? "danger" : "warning"}>
                    {c.muc === "critical" ? "Nghiêm trọng" : "Cần xem"}
                  </Chip>
                  <span className="text-meta text-ink-muted">
                    mở {ngayGio(c.mo_luc)} · lặp {c.so_lan} lần · lần cuối {ngayGio(c.lan_cuoi)}
                    {c.bao_luc ? " · đã báo Telegram" : ""}
                  </span>
                </div>
                <p className="mt-1 text-body text-ink">{c.noi_dung}</p>
              </li>
            ))}
          </ul>
        )}
        {daDong.length > 0 ? (
          <details className="rounded-card border border-hairline bg-surface">
            <summary className="cursor-pointer px-3 py-2 text-meta text-ink-muted">
              Đã tự đóng gần đây ({daDong.length})
            </summary>
            <ul className="divide-y divide-hairline border-t border-hairline">
              {daDong.map((c) => (
                <li key={c.id} className="px-3 py-2 text-meta text-ink-muted">
                  {ngayGio(c.mo_luc)} → {c.dong_luc ? ngayGio(c.dong_luc) : ""} · {c.noi_dung}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </section>

      <section className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-emph font-semibold text-ink">Lỗi theo kiểu</h2>
          <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={chiMo}
              onChange={(e) => setChiMo(e.target.checked)}
            />
            Chỉ lỗi còn phải xử lý (Mới · Đã biết)
          </label>
        </div>
        <p className="text-meta text-ink-muted">
          Mỗi kiểu lỗi một dòng, đếm số lần. Thông điệp đã che số điện thoại / tên / mã khách. Mã yêu
          cầu dùng để tra log: <code>journalctl CONTAINER_NAME=clinicai_prod-api-1 | grep &lt;mã&gt;</code>.
        </p>
        {loi === null ? (
          <p className="text-body text-ink-muted">Đang tải…</p>
        ) : loi.length === 0 ? (
          <p className="rounded-control bg-success-bg px-3 py-2 text-body text-success">Không có lỗi nào cần xử lý.</p>
        ) : (
          <ul className="space-y-2">
            {loi.map((l) => (
              <li key={l.id} className="rounded-card border border-hairline bg-surface p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Chip tone={NHAN_TT[l.trang_thai].tone}>{NHAN_TT[l.trang_thai].nhan}</Chip>
                  <Chip tone="neutral">{NHAN_NGUON[l.nguon]}</Chip>
                  <span className="min-w-0 break-all text-body font-semibold text-ink">{l.vi_tri}</span>
                </div>
                <p className="mt-1 break-words text-body text-ink">
                  <b>{l.kieu}</b>
                  {l.thong_diep ? `: ${l.thong_diep}` : ""}
                </p>
                <p className="mt-1 text-meta text-ink-muted">
                  {l.so_lan} lần · lần đầu {ngayGio(l.lan_dau)} · lần cuối {ngayGio(l.lan_cuoi)}
                  {l.ma_yeu_cau ? ` · mã ${l.ma_yeu_cau.slice(0, 8)}` : ""}
                  {l.doi_boi ? ` · ${l.doi_boi} đánh dấu` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-1">
                  {(["DA_BIET", "DA_SUA", "BO_QUA"] as const)
                    .filter((t) => t !== l.trang_thai)
                    .map((t) => (
                      <Button
                        key={t}
                        type="button"
                        size="sm"
                        variant={t === "DA_SUA" ? "soft" : "ghost"}
                        disabled={dang === l.id}
                        onClick={() => void doi(l.id, t)}
                      >
                        {NHAN_TT[t].nhan}
                      </Button>
                    ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
